# CodexHive MCP Status – 2025-11-14

## Current situation
- `mcp/codexctl-mcp.py` again relies on FastMCP’s default stdio transport (newline-delimited JSON) and emits a `notifications/serverReady` message before `mcp.run()`. Currently exported tool: `ping`.
- `python3 mcp/dev_smoke_client.py` exercises the entire handshake (`serverReady → initialize → tools/list → ping`) and serves as a fast health check without launching the Codex TUI.
- Codex CLI 0.58.0 connects successfully: `codex exec --skip-git-repo-check --sandbox read-only -- ls` runs without warnings and `/mcp` lists `codexhive`.

## Evidence
- `mcp/codexctl.log` shows `onMessage …` / `writeFrame …` entries for each request (see excerpts labeled `=== … Smoke test success ===` in `latest-log.txt`).
- `python3 mcp/dev_smoke_client.py --timeout 5` hits `initialize`, `tools/list`, and `ping` without errors.
- `codex exec --skip-git-repo-check --sandbox read-only -- ls` is warning-free (session `019a81a0-1f65-7d21-b8ad-719cbaf73252` in `~/.codex/log/codex-tui.log`).

## Next steps
1. When new issues appear, run `python3 mcp/dev_smoke_client.py` first. If it passes, append both CLI and MCP logs to `latest-log.txt` and prepare a bug report if needed.
2. Re-enable the full tool suite (`launch_codex`, `send_input`, etc.) once the skeleton stabilizes—right now only `ping` is exposed.
3. Keep the setup scripts (`setup/setup_codexhive.sh` + `.ps1`) current and always ensure `[features].rmcp_client = true` in `~/.codex/config.toml`.
