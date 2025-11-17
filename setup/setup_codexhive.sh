#!/usr/bin/env bash
set -euo pipefail

SERVER_NAME="${SERVER_NAME:-codexhive}"
SCRIPT_PATH="${SCRIPT_PATH:-/mnt/c/codexhive/mcp/codexctl-mcp.py}"
STARTUP_TIMEOUT="${STARTUP_TIMEOUT:-30}"
CONFIG_DIR="${HOME}/.codex"
CONFIG_FILE="${CONFIG_DIR}/config.toml"

mkdir -p "$CONFIG_DIR"
if [[ ! -f "$CONFIG_FILE" ]]; then
  touch "$CONFIG_FILE"
fi

python3 - <<'PY' "$CONFIG_FILE" "$SERVER_NAME" "$SCRIPT_PATH" "$STARTUP_TIMEOUT"
import json
import re
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
server_name = sys.argv[2]
script_path = sys.argv[3]
startup_timeout = int(sys.argv[4])
text = config_path.read_text(encoding="utf-8")

if text and not text.endswith("\n"):
    text += "\n"

feature_pattern = re.compile(r"(?ms)^\[features\]\s*(.*?)(?=^\[|\Z)")
match = feature_pattern.search(text)
if not match:
    text += f"\n[features]\nrmcp_client = true\n"
else:
    body = match.group(1)
    if "rmcp_client" not in body:
        start, end = match.span(1)
        new_body = body
        if new_body and not new_body.endswith("\n"):
            new_body += "\n"
        new_body += "rmcp_client = true\n"
        text = text[:start] + new_body + text[end:]

def upsert_server_block(contents: str) -> str:
    pattern = re.compile(rf"(?ms)^\[mcp_servers\\.{re.escape(server_name)}\]\s*(.*?)(?=^\[|\Z)")
    match = pattern.search(contents)
    block = [
        f"command = \"python3\"",
        "args = " + json.dumps([script_path]),
        f"startup_timeout_sec = {startup_timeout}",
    ]
    rendered = "\n".join(block) + "\n"
    if not match:
        addition = f"\n[mcp_servers.{server_name}]\n{rendered}"
        return contents + addition
    start, end = match.span(1)
    return contents[:start] + rendered + contents[end:]

text = upsert_server_block(text)
config_path.write_text(text.lstrip("\n"), encoding="utf-8")
PY

cat <<EOF
Configured MCP server '$SERVER_NAME' to run '$SCRIPT_PATH'.
Update applied to $CONFIG_FILE.
Run 'codex' and /mcp to confirm the connection.
EOF
