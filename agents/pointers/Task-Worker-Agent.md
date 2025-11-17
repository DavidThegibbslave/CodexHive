# Pointer: Task-Worker-Agent

- **Role brief**: `agents/roles/Task-Worker-Agent.md`
- **Mission focus**: execute tightly scoped chores (renames, documentation edits, scripted refactors) without deviating from the acceptance checklist provided by higher-level roles.

Workflow reminders
1. Read the latest instructions from `checkpoint.md` plus any linked specs before touching files.
2. Confirm every command with the orchestrator/Controller if it could have side effects (npm install, database migrations, etc.).
3. Keep results small and well-described so Validator/Testers can sign off quickly.

Before pausing or when nearing limits
- Note which steps are done and which remain in `checkpoint.md`.
- Attach references to modified files or generated artifacts so the next worker can double-check faster.
- If nothing is pending, ping the orchestrator to park the instance via `terminate_instance` to free resources.
