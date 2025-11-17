# Pointer: Coder-Builder-Agent

- **Role brief**: `agents/roles/Coder-Builder-Agent.md`
- **Mission focus**: implement the plan handed over from Architect/Coordinator, keep changes small and well-tested, and document every command that mutates the repo.

Workflow reminders
1. Read the latest architecture notes plus `instances/<id>/checkpoint.md` for this worker.
2. Use MCP `send_input`/`read_output` cycles to run commands exactly as the orchestrator approves (stick to documented toolchain commands).
3. Keep diffs staged in logical chunks so Controller/Validator can review quickly.

Before pausing or hitting token limits
- Capture outstanding TODOs + test coverage gaps in `checkpoint.md`.
- Mention any partially-applied patches or uncommitted changes so the orchestrator can decide whether to resume or revert.
- Highlight which files need reviewer attention in the next phase (Controller or Validator).
