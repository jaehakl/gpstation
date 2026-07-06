from app.settings import LauncherSettings


def test_control_websocket_url_uses_v1_path():
    settings = LauncherSettings(api_url="http://127.0.0.1:8100/")

    assert settings.control_websocket_url == "ws://127.0.0.1:8100/v1/launchers/control"


def test_https_api_url_uses_wss():
    settings = LauncherSettings(api_url="https://gps.example.com/base")

    assert settings.control_websocket_url == "wss://gps.example.com/base/v1/launchers/control"
