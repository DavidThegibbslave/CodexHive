#!/usr/bin/env python3
"""Quick harness to test the codexhive MCP server over stdio."""
from __future__ import annotations

import argparse
import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:  # pragma: no cover - Windows-specific wait path
    import ctypes
    import msvcrt

    _WAIT_OBJECT_0 = 0x00000000
    _WAIT_TIMEOUT = 0x00000102
    _kernel32 = ctypes.windll.kernel32

DEFAULT_SERVER = str(Path(__file__).with_name("codexctl-mcp.py"))


def _encode_frame(payload: Dict[str, Any]) -> bytes:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    return header + body


def _parse_content_length(header: str) -> Optional[int]:
    for line in header.split("\r\n"):
        lower = line.lower()
        if lower.startswith("content-length"):
            try:
                return int(line.split(":", 1)[1].strip())
            except (ValueError, IndexError):
                return None
    return None


def _read_frame(proc: subprocess.Popen[bytes], buffer: bytearray, timeout: float) -> Dict[str, Any]:
    deadline = time.time() + timeout
    stdout_fd = proc.stdout.fileno()  # type: ignore[arg-type]
    while True:
        header_end = buffer.find(b"\r\n\r\n")
        if header_end != -1:
            header_block = buffer[:header_end].decode("utf-8", errors="ignore")
            content_length = _parse_content_length(header_block)
            body_start = header_end + 4
            if content_length is None:
                raw = buffer[:header_end].strip()
                del buffer[:header_end + 4]
                if raw:
                    return json.loads(raw.decode("utf-8"))
            else:
                while len(buffer) - body_start < content_length:
                    _fill_buffer(stdout_fd, buffer, deadline)
                body = bytes(buffer[body_start : body_start + content_length])
                del buffer[: body_start + content_length]
                return json.loads(body.decode("utf-8"))

        newline = buffer.find(b"\n")
        if newline != -1:
            raw = bytes(buffer[:newline]).strip()
            del buffer[: newline + 1]
            if raw:
                return json.loads(raw.decode("utf-8"))

        _fill_buffer(stdout_fd, buffer, deadline)


def _fill_buffer(stdout_fd: int, buffer: bytearray, deadline: float) -> None:
    remaining = max(0.0, deadline - time.time())
    if remaining == 0:
        raise TimeoutError("timed out waiting for MCP data")
    _wait_for_data(stdout_fd, remaining)
    chunk = os.read(stdout_fd, 4096)
    if not chunk:
        raise EOFError("MCP server closed the STDOUT pipe")
    buffer.extend(chunk)


def _wait_for_data(stdout_fd: int, remaining: float) -> None:
    if IS_WINDOWS:
        handle = msvcrt.get_osfhandle(stdout_fd)
        if handle == -1:
            raise OSError("invalid stdout handle")
        wait_ms = max(0, int(remaining * 1000))
        result = _kernel32.WaitForSingleObject(handle, wait_ms)
        if result == _WAIT_TIMEOUT:
            raise TimeoutError("timed out waiting for MCP data")
        if result != _WAIT_OBJECT_0:
            raise OSError(f"WaitForSingleObject failed with code {result}")
    else:
        ready, _, _ = select.select([stdout_fd], [], [], remaining)
        if not ready:
            raise TimeoutError("timed out waiting for MCP data")


class SmokeClient:
    def __init__(self, command: str, args: list[str], timeout: float) -> None:
        self.proc = subprocess.Popen(
            [command, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self.timeout = timeout
        self.buffer = bytearray()
        self.next_id = 1

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def send(self, payload: Dict[str, Any]) -> None:
        assert self.proc.stdin is not None
        frame = _encode_frame(payload)
        fd = self.proc.stdin.fileno()
        view = memoryview(frame)
        while view:
            written = os.write(fd, view)
            view = view[written:]

    def read(self) -> Dict[str, Any]:
        return _read_frame(self.proc, self.buffer, self.timeout)

    def request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        req_id = self.next_id
        self.next_id += 1
        self.send({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params})
        while True:
            message = self.read()
            if message.get("id") == req_id:
                return message
            # surface stray notifications
            dumped = json.dumps(message)
            print(f"[notification] {dumped}")

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return self.request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments,
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test for codexhive MCP server")
    parser.add_argument("--cmd", default="python3", help="Command used to start the server")
    parser.add_argument(
        "--cmd-arg",
        action="append",
        dest="cmd_args",
        default=[DEFAULT_SERVER],
        help="Arguments passed to the command (can be repeated)",
    )
    parser.add_argument("--timeout", type=float, default=5.0, help="Read timeout in seconds")
    parser.add_argument(
        "--skip-server-ready",
        action="store_true",
        help="Do not wait for notifications/serverReady before sending initialize",
    )
    parser.add_argument(
        "--launch-smoke",
        action="store_true",
        help="Try launch_codex/send_input/read_output/terminate_instance tool sequence",
    )
    args = parser.parse_args()

    client = SmokeClient(args.cmd, args.cmd_args, args.timeout)
    try:
        if not args.skip_server_ready:
            ready_msg = client.read()
            print(f"received: {json.dumps(ready_msg)}")
        init = client.request(
            "initialize",
            {
                "protocolVersion": "1.0",
                "capabilities": {},
                "clientInfo": {"name": "codexhive-smoke", "version": "dev"},
            },
        )
        print(f"initialize response: {json.dumps(init)}")
        tools = client.request("tools/list", {})
        print(f"tools/list: {json.dumps(tools)}")
        try:
            ping = client.call_tool("ping", {})
            print(f"ping: {json.dumps(ping)}")
        except Exception as exc:  # pragma: no cover
            print(f"ping failed: {exc}")
        if args.launch_smoke:
            launch = client.call_tool(
                "launch_codex",
                {
                    "name": "smoke",
                    "shellCommand": "python3 -c \"import time; print('codexhive smoke'); time.sleep(1)\"",
                    "usePty": False,
                },
            )
            print(f"launch_codex: {json.dumps(launch)}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
