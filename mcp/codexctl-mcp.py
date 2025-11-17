#!/usr/bin/env python3
"""CodexHive MCP server with Codex orchestration helpers."""
from __future__ import annotations

import json
import logging
import os
import select
import signal
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass, field
from itertools import count
from pathlib import Path
from typing import Dict, List, Optional
import threading
import termios

from fastmcp import FastMCP

os.environ.setdefault("FASTMCP_SHOW_CLI_BANNER", "false")
os.environ.setdefault("FASTMCP_LOG_LEVEL", "info")

BASE_DIR = Path("/mnt/c/codexhive")
LOG_PATH = BASE_DIR / "mcp" / "codexctl.log"
INSTANCE_ROOT = BASE_DIR / "instances"
ROLES_DIR = BASE_DIR / "agents" / "roles"
POINTERS_DIR = BASE_DIR / "agents" / "pointers"
CMD_PATH = Path("/mnt/c/Windows/System32/cmd.exe")

INSTANCE_COUNTER = count(1)
INSTANCES: Dict[str, "CodexInstance"] = {}
MAX_BUFFER_BYTES = 131_072


@dataclass
class CodexInstance:
    id: str
    name: str
    label: str
    role_name: Optional[str]
    role_path: Optional[str]
    prompt: Optional[str]
    use_pty: bool
    workdir: Path
    env: Dict[str, str]
    command: List[str]
    process: subprocess.Popen[bytes]
    master_fd: Optional[int]
    log_path: Path
    read_cursor: int = 0
    buffer: bytearray = field(default_factory=bytearray)
    created_at: float = field(default_factory=time.time)
    last_output_at: float = field(default_factory=time.time)
    status: str = "running"
    mirror_window_label: Optional[str] = None
    cursor_query_tail: bytes = field(default_factory=bytes)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    stop_event: threading.Event = field(default_factory=threading.Event, repr=False)
    monitor_thread: Optional[threading.Thread] = field(default=None, repr=False)


def configure_logging() -> None:
    primary = LOG_PATH
    fallback = Path.home() / ".codexhive" / "codexctl.log"
    for path in (primary, fallback):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            logging.basicConfig(
                filename=path,
                level=logging.INFO,
                format="%(asctime)sZ\t%(levelname)s\t%(message)s",
                force=True,
            )
            logging.info("logging initialized at %s", path)
            return
        except PermissionError:
            continue
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)sZ\t%(levelname)s\t%(message)s",
        force=True,
    )
    logging.warning("Unable to create codexctl.log on any path; logging to stderr only")


def ensure_directories() -> None:
    global INSTANCE_ROOT
    candidates = [
        BASE_DIR / "instances",
        Path.home() / ".codexhive" / "instances",
    ]
    for path in candidates:
        try:
            path.mkdir(parents=True, exist_ok=True)
            INSTANCE_ROOT = path
            break
        except PermissionError:
            logging.warning("unable to create %s; trying fallback", path)
            continue
    else:
        raise PermissionError("Cannot create any runtime instances directory")
    try:
        POINTERS_DIR.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        logging.warning("pointer directory %s not writable (read-only fallback)", POINTERS_DIR)


def maybe_send_server_ready() -> None:
    raw_flag = os.environ.get("CODEXHIVE_SEND_SERVER_READY", "1")
    enabled = raw_flag.strip().lower() not in {"0", "false", "no"}
    if not enabled:
        logging.info("serverReady suppressed by CODEXHIVE_SEND_SERVER_READY=%s", raw_flag)
        return
    message = {
        "jsonrpc": "2.0",
        "method": "notifications/serverReady",
        "params": {},
    }
    payload = json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
    os.write(sys.stdout.fileno(), payload)
    logging.info("writeFrame id=no-id method=notifications/serverReady")


def _gen_instance_id() -> str:
    return f"cx-{next(INSTANCE_COUNTER):04d}"


