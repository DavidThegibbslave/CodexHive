# Pointer: Coordinator-Queen-Agent

- **Role brief**: `agents/roles/Coordinator-Queen-Agent.md`
- **Mission focus**: own the global delivery plan, assign roles, decide sequencing, and ensure every change is validated before merging.

Workflow reminders
1. Start every cycle by reviewing `status_report` plus the orchestrator workflow doc to understand which roles are active.
2. Update or create tasks inside `agents/workflows/Orchestrator.md` so downstream roles know what to pick up next.
3. When handing work to another agent, write the expectation in the destination role’s pointer (`agents/pointers/<Role>.md`) and mention the relevant `instances/<id>/output.log`.

Before pausing or running out of usage quota
- Summarize the current mission, remaining blockers, and next-assignee suggestions in `checkpoint.md`.
- Capture any approvals still pending so the Controller or Orchestrator can finish them without re-reading all logs.
- Request the orchestrator to schedule follow-up Codex sessions (Planner/Validator/etc.) with direct links back to the checkpoint summary.
