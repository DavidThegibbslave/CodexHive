# How to integrate Codex CLI and MCP

## Running Codex as an MCP server
- Codex ships with its own MCP server entrypoint. Launch with `codex mcp-server` (long-lived stdio server) or via MCP Inspector: `npx @modelcontextprotocol/inspector codex mcp-server`.
- The server exposes two tools:
  - `codex` – start a new Codex session; accepts prompt, approval-policy (`never`, `on-failure`, `untrusted`), sandbox (`workspace-write`, etc.), cwd, model override, config overrides, etc.
  - `codex-reply` – continue an existing conversation by id; requires `conversationId` and next `prompt`.
- Inspector default timeouts (30s) are too short; set Request + Total timeout to ≥600000 ms for real Codex runs.

## Leveraging Codex MCP from custom agents
- Use OpenAI Agents SDK’s `MCPServerStdio` to spawn Codex MCP (e.g. `command="npx"`, `args=["-y","codex","mcp"]`). Keep `client_session_timeout_seconds` high (e.g. 360000) so Codex sessions persist.
- Attach MCP server handles (`codex_mcp_server`) to `Agent` definitions via `mcp_servers=[codex_mcp_server]`.
- Typical workflow:
  1. Start MCP server context.
  2. Define role-specific agents (Designer, Frontend, Backend, Tester, PM, etc.) with instructions referencing Codex MCP for file writes (set approval-policy, sandbox, etc.).
  3. Use `Runner.run(...)` to orchestrate tasks, optionally with hand-offs and guardrails.
- For single-agent automation, Codex MCP can act as a deterministic worker (e.g., build a game from a designer brief). For multi-agent pipelines, coordinate deliverables and gating conditions via instructions + handoffs.

## Codex CLI best practices for MCP
- Always enable `[features].rmcp_client = true` in `~/.codex/config.toml` (or `codex --enable rmcp_client`).
- Configure STDIO MCP servers under `[mcp_servers.<name>]` with `command`, `args`, optional `env`, and `startup_timeout_sec`.
- Use `codex mcp add/list/get/remove` to manage entries; CLI + IDE share the same config.
- When connecting Codex to third-party MCPs (Context7, Playwright, Figma, etc.), define them in config or via CLI.

## Prompting + AGENTS.md guidance
- Codex reads persistent instructions from `AGENTS.md` / `AGENTS.override.md` starting at `~/.codex` and down the repo tree. Use overrides to tailor behavior per directory.
- Keep instructions under `project_doc_max_bytes` (default 32 KiB); configure `project_doc_fallback_filenames` for alternate names.
- Good prompts:
  - Provide narrow file pointers/identifiers.
  - Include verification steps or test commands.
  - Specify tooling expectations (e.g., "always run `npm test`" or "log failing commands").
  - Break large work into smaller steps or ask Codex to plan first.
- Use Codex for debugging by pasting logs/traces; include reproduction steps.

## Suggested defaults for CodexHive
- When launching Codex subprocesses through MCP tools (launch_codex, etc.), set `approval-policy="never"` and `sandbox="workspace-write"` unless an approval gate is required.
- Persist all diagnostic logs (CLI + server) to `/mnt/c/codexhive/latest-log.txt` for shared debugging.
- When orchestrating multiple Codex roles, load role prompts from `agents/roles/*.md` and rely on MCP tools to stream outputs, send input, and terminate instances.

Keep this file updated whenever new Codex CLI or MCP features become relevant.
