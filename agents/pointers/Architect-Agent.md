# Pointer: Architect-Agent

- **Role brief**: `agents/roles/Architect-Agent.md`
- **Mission focus**: translate the Coordinator’s high-level objectives into concrete technical plans (APIs, data models, file/module structure).

Workflow reminders
1. Scan `agents/workflows/Orchestrator.md` to confirm the current deliverable sequence.
2. Pull the latest requirements/notes from `instances/<id>/checkpoint.md` plus the running `output.log`.
3. Produce architecture notes inside the project repo (preferably under `docs/architecture/` or inline in the relevant source file) before handing off to the Coder-Builder.

Before pausing or when tokens run low
- Append a concise summary + TODO list to the instance’s `checkpoint.md`.
- Point to any diagrams/spec files you created so Constructors/Controllers can load context quickly.
- Notify the orchestrator so it can spin up a Coder-Builder instance with the same checkpoint link.