def _resolve_role(role_name: Optional[str], role_path: Optional[str]) -> tuple[Optional[str], Optional[Path], Optional[str]]:
    path: Optional[Path] = None
    if role_path:
        candidate = Path(role_path)
        if not candidate.is_file():
            candidate = (BASE_DIR / role_path).resolve()
        if candidate.is_file():
            path = candidate
        else:
            raise FileNotFoundError(f"rolePath {role_path} not found")
    elif role_name:
        candidate = ROLES_DIR / f"{role_name}.md"
        if not candidate.is_file():
            candidate = ROLES_DIR / role_name
        if candidate.is_file():
            path = candidate
        else:
            raise FileNotFoundError(f"role {role_name} not found in agents/roles")
    text = path.read_text(encoding="utf-8") if path else None
    return role_name, path, text


def _build_command(command: Optional[str], shell_command: Optional[str], args: Optional[List[str]]) -> List[str]:
    if shell_command:
        return ["bash", "-lc", shell_command]
    cmd = command or "codex"
    if args:
        return [cmd, *args]
    return [cmd]


def _create_process(cmd: List[str], workdir: Path, env: Dict[str, str], use_pty: bool) -> tuple[subprocess.Popen[bytes], Optional[int]]:
    if use_pty:
        import pty  # imported lazily to keep Windows fallback happier

        master_fd, slave_fd = pty.openpty()
        _configure_slave_pty(slave_fd)
        proc = subprocess.Popen(
            cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=str(workdir),
            env=env,
            close_fds=True,
        )
        os.close(slave_fd)
        os.set_blocking(master_fd, False)
        return proc, master_fd
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(workdir),
        env=env,
        bufsize=0,
        close_fds=True,
    )
    if proc.stdout is not None:
        os.set_blocking(proc.stdout.fileno(), False)
    return proc, None


def _configure_slave_pty(fd: int) -> None:
    try:
        attrs = termios.tcgetattr(fd)
    except termios.error:
        return
    lflag = attrs[3]
    if lflag & (termios.ECHO | termios.ICANON):
        attrs[3] = lflag & ~(termios.ECHO | termios.ICANON)
    attrs[6][termios.VMIN] = 1
    attrs[6][termios.VTIME] = 0
    try:
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
    except termios.error:
        pass


def _instance_dir(instance_id: str) -> Path:
    path = INSTANCE_ROOT / instance_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_log(log_path: Path, data: bytes) -> None:
    with log_path.open("ab") as handle:
        handle.write(data)


def _collect_output(instance: CodexInstance) -> None:
    with instance.lock:
        _collect_output_locked(instance)


def _collect_output_locked(instance: CodexInstance) -> None:
    if instance.use_pty and instance.master_fd is None:
        return
    fd = instance.master_fd if instance.use_pty else instance.process.stdout.fileno() if instance.process.stdout else None
    if fd is None:
        return
    while True:
        rlist, _, _ = select.select([fd], [], [], 0)
        if not rlist:
            break
        try:
            chunk = os.read(fd, 4096)
        except OSError as exc:
            if exc.errno in {5, 11}:  # EIO/EAGAIN
                break
            raise
        if not chunk:
            break
        data_for_detection = instance.cursor_query_tail + chunk
        cursor_seq = b"\x1b[6n"
        search_idx = 0
        while True:
            found = data_for_detection.find(cursor_seq, search_idx)
            if found == -1:
                break
            try:
                _send_text(instance, "\x1b[1;1R", False)
                logging.debug("responded to cursor query on %s", instance.id)
            except Exception as exc:  # pragma: no cover
                logging.warning("failed to respond to cursor query on %s: %s", instance.id, exc)
                break
            search_idx = found + len(cursor_seq)
        tail_len = len(cursor_seq) - 1
        instance.cursor_query_tail = data_for_detection[-tail_len:] if tail_len > 0 and len(data_for_detection) >= tail_len else data_for_detection
        instance.buffer.extend(chunk)
        if len(instance.buffer) > MAX_BUFFER_BYTES:
            drop = len(instance.buffer) - MAX_BUFFER_BYTES
            instance.buffer = instance.buffer[drop:]
            instance.read_cursor = max(0, instance.read_cursor - drop)
        instance.last_output_at = time.time()
        _write_log(instance.log_path, chunk)
    if instance.process.poll() is not None and instance.status == "running":
        instance.status = f"exited({instance.process.returncode})"
        instance.stop_event.set()


