from pathlib import Path

from app.settings import Settings


def test_settings_env_file_is_server_app_root_dotenv():
    assert Path(Settings.model_config["env_file"]) == Path(__file__).resolve().parents[1] / ".env"
    assert Settings.model_config["env_file_encoding"] == "utf-8"


def test_settings_reads_prefixed_values_from_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "GPSTATION_V1_PORT=8123",
                "GPSTATION_V1_PUBLIC_BASE_URL=http://example.test/base/",
                (
                    "GPSTATION_V1_TOKENS="
                    '\'{"client-token":{"user_id":"user-1","scopes":["client"]}}\''
                ),
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("GPSTATION_V1_PORT", raising=False)
    monkeypatch.delenv("GPSTATION_V1_PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("GPSTATION_V1_TOKENS", raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", str(env_file))

    settings = Settings()

    assert settings.port == 8123
    assert settings.public_base_url == "http://example.test/base"
    assert settings.tokens["client-token"].user_id == "user-1"
    assert settings.tokens["client-token"].scopes == ["client"]
