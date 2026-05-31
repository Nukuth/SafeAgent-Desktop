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

## API Error Envelope

```text
1. Added server.app handlers for HTTPException and RequestValidationError.
2. API validation and HTTP errors now return {"error": ErrorEnvelope}.
3. API error details are redacted before returning to clients.
4. Invalid event_type, risk_level, network_mode, status, and malformed request bodies now use validation.failed.
5. Added tests for API error-envelope shape and redaction.
```

Verification:

```text
.\.venv\Scripts\python.exe -m pytest tests\test_server_app.py -q
result: 3 passed, 1 warning

.\.venv\Scripts\python.exe .\scripts\check_error_catalog.py
result: OK error catalog; registered_codes=9

.\.venv\Scripts\python.exe -m pytest -q
result: 121 passed, 2 warnings

.\.venv\Scripts\python.exe .\scripts\doctor.py
result: OK doctor checks; stdlib_tests passed=121 failed=0
```

## Control Plane Client Error Mapping

```text
1. Added raise_for_control_plane_error() in local_worker.client.
2. Worker client now preserves server-returned {"error": ErrorEnvelope}.
3. Server auth.failed remains auth.failed in worker logs.
4. Plain 4xx without an error envelope maps to validation.failed.
5. Plain 5xx/network failures map to upstream.transient.
6. Response text and error details are redacted before entering local errors.
7. Added tests/test_client_errors.py.
```

Verification:

```text
.\.venv\Scripts\python.exe -m pytest tests\test_client_errors.py -q
result: 3 passed

.\.venv\Scripts\python.exe .\scripts\check_error_catalog.py
result: OK error catalog; registered_codes=9

.\.venv\Scripts\python.exe -m pytest -q
result: 124 passed, 2 warnings

.\.venv\Scripts\python.exe .\scripts\doctor.py
result: OK doctor checks; stdlib_tests passed=124 failed=0
```

## Worker Heartbeat Visibility

```text
1. Added TaskStore.latest_heartbeat(device_id).
2. Added remote-readable GET /api/devices/{device_id}/heartbeat.
3. Worker heartbeat writes still require SAFEAGENT_WORKER_TOKEN.
4. Remote heartbeat reads use SAFEAGENT_SERVER_TOKEN.
5. LocalWorker.run_once now posts best-effort poll_started and poll_completed heartbeats.
6. Heartbeat failures write heartbeat_failed locally and do not block polling or task handling.
7. Heartbeat payloads are redacted at the cloud store boundary.
```

Verification:

```text
.\.venv\Scripts\python.exe -m pytest tests\test_worker.py tests\test_server_store.py tests\test_server_app.py -q
result: 11 passed, 1 warning

.\.venv\Scripts\python.exe .\scripts\run_stdlib_tests.py
result: passed=125 failed=0

.\.venv\Scripts\python.exe -m pytest -q
result: 125 passed, 2 warnings

.\.venv\Scripts\python.exe .\scripts\doctor.py
result: OK doctor checks; stdlib_tests passed=125 failed=0
```

## Derived Worker Heartbeat Status

```text
1. Added shared build_device_heartbeat_view().
2. GET /api/devices/{device_id}/heartbeat now returns device_status.
3. device_status can be online, stale, or never_seen.
4. API response includes age_seconds and stale_after_seconds.
5. Default stale threshold is 60 seconds and can be changed with stale_after_seconds query param.
6. Stored heartbeat payload remains raw/redacted; status derivation stays outside TaskStore.
7. Invalid heartbeat timestamps are treated as stale with status_reason=invalid_updated_at.
```

Verification:

```text
.\.venv\Scripts\python.exe -m pytest tests\test_heartbeat_status.py tests\test_server_app.py tests\test_server_store.py -q
result: 11 passed, 1 warning

.\.venv\Scripts\python.exe .\scripts\check_module_boundaries.py
result: OK module boundaries

.\.venv\Scripts\python.exe -m pytest -q
result: 128 passed, 2 warnings

.\.venv\Scripts\python.exe .\scripts\doctor.py
result: OK doctor checks; stdlib_tests passed=128 failed=0
```