def _send_text(instance: CodexInstance, text: str, append_newline: bool) -> None:
    payload = text if not append_newline else text + "\n"
    data = payload.encode("utf-8")
    target_fd = instance.master_fd if instance.use_pty else instance.process.stdin.fileno() if instance.process.stdin else None
    if target_fd is None:
        raise RuntimeError("instance stdin not available")
    view = memoryview(data)
    while view:
        written = os.write(target_fd, view)
        view = view[written:]


def _monitor_instance_output(instance: CodexInstance) -> None:
    while True:
        if instance.stop_event.is_set():
            return
        _collect_output(instance)
        with instance.lock:
            is_running = instance.status == "running"
        if not is_running:
            return
        time.sleep(0.05)


def _start_monitoring(instance: CodexInstance) -> None:
    if instance.monitor_thread and instance.monitor_thread.is_alive():
        return
    thread = threading.Thread(target=_monitor_instance_output, args=(instance,), daemon=True)
    instance.monitor_thread = thread
    thread.start()


def _stop_monitoring(instance: CodexInstance) -> None:
    instance.stop_event.set()
    thread = instance.monitor_thread
    if thread and thread.is_alive():
        thread.join(timeout=1.0)


def _to_windows_path(path: Path) -> Optional[str]:
    resolved = path.resolve()
    parts = resolved.parts
    if len(parts) >= 4 and parts[1] == "mnt":
        drive = parts[2].upper()
        rest = Path(*parts[3:]).as_posix().replace("/", "\\")
        return f"{drive}:\\{rest}"
    return None


def _mirror_in_cmd(instance: CodexInstance, label: Optional[str]) -> Optional[str]:
    if not CMD_PATH.exists():
        logging.warning("cmd.exe unavailable; cannot open mirror window")
        return None
    windows_log = _to_windows_path(instance.log_path)
    if not windows_log:
        logging.warning("cannot map %s to Windows path", instance.log_path)
        return None
    win_label = label or instance.label
    ps_command = textwrap.dedent(
        f"""
        $Host.UI.RawUI.WindowTitle = '{win_label}';
        Write-Host 'Streaming {windows_log} (Ctrl+C to stop)';
        Get-Content -Path '{windows_log}' -Tail 80 -Wait
        """
    ).strip()
    cmd = [
        str(CMD_PATH),
        "/c",
        "start",
        win_label,
        "powershell.exe",
        "-NoExit",
        "-Command",
        ps_command,
    ]
    try:
        subprocess.Popen(cmd)
        instance.mirror_window_label = win_label
        return win_label
    except Exception as exc:  # pragma: no cover
        logging.warning("unable to mirror output in cmd window: %s", exc)
        return None


def _require_instance(instance_id: str) -> CodexInstance:
    if instance_id not in INSTANCES:
        raise ValueError(f"instance {instance_id} not found")
    inst = INSTANCES[instance_id]
    with inst.lock:
        _collect_output_locked(inst)
    return inst


def _resume_hint(instance: CodexInstance) -> str:
    if instance.role_name:
        pointer = POINTERS_DIR / f"{instance.role_name}.md"
        if pointer.exists():
            return f"Review {pointer} and {instance.log_path}"
    return f"Review log {instance.log_path} and agents/pointers/README.md"


configure_logging()
ensure_directories()
mcp = FastMCP("codexhive")


@mcp.tool()
def ping() -> str:
    return "pong"


@mcp.tool()
def list_roles() -> Dict[str, Dict[str, str]]:
    roles: Dict[str, Dict[str, str]] = {}
    if ROLES_DIR.is_dir():
        for path in sorted(ROLES_DIR.glob("*.md")):
            name = path.stem
            first_line = path.read_text(encoding="utf-8").splitlines()[0] if path.exists() else ""
            roles[name] = {"path": str(path), "title": first_line.lstrip("# ").strip()}
    return roles


