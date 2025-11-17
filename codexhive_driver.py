#!/usr/bin/env python3
"""Simple file-driven CodexHive MCP client for manual orchestration."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict

import sys

ROOT = Path(__file__).resolve().parent
MCP_DIR = ROOT / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from dev_smoke_client import SmokeClient  # type: ignore  # pylint: disable=wrong-import-position

CMD_FILE = Path("/tmp/codexhive_cmds.jsonl")
EVENT_FILE = Path("/tmp/codexhive_events.jsonl")
POLL_INTERVAL = 0.5


def append_event(event: Dict[str, Any]) -> None:
    EVENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with EVENT_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, separators=(",", ":")) + "\n")


def main() -> int:
    client = SmokeClient("python3", [str(MCP_DIR / "codexctl-mcp.py")], timeout=120.0)
    try:
        ready = client.read()
        append_event({"type": "serverReady", "payload": ready})
        init = client.request(
            "initialize",
            {
                "protocolVersion": "1.0",
                "capabilities": {},
                "clientInfo": {"name": "codexhive-driver", "version": "0.1"},
            },
        )
        append_event({"type": "initialize", "payload": init})
        tools = client.request("tools/list", {})
        append_event({"type": "tools", "payload": tools})

        last_pos = 0
        CMD_FILE.touch(exist_ok=True)
        while True:
            with CMD_FILE.open("r", encoding="utf-8") as handle:
                handle.seek(last_pos)
                while True:
                    line = handle.readline()
                    if not line:
                        break
                    last_pos = handle.tell()
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        cmd = json.loads(line)
                    except json.JSONDecodeError as exc:
                        append_event({"type": "error", "error": f"Invalid JSON: {exc}", "raw": line})
                        continue
                    cmd_id = cmd.get("id")
                    action = cmd.get("action")
                    args = cmd.get("args") or {}
                    try:
                        if action == "shutdown":
                            append_event({"id": cmd_id, "status": "ok", "result": "shutting down"})
                            return 0
                        elif action == "launch":
                            result = client.call_tool("launch_codex", args)
                        elif action == "send_input":
                            result = client.call_tool("send_input", args)
                        elif action == "read_output":
                            result = client.call_tool("read_output", args)
                        elif action == "terminate":
                            result = client.call_tool("terminate_instance", args)
                        elif action == "signal":
                            result = client.call_tool("signal_instance", args)
                        elif action == "list_instances":
                            result = client.call_tool("list_instances", {})
                        elif action == "status_report":
                            result = client.call_tool("status_report", {})
                        elif action == "assign_role":
                            result = client.call_tool("assign_role", args)
                        elif action == "checkpoint":
                            result = client.call_tool("checkpoint_instance", args)
                        elif action == "ping":
                            result = client.call_tool("ping", {})
                        else:
                            append_event({"id": cmd_id, "status": "error", "error": f"Unknown action {action}"})
                            continue
                        append_event({"id": cmd_id, "status": "ok", "result": result})
                    except Exception as exc:  # pragma: no cover
                        append_event({"id": cmd_id, "status": "error", "error": str(exc)})
            time.sleep(POLL_INTERVAL)
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