## Remote Task Visibility API

```text
1. Added TaskStore.list_tasks() for remote-safe task status views.
2. Added TaskStore.get_task_detail() for redacted task detail, events, approvals, and run_ids.
3. Added GET /api/tasks with optional device_id, status, and limit filters.
4. Added GET /api/tasks/{task_id} for remote task detail.
5. Remote task reads require SAFEAGENT_SERVER_TOKEN.
6. Worker token cannot use remote read routes when tokens are separated.
7. GET /api/tasks does not claim pending tasks or mutate task status.
8. Invalid status filters return validation.failed through the standard API envelope.
```

Verification:

```text
.\.venv\Scripts\python.exe -m pytest tests\test_server_store.py tests\test_server_app.py -q
result: 9 passed, 1 warning

.\.venv\Scripts\python.exe .\scripts\check_error_catalog.py
result: OK error catalog; registered_codes=9

.\.venv\Scripts\python.exe -m pytest -q
result: 129 passed, 2 warnings

.\.venv\Scripts\python.exe .\scripts\doctor.py
result: OK doctor checks; stdlib_tests passed=129 failed=0
```

## Configured Model Providers

```text
1. Added configs/models.json and configs/models.yaml.
2. Model base URLs, model names, system prompts, and api_key_env names now live in config.
3. Real API keys remain environment-only and are not written to config.
4. Worker now builds ProviderRegistry from configs/models.json.
5. local_qwen defaults to qwen-35b-local at http://127.0.0.1:8000/v1.
6. deepseek defaults to deepseek-chat at https://api.deepseek.com/v1 and requires SAFEAGENT_DEEPSEEK_API_KEY.
7. codex stays disabled by default until configs/models.json enables it and SAFEAGENT_CODEX_API_KEY is set.
8. check_config_sync now includes models.yaml/models.json and validates provider config shape.
```

Verification:

```text
.\.venv\Scripts\python.exe .\scripts\check_config_sync.py
result: OK config YAML/JSON sync and registry security contracts

.\.venv\Scripts\python.exe -m pytest tests\test_config_sync.py tests\test_model_router.py tests\test_local_provider.py -q
result: 16 passed

.\.venv\Scripts\python.exe .\scripts\check_error_catalog.py
result: OK error catalog; registered_codes=9

.\.venv\Scripts\python.exe -m pytest tests\test_config_sync.py tests\test_model_router.py tests\test_local_provider.py tests\test_worker.py -q
result: 19 passed

.\.venv\Scripts\python.exe -m pytest -q
result: 131 passed, 2 warnings

.\.venv\Scripts\python.exe .\scripts\doctor.py
result: OK doctor checks; graph_runtime resolved_runtime=langgraph; stdlib_tests passed=131 failed=0
```

## Model Config Status Check

```text
1. Added scripts/check_model_config.py.
2. The script reports provider enabled/ready/model/base_url/api_key_env/has_api_key/api_key_source/reason.
3. The script does not print real API key values.
4. Doctor now runs model_config as a separate check.
5. DeepSeek without SAFEAGENT_DEEPSEEK_API_KEY reports ready=False with reason=missing SAFEAGENT_DEEPSEEK_API_KEY.
6. Codex remains ready=False while disabled in configs/models.json.
```

Verification:

```text
.\.venv\Scripts\python.exe .\scripts\check_model_config.py
result: OK model config; deepseek ready=False reason=missing SAFEAGENT_DEEPSEEK_API_KEY

.\.venv\Scripts\python.exe -m pytest tests\test_model_router.py tests\test_doctor.py -q
result: 14 passed

.\.venv\Scripts\python.exe .\scripts\check_error_catalog.py
result: OK error catalog; registered_codes=9

.\.venv\Scripts\python.exe .\scripts\check_config_sync.py
result: OK config YAML/JSON sync and registry security contracts

.\.venv\Scripts\python.exe -m pytest -q
result: 133 passed, 2 warnings

.\.venv\Scripts\python.exe .\scripts\doctor.py
result: OK doctor checks; model_config passed; graph_runtime resolved_runtime=langgraph; stdlib_tests passed=133 failed=0
```
