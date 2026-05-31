from pathlib import Path

from safeagent.shared.error_catalog import (
    ERROR_CATALOG,
    find_error_codes_in_source,
    find_unregistered_error_codes,
    is_registered_error_code,
)


def test_error_catalog_contains_current_error_codes():
    expected = {
        "auth.failed",
        "dependency.missing",
        "model.invocation_failed",
        "policy.denied",
        "provider.not_configured",
        "upstream.transient",
        "validation.failed",
    }
    assert expected.issubset(ERROR_CATALOG)
    assert all(ERROR_CATALOG[code].operator_hint for code in expected)


def test_current_source_has_no_unregistered_error_codes():
    assert find_unregistered_error_codes(Path("src")) == {}


def test_error_catalog_finds_unknown_code(tmp_path):
    source = tmp_path / "sample.py"
    source.write_text(
        'from safeagent.shared.errors import SafeAgentError\n'
        'err = SafeAgentError("unknown.code", "test", "bad")\n',
        encoding="utf-8",
    )
    discovered = find_error_codes_in_source(tmp_path)
    assert discovered["unknown.code"]
    unknown = find_unregistered_error_codes(tmp_path)
    assert "unknown.code" in unknown
    assert is_registered_error_code("unknown.code") is False

