# CodexHive Pointer Directory

This directory hosts short “where to look next” notes for every CodexHive role plus the orchestrator. Each pointer keeps three facts in one place:

1. **Primary brief** – link to the long-form role prompt under `agents/roles`.
2. **Runtime breadcrumbs** – where the role should log its current mission status (typically the per-instance `output.log` and `checkpoint.md` inside `/mnt/c/codexhive/instances/<id>`).
3. **Handoff expectation** – who validates the work next and what to prepare before tokens/time-budget expire.

The MCP server exposes these hints via `status_report`/`checkpoint_instance`, so the orchestrator (or any other Codex acting through MCP) always knows which documents to surface when reviving an instance after a pause.

Global policy: the orchestrator (or Controller acting on its behalf) must run the Codex `/status` command frequently—ideally before every request. When either the `5h` or `1w` counters look low, every active role uses its pointer instructions to capture “next steps” plus outstanding TODOs in `instances/<id>/checkpoint.md` so work can resume seamlessly after the reset window.

If you add a new role, create a matching pointer file (`<RoleName>.md`) using the templates below.
