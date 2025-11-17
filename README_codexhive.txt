# CodexHive – MCP Orchestrator for Codex CLI

CodexHive hosts a Model Context Protocol (MCP) server that can spin up and coordinate multiple Codex CLI sessions (Planner, Builder, Tester, etc.) from a single “orchestrator” Codex instance. This document explains how to plug CodexHive into your Codex CLI on **WSL** and **Windows**, how to verify the MCP link, and where to find the supporting scripts and role prompts.

---

## 1. Prerequisites

- Codex CLI `>= 0.58.0` installed either in WSL (recommended) or on Windows with PowerShell 7.
- Python 3.10+ available in the environment that will run `mcp/codexctl-mcp.py`.
- Node.js (only needed if you plan to work on Codex CLI tooling itself).
- For Windows setups that forward to WSL: WSL must be enabled and able to run `python3`.

> **Tip:** Codex CLI must have the RMCP/MCP client enabled. Either run `codex --enable rmcp_client …` each time or set it permanently in `~/.codex/config.toml`:
>
> ```toml
> [features]
> rmcp_client = true
> ```

---

## 2. WSL setup (Linux path `/mnt/c/codexhive`)

1. **Clone or copy the repository** into `/mnt/c/codexhive`. Stay on the Linux side when editing.
2. **Configure Codex CLI automatically**  
   Run the helper script (still inside WSL):
   ```bash
   /mnt/c/codexhive/setup/setup_codexhive.sh
   ```
   The script writes `~/.codex/config.toml` entries so Codex knows how to start the CodexHive MCP server (`python3 /mnt/c/codexhive/mcp/codexctl-mcp.py`).
3. **Start the MCP server** (if Codex CLI does not launch it automatically):
   ```bash
   cd /mnt/c/codexhive
   python3 mcp/codexctl-mcp.py
   ```
   Leave this running in its own terminal.
4. **Verify the server** by running the smoke test from another terminal:
   ```bash
   cd /mnt/c/codexhive
   python3 mcp/dev_smoke_client.py --timeout 10 --launch-smoke
   ```
   You should see `initialize`, `tools/list`, `ping`, and a small `launch_codex` test succeed.
5. **Launch Codex CLI** (still in WSL):
   ```bash
   codex --enable rmcp_client
   ```
   Inside the Codex TUI run `/mcp` → `tools/list`. You should see a `codexhive` entry exposing tools like `launch_codex`, `send_input`, `status_report`, etc.

---

## 3. Windows setup (PowerShell)

If you run Codex CLI on Windows but still rely on WSL for Python:

1. Open **PowerShell 7** as your normal user.
2. Execute the setup script:
   ```powershell
   Set-Location C:\codexhive
   .\setup\setup_codexhive.ps1
   ```
   This registers an MCP server named `codexhive` that launches `pwsh` → `mcp/codexctl-mcp.ps1`, which in turn calls `wsl.exe -e python3 /mnt/c/codexhive/mcp/codexctl-mcp.py`.
3. Start Codex CLI (`codex` in PowerShell). Use `/mcp` inside the TUI to ensure the server shows up. The Windows script automatically handles launching/monitoring the server process.
4. Logs still live under the WSL path (`/mnt/c/codexhive/mcp/codexctl.log` and `/mnt/c/codexhive/instances/*/output.log`). Use WSL or UNC paths when you need to inspect them from Windows.

---

## 4. Using CodexHive once connected

Inside any Codex CLI session with CodexHive attached:

1. **List tools**: `/mcp` → `tools/list` to confirm availability.
2. **Launch a worker**:
   ```json
   tools/call launch_codex {
     "name": "Planner",
     "roleName": "Coordinator-Queen-Agent",
     "prompt": "Kick off Component Compare Hub milestone planning.",
     "mirrorToCmd": true,
     "cmdLabel": "Planner cx-0008"
   }
   ```
   Each worker receives the relevant role prompt from `agents/roles/*.md`. With `mirrorToCmd=true` a Windows console tails the log (`instances/cx-0008/output.log`).
3. **Drive the worker**: use `send_input` to answer approval prompts or provide context; poll `read_output(waitSeconds=2)` to capture replies.
4. **Monitor everything**: `status_report` summarizes each active worker (uptime, last output timestamp, log path, and the pointer file to read before resuming). `list_instances` shows raw process info.
5. **Checkpoint and stop**: call `checkpoint_instance` before terminating or when tokens (Codex `/status`) run low. The checkpoint file (e.g., `instances/cx-0008/checkpoint.md`) records the next steps so a new worker can resume later. Finish with `terminate_instance` (set `force=true` only if needed).

> **Always run `/status` in the Codex CLI** before approving commands. When the 5‑hour or 1‑week quotas drop, instruct every worker to summarize in their checkpoint, then pause them so nothing is lost when the quota resets.

---

## 5. Repository layout

| Path | Description |
| --- | --- |
| `mcp/codexctl-mcp.py` | MCP server entry point (FastMCP). Handles PTY mirroring, cursor handshake, log streaming, checkpoints, etc. |
| `mcp/dev_smoke_client.py` | Standalone smoke tester that checks `initialize`, `tools/list`, `ping`, and `launch_codex`. |
| `mcp/codexctl-mcp.ps1` | Windows wrapper that starts the MCP server through WSL. |
| `setup/setup_codexhive.sh` / `.ps1` | Helper scripts that add the MCP entry to `~/.codex/config.toml` (WSL or Windows). |
| `agents/roles/*.md` | Role prompts injected into workers (Architect, Coder, Controller, etc.). |
| `agents/pointers/*.md` | “Where to resume” notes surfaced by `status_report` for each role. |
| `agents/workflows/Orchestrator.md` | Step-by-step loop for the orchestrator Codex session. |
| `agent.md`, `AGENTS.md` | Handover notes and operational policies (logging, token monitoring, documentation workflow). |
| `instances/<id>/output.log` | Terminal transcript for each worker (automatically tailed when `mirrorToCmd=true`). |
| `instances/<id>/checkpoint.md` | Persistent summary of progress/next steps, written via `checkpoint_instance`. |

---

## 6. Logs and troubleshooting

- **Server log**: `/mnt/c/codexhive/mcp/codexctl.log` captures MCP requests/responses. Check it whenever the smoke test or Codex CLI reports handshake issues.
- **Latest Codex CLI log**: append tails of `~/.codex/log/codex-tui.log` to `latest-log.txt` whenever a Codex session fails. This keeps the next operator informed.
- **If Codex workers complain about cursor probes**: ensure you are launching them with `usePty=true` (the default) and that `mcp/codexctl-mcp.py` is up to date. The server already auto-responds to `CSI 6n`, so any recurrence usually means PTY creation failed (check OS limits).
- **Smoke test fails at `initialize`**: verify that no orphaned MCP processes are already holding the stdio pipe and that `python3 mcp/dev_smoke_client.py --timeout 30` can reach a fresh server. Restarting the server usually clears it.

---

## 7. Next steps

1. Run `/status` in Codex CLI before every MCP interaction to guard against low token budgets.
2. Use `agents/pointers/*.md` whenever you hand work off to another Codex role—they describe what to read and how to resume safely.
3. When you add new roles or workflows, keep both the role prompt and the pointer document in sync so `status_report` surfaces the right hints.

Happy orchestrating!

