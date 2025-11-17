# Pointer: Orchestrator

- **Workflow guide**: `agents/workflows/Orchestrator.md`
- **Mission focus**: be the single Codex instance that drives CodexHive via MCP—spawning roles, waiting for their outputs, granting approvals, and coordinating checkpoints/resumptions.

Operational checklist
1. Before approving or issuing any request, run `/status` in the Codex CLI and log how much of the `5h`/`1w` allowance remains; treat warnings as a signal to start pausing workers.
2. Use MCP `launch_codex` with `mirrorToCmd=true` for any role that needs a human-visible terminal. Label each window with the role + instance id so it is easy to track.
3. After every `send_input`, call `read_output(waitSeconds=2)` and decide whether to approve, request changes, or reroute work to another role.
4. Poll `status_report` on a cadence (e.g., every 5 minutes) to see if any instance is idle, blocked, or near the token/time budget.
5. Trigger `checkpoint_instance` whenever a worker is about to pause so the continuation prompt plus log path is captured, and explicitly tell every active agent to jot down “next steps” when `/status` shows low quota.

Escalation/hand-off
- When a worker finishes a milestone, archive the log path + checkpoint into `latest-log.txt` and spin up the next role with those references embedded in the prompt.
- If quotas expire mid-run, close the affected instances with `terminate_instance` after ensuring their checkpoints exist. Resume later by launching a fresh role and pasting the stored summary.