@mcp.tool()
def launch_codex(
    name: Optional[str] = None,
    roleName: Optional[str] = None,
    rolePath: Optional[str] = None,
    prompt: Optional[str] = None,
    shellCommand: Optional[str] = None,
    command: Optional[str] = None,
    args: Optional[List[str]] = None,
    workdir: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    usePty: bool = True,
    mirrorToCmd: bool = False,
    cmdLabel: Optional[str] = None,
    initialInput: Optional[str] = None,
) -> Dict[str, str]:
    role_name, resolved_path, role_text = _resolve_role(roleName, rolePath)
    instance_id = _gen_instance_id()
    resolved_workdir = Path(workdir) if workdir else BASE_DIR
    resolved_workdir.mkdir(parents=True, exist_ok=True)
    env_vars = os.environ.copy()
    if env:
        env_vars.update({k: str(v) for k, v in env.items()})
    cmd = _build_command(command, shellCommand, args)
    proc, master_fd = _create_process(cmd, resolved_workdir, env_vars, usePty)
    log_dir = _instance_dir(instance_id)
    log_path = log_dir / "output.log"
    inst_name = name or (role_name or "codex")
    label = f"{inst_name} ({instance_id})" if role_name is None else f"{inst_name}/{role_name} ({instance_id})"
    instance = CodexInstance(
        id=instance_id,
        name=inst_name,
        label=label,
        role_name=role_name,
        role_path=str(resolved_path) if resolved_path else None,
        prompt=prompt,
        use_pty=usePty,
        workdir=resolved_workdir,
        env=env_vars,
        command=cmd,
        process=proc,
        master_fd=master_fd,
        log_path=log_path,
    )
    INSTANCES[instance_id] = instance
    _start_monitoring(instance)
    logging.info("launch_codex id=%s cmd=%s", instance_id, cmd)

    initial_chunks: List[str] = []
    if role_text:
        initial_chunks.append(
            textwrap.dedent(
                f"""
                You are assuming the role '{role_name}'. Review {resolved_path}.
                When ready, acknowledge with a one-line status and wait for instructions.
                """
            ).strip()
        )
        initial_chunks.append(role_text)
    if prompt:
        initial_chunks.append(prompt)
    if initialInput:
        initial_chunks.append(initialInput)
    for chunk in initial_chunks:
        _send_text(instance, chunk + "\n", False)
        _collect_output(instance)

    mirror_label = None
    if mirrorToCmd:
        mirror_label = _mirror_in_cmd(instance, cmdLabel)

    return {
        "id": instance_id,
        "name": inst_name,
        "label": label,
        "role": role_name or "",
        "logPath": str(log_path),
        "pid": str(proc.pid),
        "mirrorWindowLabel": mirror_label or instance.mirror_window_label or "",
    }


@mcp.tool()
def list_instances() -> List[Dict[str, str]]:
    output: List[Dict[str, str]] = []
    for inst in INSTANCES.values():
        with inst.lock:
            _collect_output_locked(inst)
            output.append(
                {
                    "id": inst.id,
                    "name": inst.name,
                    "label": inst.label,
                    "role": inst.role_name or "",
                    "status": inst.status,
                    "pid": str(inst.process.pid),
                    "logPath": str(inst.log_path),
                    "lastOutputTs": str(inst.last_output_at),
                    "mirrorWindowLabel": inst.mirror_window_label or "",
                }
            )
    return output


@mcp.tool()
def send_input(instanceId: str, text: str, appendNewline: bool = True) -> Dict[str, str]:
    inst = _require_instance(instanceId)
    _send_text(inst, text, appendNewline)
    logging.info("send_input id=%s bytes=%d", instanceId, len(text))
    return {"id": instanceId, "status": "ok"}


@mcp.tool()
def read_output(instanceId: str, maxBytes: int = 4096, waitSeconds: float = 0.0) -> Dict[str, str]:
    inst = _require_instance(instanceId)
    if waitSeconds > 0:
        deadline = time.time() + waitSeconds
        while time.time() < deadline:
            with inst.lock:
                prev_size = len(inst.buffer)
            _collect_output(inst)
            with inst.lock:
                if len(inst.buffer) > prev_size:
                    break
            time.sleep(0.1)
    else:
        _collect_output(inst)
    with inst.lock:
        new_bytes = inst.buffer[inst.read_cursor :]
        inst.read_cursor = len(inst.buffer)
        status = inst.status
        log_path = str(inst.log_path)
    if maxBytes and len(new_bytes) > maxBytes:
        new_bytes = new_bytes[-maxBytes:]
    text = new_bytes.decode("utf-8", errors="replace")
    return {"id": instanceId, "output": text, "status": status, "logPath": log_path}


