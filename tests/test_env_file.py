import os
from pathlib import Path

from safeagent.local_worker.env_file import build_effective_env, load_env_file
from safeagent.local_worker.settings import WorkerSettings
from safeagent.server.settings import ServerSettings
from safeagent.shared.errors import ValidationError


def test_load_env_file_parses_simple_key_value_pairs(tmp_path):
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "# local secrets",
                "SAFEAGENT_DEEPSEEK_API_KEY=secret-value",
                'SAFEAGENT_DEVICE_ID="pc-from-file"',
                "SAFEAGENT_EMERGENCY_LOCAL_MODEL=true",
            ]
        ),
        encoding="utf-8",
    )

    values = load_env_file(env_file)

    assert values["SAFEAGENT_DEEPSEEK_API_KEY"] == "secret-value"
    assert values["SAFEAGENT_DEVICE_ID"] == "pc-from-file"
    assert values["SAFEAGENT_EMERGENCY_LOCAL_MODEL"] == "true"


def test_load_env_file_accepts_utf8_bom_from_powershell_set_content(tmp_path):
    env_file = tmp_path / ".env.local"
    env_file.write_text("\ufeff# local secrets\nSAFEAGENT_DEEPSEEK_API_KEY=secret-value", encoding="utf-8")

    values = load_env_file(env_file)

    assert values["SAFEAGENT_DEEPSEEK_API_KEY"] == "secret-value"


def test_build_effective_env_lets_process_env_override_file_values(tmp_path):
    env_file = tmp_path / ".env.local"
    env_file.write_text("SAFEAGENT_DEVICE_ID=pc-from-file\nSAFEAGENT_DEEPSEEK_API_KEY=file-key", encoding="utf-8")

    effective = build_effective_env(
        base_env={"SAFEAGENT_DEVICE_ID": "pc-from-process"},
        env_file=env_file,
    )

    assert effective["SAFEAGENT_DEVICE_ID"] == "pc-from-process"
    assert effective["SAFEAGENT_DEEPSEEK_API_KEY"] == "file-key"


def test_load_env_file_reports_invalid_lines(tmp_path):
    env_file = tmp_path / ".env.local"
    env_file.write_text("not a key value line", encoding="utf-8")

    try:
        load_env_file(env_file)
    except ValidationError as exc:
        assert exc.envelope.code == "validation.failed"
        assert exc.envelope.module == "shared.env_file"
        assert exc.envelope.details["line_number"] == 1
    else:
        raise AssertionError("expected ValidationError")


def test_worker_settings_reads_env_local_without_committing_secrets(tmp_path):
    workspace = tmp_path
    env_file = workspace / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "SAFEAGENT_WORKER_TOKEN=file-worker-token",
                "SAFEAGENT_DEVICE_ID=file-pc",
                "SAFEAGENT_DEEPSEEK_API_KEY=file-deepseek-key",
            ]
        ),
        encoding="utf-8",
    )
    keys = [
        "SAFEAGENT_ENV_FILE",
        "SAFEAGENT_WORKSPACE_ROOT",
        "SAFEAGENT_WORKER_TOKEN",
        "SAFEAGENT_SERVER_TOKEN",
        "SAFEAGENT_DEVICE_ID",
        "SAFEAGENT_DEEPSEEK_API_KEY",
    ]
    original = {key: os.environ.get(key) for key in keys}
    try:
        for key in keys:
            os.environ.pop(key, None)
        os.environ["SAFEAGENT_ENV_FILE"] = str(env_file)
        os.environ["SAFEAGENT_WORKSPACE_ROOT"] = str(workspace)
        settings = WorkerSettings.from_env()
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    assert settings.token == "file-worker-token"
    assert settings.device_id == "file-pc"
    assert settings.provider_env is not None
    assert settings.provider_env["SAFEAGENT_DEEPSEEK_API_KEY"] == "file-deepseek-key"


def test_server_settings_reads_env_local_for_control_console_tokens(tmp_path):
    workspace = tmp_path
    env_file = workspace / ".env.local"
    db_path = workspace / "server.sqlite3"
    env_file.write_text(
        "\n".join(
            [
                "SAFEAGENT_SERVER_TOKEN=file-server-token",
                "SAFEAGENT_WORKER_TOKEN=file-worker-token",
                f"SAFEAGENT_DB_PATH={db_path}",
            ]
        ),
        encoding="utf-8",
    )
    keys = [
        "SAFEAGENT_ENV_FILE",
        "SAFEAGENT_WORKSPACE_ROOT",
        "SAFEAGENT_WORKER_TOKEN",
        "SAFEAGENT_SERVER_TOKEN",
        "SAFEAGENT_DB_PATH",
    ]
    original = {key: os.environ.get(key) for key in keys}
    try:
        for key in keys:
            os.environ.pop(key, None)
        os.environ["SAFEAGENT_ENV_FILE"] = str(env_file)
        os.environ["SAFEAGENT_WORKSPACE_ROOT"] = str(workspace)
        settings = ServerSettings.from_env()
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    assert settings.token == "file-server-token"
    assert settings.worker_token == "file-worker-token"
    assert settings.db_path == db_path
