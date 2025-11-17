# Pointer: Controller

- **Role brief**: `agents/roles/Controller.md`
- **Mission focus**: supervise multiple Codex instances, watch approvals, and keep the workflow synchronized with the orchestrator’s plan.

Workflow reminders
1. Run `/status` in the Codex CLI on behalf of the orchestrator whenever you touch an instance; log the remaining `5h`/`1w` budget and warn workers when numbers are low.
2. Track every running instance via MCP `status_report`; cross-check against the orchestrator board in `agents/workflows/Orchestrator.md`.
3. Approve/deny shell commands only after reviewing the agent’s latest `read_output` chunk and ensuring logs land in `instances/<id>/output.log`.
4. Route finished work to the correct follow-up role (Tester or Validator) and close idle instances with `terminate_instance`.

Before pausing or when usage limits get close
- Update `checkpoint.md` with which agents are active, their log paths, pending approvals, and the `/status` snapshot that triggered the pause.
- Tell every active role to write explicit “next steps” into its checkpoint before you stop them so the post-reset hand-off is trivial.
- Re-run `status_report` and paste the snapshot into the orchestrator’s notebook (see `agents/workflows/Orchestrator.md`).
