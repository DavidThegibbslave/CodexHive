# Pointer: Tester-Agent

- **Role brief**: `agents/roles/Tester-Agent.md`
- **Mission focus**: decide and run the right validation strategy (unit tests, smoke scripts, manual QA) before code reaches Validator/Controller sign-off.

Workflow reminders
1. Load the change summary + affected files from the prior role’s `checkpoint.md`.
2. Prepare reproducible commands in `latest-log.txt` (or inline in your output) so others can re-run the same checks.
3. Capture failures verbatim in `instances/<id>/output.log` and suggest owners for follow-up fixes.

Before pausing or approaching quotas
- Document coverage gaps and pending tests in `checkpoint.md`.
- Mention any resources you provisioned (test servers, fixtures) so they can be cleaned up or reused.
- Alert the orchestrator if blockers require another Coder-Builder round before validation can proceed.
