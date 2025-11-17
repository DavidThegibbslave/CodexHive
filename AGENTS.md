# CodexHive Agent Instructions

- CodexHive relies on the custom MCP server in `mcp/codexctl-mcp.py`. Always verify it is running (`python3 mcp/dev_smoke_client.py` or `/mcp` → tools/list) before assuming failures are on the Codex CLI side.
- When an error or unexpected behavior occurs, query the Context7 MCP server (`context7`) for the latest Codex/MCP documentation before changing code or configs. The CLI command `codex mcp call context7 resolve-library-id -- <query>` (or `/mcp` → Context7 tools) should be your first step.
- Keep `agent.md`, `latest-log.txt`, and `mcp/codexctl.log` up to date with findings so the next agent has the full context.
- After every failed Codex run, append the newest CLI + MCP logs to `latest-log.txt` per the workflow described in `agent.md`.
