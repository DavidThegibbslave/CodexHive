# CodexHive Orchestrator Workflow

The orchestrator is the Codex instance that talks to the CodexHive MCP server and coordinates all subordinate roles. Follow this loop whenever you run an automated session.

## 1. Preparation
1. Vor jeder neuen MCP-Anfrage den Codex-CLI-Befehl `/status` ausführen (oder in der TUI triggern), um den aktuellen Stand der `5h`-/`1w`-Kontingente zu kennen. Notiere Warnungen sofort in deinen Arbeitsnotizen.
2. Ensure the MCP server is running (`python3 mcp/dev_smoke_client.py` should pass) and the Codex CLI session you are using has `/mcp` access.
3. Load `agents/pointers/README.md` plus the pointer for each role you expect to spawn so you know which docs/logs to surface.
4. Decide the initial roster (Planner/Architect/Coder/etc.) and write it down in `agent.md` or your working notes.

## 2. Launch workers with context
1. Call `launch_codex` with at least `name`, `roleName`, and `prompt`. Example:
   ```json
   {
     "name": "Planner",
     "roleName": "Coordinator-Queen-Agent",
     "prompt": "Kick off sprint goal XYZ.",
     "mirrorToCmd": true,
     "cmdLabel": "Planner cx-0001"
   }
   ```
2. Set `mirrorToCmd=true` when you want a Windows terminal that streams the same `output.log` so humans can observe progress. Labels should always include the role and `instanceId`.
3. For sandboxed shell commands (e.g., running scripts directly), use `shellCommand` instead of `command/args`.

## 3. Drive the conversation
1. After sending instructions with `send_input`, immediately poll `read_output(waitSeconds=2)` to capture their response.
2. Approve long-running commands manually: watch the mirrored CMD window or `read_output` until the agent asks for the next step.
3. If a different agent must double-check a change, note the relevant `logPath` + summary in that role’s pointer file and launch the reviewer.

## 4. Monitor health
1. Run `status_report` on a schedule (e.g., every 5 minutes). If `secondsSinceOutput` grows beyond your comfort, ping the worker with a status request.
2. Keep `list_instances` handy; terminate idle ones to conserve hourly quotas.
3. After every `/status` check that shows dwindling `5h` or `1w` budgets, broadcast a “prepare to pause” order: each worker writes the next steps/TODOs into `checkpoint.md`, then you call `checkpoint_instance` so the log path + summary live at `instances/<id>/checkpoint.md` before limits hit zero.

## 5. Pauses and resumptions
1. Before closing a worker, ensure its `checkpoint.md` mentions:
   - Mission goal + remaining work
   - Files touched / commands still running
   - Which role should resume and when
2. Terminate the instance once the checkpoint is written and, if applicable, append the latest logs to `latest-log.txt`.
3. To resume later, relaunch a fresh role and include the checkpoint path plus `logPath` in the prompt so the new instance can self-bootstrap.

## 6. Validation + sign-off
1. Assign the Validator-Reviewer role once coding/testing is done. Feed it the checkpoints and diffs.
2. When Validator approves, instruct the Controller to stop remaining workers and archive their log paths.
3. Update `agent.md` with what shipped, where the logs/checkpoints live, and any open follow-ups.

By keeping this cadence tight, you can juggle multiple Codex agents safely while always knowing which log or checkpoint to surface when quotas or approvals get in the way.
