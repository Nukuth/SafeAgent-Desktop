# SafeAgent Workspace

SafeAgent Workspace is the MVP foundation for a secure local multi-agent system.

It uses a remote control plane plus a local polling worker:

```text
Remote browser
→ Aliyun/Tencent cloud server control plane
→ task queue and redacted events
→ local E:\agents worker polls tasks
→ local policy review, approval gates, execution boundary
→ redacted event upload
```

The cloud server must not store DeepSeek/Codex API keys and must not execute local commands. The local worker owns model calls, risk checks, approvals, execution, and full audit logs.

## Priority Order

The project priority is fixed:

```text
P0 Safety boundaries and clear error handling
P1 LangGraph core orchestration
P2 End-to-end MVP task loop
P3 Model providers: DeepSeek, Codex review, local Qwen 35B/32B fallback
P4 Controlled local computer operations
P5 Remote control UI and cloud deployment
P6 Knowledge base, memory, and long-term extensions
```

Safety is always above automation speed, UI polish, model output quality, and LangGraph migration speed. LangGraph is the long-term orchestration core, but it must preserve the local policy engine, approval gates, plan hash checks, audit logs, and module boundaries.

See `docs/ROADMAP_STATUS.md` for the current alignment status and staged roadmap.
See `docs/ERRORS.md` for the structured error-code catalog.
See `docs/TROUBLESHOOTING_LANGGRAPH_INSTALL.md` if LangGraph installation fails.

Graph runtime defaults to `auto`, which uses LangGraph when installed and keeps
the standard-library runner only as a fallback/comparison path:

```powershell
$env:SAFEAGENT_GRAPH_RUNTIME="auto"       # default, prefer LangGraph
$env:SAFEAGENT_GRAPH_RUNTIME="langgraph"  # require LangGraph
$env:SAFEAGENT_GRAPH_RUNTIME="stdlib"     # fallback/comparison only
```

## Current MVP

This first scaffold focuses on stable boundaries:

```text
src/safeagent/shared      shared schemas, errors, auth, audit events
src/safeagent/server      cloud control plane API and SQLite task store
src/safeagent/local_worker local policy engine, orchestrator, polling worker
configs                  agent and profile registry drafts
tests                    standard-library tests for boundaries and policies
```

## Install

```powershell
cd E:\agents
.\.runtime\Python312\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .[dev]
```

This workspace uses a project-local Windows Python at
`E:\agents\.runtime\Python312` because the system `C:\msys64` Python cannot
install LangGraph binary dependencies reliably on Windows. Do not add this
runtime to the system `PATH`; call it through the explicit path above.

## Run Server

```powershell
$env:SAFEAGENT_SERVER_TOKEN="change-me"
$env:SAFEAGENT_DB_PATH="E:\agents\state\server.sqlite3"
uvicorn safeagent.server.app:create_app --factory --host 127.0.0.1 --port 8080
```

## Run Worker

```powershell
$env:SAFEAGENT_CONTROL_URL="http://127.0.0.1:8080"
$env:SAFEAGENT_WORKER_TOKEN="change-me"
$env:SAFEAGENT_DEVICE_ID="local-pc-1"
python -m safeagent.local_worker.worker
```

## Safety Defaults

- Public IDs are UUIDs, not incrementing IDs.
- All API responses use the same structured error envelope.
- Remote tasks are requests, not commands.
- The worker re-evaluates every task locally.
- External writes, deletes, installs, and downloads are gated by policy.
- Downloads are only allowed under `E:\agents\downloads`.
- Full logs stay local under `E:\agents\logs`; cloud events are redacted summaries.
- The server store redacts task content, event payloads, approvals, and heartbeats before SQLite persistence.
