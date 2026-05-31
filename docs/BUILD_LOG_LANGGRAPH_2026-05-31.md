# 2026-05-31 LangGraph Install And Adapter Log

## Goal

```text
1. Install the dependencies required for the LangGraph project path.
2. Avoid wasting traffic on incompatible MSYS Python builds.
3. Add a LangGraph state contract and optional adapter layer.
4. Verify the adapter does not weaken existing safety gates.
```

## Environment Work

```text
1. The default python was C:\msys64\ucrt64\bin\python.exe.
2. Installing LangGraph with that Python failed while building uuid-utils / ormsgpack.
3. The failure was caused by the mingw platform missing compatible binary wheels.
4. Chocolatey python312 install failed because the shell was not elevated.
5. Downloaded the official Python 3.12.6 Windows installer to E:\agents\downloads.
6. Installed project-local Python to E:\agents\.runtime\Python312.
7. Recreated E:\agents\.venv with that Python.
8. Installed project and dev dependencies successfully.
```

## Code Changes

```text
1. pyproject.toml now includes langgraph>=0.2.0,<1.0.0.
2. Added DependencyMissingError with code dependency.missing.
3. Added src/safeagent/local_worker/langgraph_state.py.
4. Added src/safeagent/local_worker/langgraph_adapter.py.
5. Added tests/test_langgraph_adapter.py.
6. Added .gitignore for .venv, .runtime, downloads, logs, state, and models.
```

## Safety Notes

```text
1. The LangGraph adapter is optional and does not replace LocalOrchestrator yet.
2. LangGraph nodes still use injected handlers and do not execute shell directly.
3. The adapter rechecks executor approval-gate safety before compiling.
4. Dynamic routing uses Command(goto=...) to avoid duplicate static-edge execution.
5. PolicyEngine, approval validation, plan_hash, redaction, and Executor remain separate boundaries.
```

## Verification

```text
.\.venv\Scripts\python.exe -m pytest tests\test_langgraph_adapter.py -q
result: 5 passed

.\.venv\Scripts\python.exe -m pytest -q
result: 102 passed

.\.venv\Scripts\python.exe .\scripts\doctor.py
result: OK doctor checks; stdlib_tests passed=102 failed=0
```

## Runtime Follow-Up

```text
1. Added src/safeagent/local_worker/graph_runtime.py.
2. Added SAFEAGENT_GRAPH_RUNTIME with values auto / langgraph / stdlib.
3. auto prefers LangGraph when installed.
4. stdlib remains fallback/comparison only.
5. LocalOrchestrator now records graph_runtime in plan input and graph events.
6. Added tests/test_graph_runtime.py.
```

Verification:

```text
.\.venv\Scripts\python.exe -m pytest tests\test_langgraph_adapter.py tests\test_graph_runtime.py tests\test_orchestrator.py -q
result: 20 passed
```

Full verification after enabling auto runtime:

```text
.\.venv\Scripts\python.exe -m pytest -q
result: 107 passed

.\.venv\Scripts\python.exe .\scripts\doctor.py
result: OK doctor checks; stdlib_tests passed=107 failed=0
```

## Graph Runtime Doctor Check

```text
1. Added scripts/check_graph_runtime.py.
2. doctor.py now runs graph_runtime before local_smoke.
3. check_graph_runtime validates SAFEAGENT_GRAPH_RUNTIME and confirms the low-risk safe_shell path.
4. .env.example now includes SAFEAGENT_GRAPH_RUNTIME=auto.
5. doctor output filters the known LangGraph allowed_objects deprecation warning.
```

Verification:

```text
.\.venv\Scripts\python.exe -m pytest -q
result: 110 passed

.\.venv\Scripts\python.exe .\scripts\doctor.py
result: OK doctor checks; graph_runtime resolved_runtime=langgraph; stdlib_tests passed=110 failed=0
```

## Error Catalog Doctor Check

```text
1. Added src/safeagent/shared/error_catalog.py.
2. Added scripts/check_error_catalog.py.
3. doctor.py now runs error_catalog before graph_runtime.
4. Added docs/ERRORS.md.
5. README.md now links to the error-code catalog.
```

Registered codes:

```text
auth.failed
dependency.missing
model.invocation_failed
policy.denied
provider.not_configured
upstream.transient
validation.failed
```

Verification:

