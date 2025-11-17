# Pointer: Validator-Reviewer-Agent

- **Role brief**: `agents/roles/Validator-Reviewer-Agent.md`
- **Mission focus**: inspect diffs, confirm requirements, enforce coding standards, and write the final approval note before delivery.

Workflow reminders
1. Read the latest `checkpoint.md` plus the `git diff` link provided by the Coder/Tester.
2. Record every finding (file + line) either in `agent.md` or the repo’s review log so feedback stays traceable.
3. When satisfied, notify the orchestrator and Controller that the branch is ready for merge/deployment.

Before pausing or losing the session
- Summarize outstanding issues + file references in `checkpoint.md`.
- Flag any missing evidence (tests, screenshots) so the orchestrator can assign another agent if needed.
- If everything is clean, instruct the orchestrator whether to archive or terminate the involved instances.
