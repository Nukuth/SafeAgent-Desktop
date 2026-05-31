from safeagent.local_worker.doctor import (
    DoctorCheckResult,
    doctor_exit_code,
    filter_known_stderr,
    format_doctor_report,
)


def test_doctor_report_passes_when_all_checks_pass():
    results = [
        DoctorCheckResult(name="config", return_code=0, stdout="OK"),
        DoctorCheckResult(name="smoke", return_code=0),
    ]
    report = format_doctor_report(results)
    assert doctor_exit_code(results) == 0
    assert "PASS config" in report
    assert "OK doctor checks" in report


def test_doctor_report_fails_when_any_check_fails():
    results = [
        DoctorCheckResult(name="config", return_code=0),
        DoctorCheckResult(name="smoke", return_code=1, stderr="bad"),
    ]
    report = format_doctor_report(results)
    assert doctor_exit_code(results) == 1
    assert "FAIL smoke" in report
    assert "stderr:" in report
    assert "FAIL doctor checks" in report


def test_doctor_filters_known_langgraph_warning():
    stderr = "\n".join(
        [
            "E:\\agents\\.venv\\Lib\\site-packages\\langgraph\\cache\\base\\__init__.py:8: LangChainPendingDeprecationWarning: The default value of `allowed_objects` will change in a future version.",
            "  from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer",
            "real error",
        ]
    )
    assert filter_known_stderr(stderr) == "real error"


def test_doctor_report_includes_error_catalog_check_name():
    results = [DoctorCheckResult(name="error_catalog", return_code=0, stdout="OK error catalog")]
    report = format_doctor_report(results)
    assert "PASS error_catalog" in report
    assert "OK error catalog" in report