```text
.\.venv\Scripts\python.exe .\scripts\check_error_catalog.py
result: OK error catalog; registered_codes=7

.\.venv\Scripts\python.exe -m pytest tests\test_error_catalog.py tests\test_doctor.py -q
result: 7 passed

.\.venv\Scripts\python.exe .\scripts\doctor.py --quick
result: OK doctor checks; error_catalog passed
```

Full verification:

```text
.\.venv\Scripts\python.exe -m pytest -q
result: 114 passed, 1 warning

.\.venv\Scripts\python.exe .\scripts\doctor.py
result: OK doctor checks; error_catalog passed; graph_runtime resolved_runtime=langgraph; stdlib_tests passed=114 failed=0
```

## Worker Task Isolation

```text
1. Initialized the workspace as a git repository and committed the SafeAgent baseline.
2. Added .gitattributes to keep tracked text files LF-stable.
3. Ignored generated *.egg-info package metadata.
4. LocalWorker.run_once now isolates each pending task.
5. A task failure writes task_failed to the local audit log.
6. A task failure tries to post a run_failed event and update that task to failed.
7. Failure reporting is best effort and cannot block later tasks in the same poll batch.
8. Added worker.task_failed and worker.report_failed to the registered error catalog.
9. Added tests/test_worker.py.
10. Updated troubleshooting guidance for task_failed and task_failure_report_failed.
```

Verification:

```text
.\.venv\Scripts\python.exe -m pytest tests\test_worker.py -q
result: 2 passed

.\.venv\Scripts\python.exe .\scripts\check_error_catalog.py
result: OK error catalog; registered_codes=9

.\.venv\Scripts\python.exe -m pytest -q
result: 116 passed, 1 warning

.\.venv\Scripts\python.exe .\scripts\doctor.py --quick
result: OK doctor checks; error_catalog registered_codes=9; graph_runtime resolved_runtime=langgraph

.\.venv\Scripts\python.exe .\scripts\doctor.py
result: OK doctor checks; stdlib_tests passed=116 failed=0
```

## Cloud Store Redaction Boundary

```text
1. Added TaskStore-level redaction before SQLite persistence.
2. Redacts remote task content before claim_pending returns it to the worker.
3. Redacts event summaries/details before storing payload_json.
4. Redacts approval payloads before storing payload_json.
5. Redacts heartbeat payloads before storing payload_json.
6. Redacts SafeAgentError API responses at the FastAPI handler boundary.
7. Preserves audit identifiers such as task_id, run_id, approval_id, plan_hash, and command_hash.
8. Added tests proving secrets do not appear in persisted cloud SQLite payloads.
```

Verification:

```text
.\.venv\Scripts\python.exe -m pytest tests\test_shared.py tests\test_server_store.py -q
result: 11 passed

.\.venv\Scripts\python.exe -m pytest -q
result: 118 passed, 1 warning

.\.venv\Scripts\python.exe .\scripts\doctor.py
result: OK doctor checks; stdlib_tests passed=118 failed=0
```

## Worker-Only API Boundary

```text
1. Added SAFEAGENT_WORKER_TOKEN to ServerSettings.
2. Server falls back to SAFEAGENT_SERVER_TOKEN only when SAFEAGENT_WORKER_TOKEN is unset.
3. Worker-only routes now require the worker token:
   - GET /api/tasks/pending
   - POST /api/tasks/{task_id}/heartbeat
   - POST /api/tasks/{task_id}/events
   - GET /api/tasks/{task_id}/approval/latest
   - POST /api/tasks/{task_id}/status
4. Remote UI routes continue to use SAFEAGENT_SERVER_TOKEN and remote permission headers.
5. Fixed FastAPI body parsing by removing postponed annotations from server.app.
6. Fixed event payload parsing by converting event_type, risk_level, and network_mode strings to enums.
7. Added tests/test_server_app.py.
```

Verification:

```text
.\.venv\Scripts\python.exe -m pytest tests\test_server_app.py -q
result: 2 passed, 1 warning

.\.venv\Scripts\python.exe -m pytest -q
result: 120 passed, 2 warnings

.\.venv\Scripts\python.exe .\scripts\run_stdlib_tests.py
result: passed=120 failed=0

.\.venv\Scripts\python.exe .\scripts\doctor.py
result: OK doctor checks; stdlib_tests passed=120 failed=0
```
