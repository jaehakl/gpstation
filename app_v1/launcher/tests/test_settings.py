from pathlib import Path

from app.settings import LauncherSettings


def test_launcher_settings_env_file_is_launcher_app_root_dotenv():
    assert Path(LauncherSettings.model_config["env_file"]) == Path(__file__).resolve().parents[1] / ".env"
    assert LauncherSettings.model_config["env_file_encoding"] == "utf-8"


def test_launcher_settings_reads_prefixed_values_from_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "GPSTATION_V1_API_URL=http://127.0.0.1:8199/base/",
                "GPSTATION_V1_ACCESS_TOKEN=test-launcher-token",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("GPSTATION_V1_API_URL", raising=False)
    monkeypatch.delenv("GPSTATION_V1_ACCESS_TOKEN", raising=False)
    monkeypatch.setitem(LauncherSettings.model_config, "env_file", str(env_file))

    settings = LauncherSettings()

    assert settings.api_url == "http://127.0.0.1:8199/base"
    assert settings.access_token == "test-launcher-token"


def test_control_websocket_url_uses_v1_path():
    settings = LauncherSettings(api_url="http://127.0.0.1:8100/")

    assert settings.control_websocket_url == "ws://127.0.0.1:8100/v1/launchers/control"


def test_https_api_url_uses_wss():
    settings = LauncherSettings(api_url="https://gps.example.com/base")

    assert settings.control_websocket_url == "wss://gps.example.com/base/v1/launchers/control"