@mcp.tool()
def terminate_instance(instanceId: str, force: bool = False) -> Dict[str, str]:
    inst = _require_instance(instanceId)
    if inst.status.startswith("exited"):
        return {"id": instanceId, "status": inst.status}
    if force:
        inst.process.kill()
    else:
        inst.process.terminate()
    try:
        inst.process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        inst.process.kill()
    inst.status = f"exited({inst.process.returncode})"
    _stop_monitoring(inst)
    logging.info("terminate_instance id=%s status=%s", instanceId, inst.status)
    return {"id": instanceId, "status": inst.status}


@mcp.tool()
def signal_instance(instanceId: str, signalName: str = "SIGINT") -> Dict[str, str]:
    inst = _require_instance(instanceId)
    signal_upper = signalName.upper()
    if signal_upper == "CTRL_C":
        _send_text(inst, "\x03", False)
    elif signal_upper == "CTRL_D":
        _send_text(inst, "\x04", False)
    else:
        sig = getattr(signal, signal_upper, signal.SIGINT)
        os.kill(inst.process.pid, sig)
    return {"id": instanceId, "status": inst.status}


@mcp.tool()
def assign_role(
    instanceId: str,
    roleName: Optional[str] = None,
    rolePath: Optional[str] = None,
    autoInject: bool = True,
) -> Dict[str, str]:
    inst = _require_instance(instanceId)
    role_name, resolved_path, role_text = _resolve_role(roleName, rolePath)
    inst.role_name = role_name
    inst.role_path = str(resolved_path) if resolved_path else inst.role_path
    if autoInject and role_text:
        _send_text(
            inst,
            textwrap.dedent(
                f"""
                Updating your role to '{role_name}'. Review {resolved_path} and summarize current progress before continuing.
                {role_text}
                """
            ).strip(),
            True,
        )
    return {"id": instanceId, "role": role_name or "", "path": str(resolved_path) if resolved_path else ""}


@mcp.tool()
def mirror_output_window(instanceId: str, label: Optional[str] = None) -> Dict[str, str]:
    inst = _require_instance(instanceId)
    win_label = _mirror_in_cmd(inst, label)
    if not win_label:
        raise RuntimeError("unable to open Windows terminal mirror")
    return {"id": instanceId, "mirrorWindowLabel": win_label}


@mcp.tool()
def status_report() -> Dict[str, List[Dict[str, str]]]:
    entries: List[Dict[str, str]] = []
    now = time.time()
    for inst in INSTANCES.values():
        with inst.lock:
            _collect_output_locked(inst)
            entries.append(
                {
                    "id": inst.id,
                    "label": inst.label,
                    "role": inst.role_name or "",
                    "status": inst.status,
                    "uptimeSeconds": f"{now - inst.created_at:.1f}",
                    "secondsSinceOutput": f"{now - inst.last_output_at:.1f}",
                    "logPath": str(inst.log_path),
                    "resumeHint": _resume_hint(inst),
                }
            )
    return {"instances": entries}


@mcp.tool()
def checkpoint_instance(instanceId: str, summary: Optional[str] = None) -> Dict[str, str]:
    inst = _require_instance(instanceId)
    note = summary or "No summary supplied."
    state_path = inst.log_path.with_name("checkpoint.md")
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    content = textwrap.dedent(
        f"""
        ## Checkpoint {timestamp} UTC
        Role: {inst.role_name or 'unassigned'}
        Pointer: {_resume_hint(inst)}

        {note.strip()}
        """
    ).strip()
    with state_path.open("a", encoding="utf-8") as handle:
        handle.write(content + "\n\n")
    logging.info("checkpoint_instance id=%s path=%s", inst.id, state_path)
    return {"id": inst.id, "checkpointPath": str(state_path)}


if __name__ == "__main__":
    logging.info("codexhive MCP starting")
    maybe_send_server_ready()
    mcp.run(show_banner=False)
