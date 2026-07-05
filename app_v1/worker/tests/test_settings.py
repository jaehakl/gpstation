from gpstation_worker_v1.settings import WorkerSettings


def test_control_websocket_url_uses_v1_path():
    settings = WorkerSettings(api_url="http://127.0.0.1:8100/")

    assert settings.control_websocket_url == "ws://127.0.0.1:8100/v1/workers/control"


def test_https_api_url_uses_wss():
    settings = WorkerSettings(api_url="https://gps.example.com/base")

    assert settings.control_websocket_url == "wss://gps.example.com/base/v1/workers/control"
