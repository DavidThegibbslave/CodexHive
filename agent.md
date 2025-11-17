# CodexHive – Agent Handover Notes (agent.md)

Goal
- Keep the CodexHive MCP server healthy so any Codex CLI session (Windows or WSL) can launch, monitor, and terminate subordinate Codex workers via MCP (`launch_codex`, `send_input`, `read_output`, `terminate_instance`, etc.).

Documentation protocol
- Whenever Codex CLI shows an unexpected prompt or the MCP server misbehaves, query the Context7 MCP server (`context7`) for the latest Codex/MCP docs before patching scripts. This keeps fixes aligned with current CLI expectations.
- Log every change, test, or investigation result in `agent.md`, `latest-log.txt`, and `mcp/codexctl.log` so the next operator can resume without digging through terminals.

Usage / token policy
- Before **every** MCP action, run `/status` in the Codex CLI (or have the orchestrator request it) to monitor the 5‑hour and 1‑week quotas.
- If either quota is low (warning badges or only a few minutes/tokens left), order all active roles to capture next steps, TODOs, and relevant log/file paths in `instances/<id>/checkpoint.md`.
- When a quota is nearly exhausted, pause work gracefully (checkpoint + plan in the corresponding pointer/log) and avoid approving new commands until after the reset so nothing is lost.

Current state
- Files and roles
  - MCP wrapper (PowerShell 7): `C:\codexhive\mcp\codexctl-mcp.ps1` calls `wsl.exe -e python3 /mnt/c/codexhive/mcp/codexctl-mcp.py` and keeps stdout clean (no banners or extra characters).
  - Python MCP server + smoke harness: `/mnt/c/codexhive/mcp/codexctl-mcp.py` (FastMCP, newline JSON framing) and `/mnt/c/codexhive/mcp/dev_smoke_client.py` (runs the STDIO handshake and basic tool calls).
  - Setup scripts: `setup/setup_codexhive.ps1` (Windows) and `setup/setup_codexhive.sh` (WSL/Linux) add the correct entries to `~/.codex/config.toml`, including `[features].rmcp_client = true`.
  - Role prompts: `agents/roles/*.md` contain the long-form briefings for Architect/Coder/Controller/etc.; the matching short “pointer” files live under `agents/pointers/*.md`.
  - High-level workflow docs: `README_codexhive.txt` for the user view and `agents/workflows/Orchestrator.md` for the orchestrator loop (status + checkpoint cadence).
- Python MCP server
  - Runs as `FastMCP("codexhive")` and logs to `/mnt/c/codexhive/mcp/codexctl.log` (fallback `~/.codexhive/codexctl.log`).
  - Emits `notifications/serverReady` (toggle with `CODEXHIVE_SEND_SERVER_READY`) and exposes the full tool suite (launch/send/list/read/signals/mirror/status/checkpoint).
  - `python3 mcp/dev_smoke_client.py` validates the handshake: `serverReady → initialize → tools/list → ping → optional launch`.

Configuration
- Windows (`C:\Users\<user>\.codex\config.toml`)
  ```toml
  [mcp_servers.codexhive]
  command = 'C:\\Windows\\System32\\wsl.exe'
  args = ['-e','python3','/mnt/c/codexhive/mcp/codexctl-mcp.py']
  startup_timeout_sec = 30
  ```
- WSL (`~/.codex/config.toml`)
  ```toml
  [mcp_servers.codexhive]
  command = 'python3'
  args = ['/mnt/c/codexhive/mcp/codexctl-mcp.py']
  startup_timeout_sec = 30

  [features]
  rmcp_client = true
  ```
- Optional debugging: set `[mcp_client] log_level = "debug"` and restart Codex to capture verbose MCP traces.

Operations & smoke test cadence
1. Run the setup script (`setup/setup_codexhive.sh` on WSL or `.ps1` on Windows) so `~/.codex/config.toml` stays in sync.
2. Launch Codex CLI with RMCP enabled (`codex --enable rmcp_client` if the flag is not already set).
3. Execute `python3 mcp/dev_smoke_client.py --timeout 10 --launch-smoke` to verify the handshake before touching `/mcp` inside the Codex TUI.
4. Tail `mcp/codexctl.log` (`tail -n 200 /mnt/c/codexhive/mcp/codexctl.log`) and append the relevant portion to `latest-log.txt` whenever something fails—this is the shared incident log.

Available MCP tools (see README + orchestrator workflow for details)
- `launch_codex`: Starts Codex or shell processes with optional PTY, role prompt injection, `mirrorToCmd` log streaming, and direct shell command support.
- `send_input`: Writes text to the instance (`appendNewline` toggles `\n`).
- `read_output`: Returns incremental terminal output, optionally blocking via `waitSeconds`.
- `list_instances`: Shows ID, label, role, status, PID, log path, and mirror information.
- `assign_role` / `list_roles`: Loads role prompts from `agents/roles/*.md` and injects them into a running worker.
- `signal_instance`: Sends SIGINT/SIGTERM or raw control characters (CTRL+C / CTRL+D).
- `mirror_output_window`: Opens a Windows console tailing the log for easier monitoring.
- `terminate_instance`: Gracefully stops a process (or force kills with `force=true`).
- `status_report`: Aggregates uptime, seconds since output, log path, and pointer-based resume hints.
- `checkpoint_instance`: Writes or appends a summary to `instances/<id>/checkpoint.md`.
- `dev_smoke_client`: External helper to drive `initialize`, `tools/list`, `ping`, and a sample `launch_codex`.

Log workflow
- After each noteworthy action, inspect `/mnt/c/codexhive/mcp/codexctl.log` (frames, requests, responses). The MCP server must stay silent on stdout except for JSON messages.
- For shared history, append the last 200 lines of `~/.codex/log/codex-tui.log` and the MCP log excerpt to `/mnt/c/codexhive/latest-log.txt`, tagged with timestamps.
- `latest-log.txt` is strictly for handover—never delete it; just keep appending chronological entries.

Open items / next steps
- Optional: add automatic log truncation/rotation (currently 128 KiB in-memory buffer, file grows indefinitely).
- Add more smoke tests (`send_input`↔`read_output` round-trips, `status_report` assertions, etc.).
- Keep the pointer directory in sync whenever you add a new role, and consider small UI helpers that call `status_report` on a schedule.
