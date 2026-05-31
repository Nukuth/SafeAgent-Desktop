# SafeAgent Error Codes

SafeAgent uses structured errors so every failure can be traced to a module,
code, message, severity, retriable flag, and details payload.

The source of truth is:

```text
src/safeagent/shared/error_catalog.py
```

The health check is:

```powershell
.\.venv\Scripts\python.exe .\scripts\check_error_catalog.py
```

`doctor.py` runs this check automatically.

## Current Codes

```text
auth.failed
dependency.missing
model.invocation_failed
policy.denied
provider.not_configured
upstream.transient
validation.failed
worker.report_failed
worker.task_failed
```

`validation.failed` is also used for FastAPI request-body, query-parameter, and
HTTP validation failures. API callers should always read the top-level
`error.code`, `error.module`, and `error.details` fields instead of relying on
FastAPI's default `detail` shape.

## Rules

```text
1. New error codes must be added to ERROR_CATALOG before use.
2. Error codes should use category.reason format.
3. Error details must be safe to log after redaction.
4. Provider/API key values must never appear in details.
5. Transient errors should set retriable=true only when an automatic retry is safe.
6. Policy and approval failures are not retriable by blind retry.
7. Worker task isolation failures must not stop unrelated tasks in the same poll batch.
```

## Adding A New Error

1. Add a new `ErrorCodeSpec` in `src/safeagent/shared/error_catalog.py`.
2. Use the code in a `SafeAgentError`, `ErrorEnvelope`, or node error object.
3. Add or update tests for the expected failure.
4. Run:

```powershell
.\.venv\Scripts\python.exe .\scripts\check_error_catalog.py
.\.venv\Scripts\python.exe .\scripts\doctor.py --quick
```

If the code is missing from the catalog, doctor fails with:

```text
FAIL unregistered error codes
```

This is intentional. It prevents unclear module-local errors from leaking into
the runtime or cloud logs.
