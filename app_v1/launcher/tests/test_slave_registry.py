import asyncio
import json

import pytest

from app.control import handle_server_message, launcher_hello_payload
from app.settings import LauncherSettings
from app.slave_registry import SlaveApp, SlaveAppRegistry, load_registry
from app.subprocess_manager import SESSION_LOG_LINE_LIMIT, ManagedWorker, SessionManager, json_line, subprocess_env


def write_manifest(root, folder_name: str, slave_app_id: str, **extra) -> None:
    plugin_dir = root / folder_name
    plugin_dir.mkdir()
    (plugin_dir / "manifest.json").write_text(
        json.dumps(
            {
                "id": slave_app_id,
                "name": slave_app_id.title(),
                "module": "app",
                **extra,
            }
        ),
        encoding="utf-8",
    )


def test_load_registry_from_manifests(tmp_path):
    write_manifest(tmp_path, "echo", "echo")
    write_manifest(tmp_path, "other", "other", startup_timeout_seconds=300)

    registry = load_registry(tmp_path)

    assert registry.ids() == ["echo", "other"]
    assert registry.require("echo").module == "app"
    assert registry.require("echo").project_dir == tmp_path / "echo"
    assert registry.require("echo").startup_timeout_seconds is None
    assert registry.require("other").startup_timeout_seconds == 300


def test_registry_builds_slave_app_metadata(tmp_path):
    write_manifest(tmp_path, "echo", "echo")
    write_manifest(tmp_path, "ai", "ai", startup_timeout_seconds=300)

    registry = load_registry(tmp_path)

    assert registry.metadata() == {
        "slave_apps": {
            "ai": {
                "startup_timeout_seconds": 300,
            }
        }
    }


def test_launcher_hello_payload_includes_slave_app_metadata(tmp_path):
    write_manifest(tmp_path, "ai", "ai", startup_timeout_seconds=300)
    registry = load_registry(tmp_path)

    payload = launcher_hello_payload(LauncherSettings(access_token="test-token"), registry)

    assert payload["slave_app_ids"] == ["ai"]
    assert payload["metadata"] == {
        "slave_apps": {
            "ai": {
                "startup_timeout_seconds": 300,
            }
        }
    }


def test_registry_rejects_duplicate_ids(tmp_path):
    with pytest.raises(ValueError):
        SlaveAppRegistry(
            [
                SlaveApp(id="echo", name="Echo", module="app", project_dir=tmp_path / "echo"),
                SlaveApp(id="echo", name="Echo Again", module="app", project_dir=tmp_path / "echo-again"),
            ]
        )


def test_registry_builds_subprocess_args(tmp_path):
    slave_app = SlaveApp(id="echo", name="Echo", module="app", project_dir=tmp_path / "echo")
    registry = SlaveAppRegistry([slave_app])

    args = registry.subprocess_args("session-1", "echo", 60)

    assert args == [
        str(slave_app.python_executable),
        "-m",
        "app",
        "--session-id",
        "session-1",
        "--ttl-seconds",
        "60",
    ]


def test_registry_builds_worker_subprocess_args(tmp_path):
    slave_app = SlaveApp(id="echo", name="Echo", module="app", project_dir=tmp_path / "echo")
    registry = SlaveAppRegistry([slave_app])

    assert registry.worker_subprocess_args("echo") == [
        str(slave_app.python_executable),
        "-m",
        "app",
        "--worker",
    ]


def test_session_manager_uses_slave_startup_timeout_when_larger(tmp_path):
    registry = SlaveAppRegistry(
        [
            SlaveApp(
                id="ai",
                name="AI",
                module="app",
                project_dir=tmp_path / "ai",
                startup_timeout_seconds=300,
            )
        ]
    )
    manager = SessionManager(
        LauncherSettings(access_token="test-token", session_ready_timeout_seconds=10),
        async_noop,
        registry,
    )

    assert manager.ready_timeout_seconds_for("ai") == 300


def test_session_manager_uses_global_timeout_without_slave_override(tmp_path):
    registry = SlaveAppRegistry([SlaveApp(id="echo", name="Echo", module="app", project_dir=tmp_path / "echo")])
    manager = SessionManager(
        LauncherSettings(access_token="test-token", session_ready_timeout_seconds=10),
        async_noop,
        registry,
    )

    assert manager.ready_timeout_seconds_for("echo") == 10


def test_subprocess_env_includes_rtc_ice_servers_json():
    settings = LauncherSettings(
        access_token="test-token",
        rtc_ice_servers_json='[{"urls":"turn:turn.example.com:3478","username":"u","credential":"p"}]',
        rtc_ice_gather_timeout_seconds="1.5",
        rtc_memory_cache_enabled="false",
    )

    env = subprocess_env(settings)
    assert env["GPSTATION_V1_RTC_ICE_SERVERS_JSON"] == settings.rtc_ice_servers_json
    assert env["GPSTATION_V1_RTC_ICE_GATHER_TIMEOUT_SECONDS"] == "1.5"
    assert env["GPSTATION_V1_RTC_MEMORY_CACHE_ENABLED"] == "false"
    assert env["PYTHONIOENCODING"] == "utf-8"
    assert env["PYTHONUTF8"] == "1"


def test_json_line_encodes_non_ascii_as_utf8():
    data = json_line({"kind": "job.ready", "input": {"prompt": "한글 prompt"}})

    assert data.endswith(b"\n")
    assert "한글".encode("utf-8") in data
    assert json.loads(data.decode("utf-8"))["input"]["prompt"] == "한글 prompt"


def test_registry_rejects_unknown_launch_app(tmp_path):
    registry = SlaveAppRegistry([SlaveApp(id="echo", name="Echo", module="app", project_dir=tmp_path / "echo")])

    with pytest.raises(KeyError):
        registry.subprocess_args("session-1", "missing", 60)


@pytest.mark.asyncio
async def test_start_session_missing_executable_venv_sends_error(tmp_path):
    messages = []

    async def send_control(message):
        messages.append(message)

    project_dir = tmp_path / "echo"
    project_dir.mkdir()
    registry = SlaveAppRegistry([SlaveApp(id="echo", name="Echo", module="app", project_dir=project_dir)])
    manager = SessionManager(LauncherSettings(access_token="test-token"), send_control, registry)

    await manager.start_session("session-1", "echo", 60)

    assert messages[0]["type"] == "session.error"
    assert messages[0]["session_id"] == "session-1"
    assert messages[0]["code"] == "executable_venv_missing"
    assert str(project_dir) in messages[0]["detail"]
    assert "poetry install" in messages[0]["detail"]
    assert manager.sessions == {}


@pytest.mark.asyncio
async def test_start_job_rejects_second_job_while_busy(tmp_path):
    messages = []

    async def send_control(message):
        messages.append(message)

    project_dir = tmp_path / "echo"
    project_dir.mkdir()
    registry = SlaveAppRegistry([SlaveApp(id="echo", name="Echo", module="app", project_dir=project_dir)])
    manager = SessionManager(LauncherSettings(access_token="test-token"), send_control, registry)
    manager.current_job_id = "job-1"

    await manager.start_job(
        job_id="job-2",
        handler_type="echo.request",
        slave_app_id="echo",
        offer={"type": "offer", "sdp": "v=0\r\n"},
    )

    assert messages == [
        {
            "type": "job.error",
            "job_id": "job-2",
            "code": "launcher_busy",
            "detail": "launcher is busy with job job-1",
        }
    ]


@pytest.mark.asyncio
async def test_start_job_rejects_unknown_slave_app():
    messages = []

    async def send_control(message):
        messages.append(message)

    manager = SessionManager(LauncherSettings(access_token="test-token"), send_control, SlaveAppRegistry([]))

    await manager.start_job(
        job_id="job-1",
        handler_type="echo.request",
        slave_app_id="missing",
        offer={"type": "offer", "sdp": "v=0\r\n"},
    )

    assert messages[0]["type"] == "job.error"
    assert messages[0]["code"] == "unknown_slave_app"


@pytest.mark.asyncio
async def test_cancel_job_forwards_cancel_to_worker_without_reset():
    messages = []

    async def send_control(message):
        messages.append(message)

    stdout_task = asyncio.create_task(asyncio.sleep(60))
    stderr_task = asyncio.create_task(asyncio.sleep(60))
    process = FakeWorkerProcess()
    manager = SessionManager(LauncherSettings(access_token="test-token"), send_control, SlaveAppRegistry([]))
    manager.worker = ManagedWorker(
        slave_app_id="echo",
        process=process,
        ready_event=asyncio.Event(),
        stdout_task=stdout_task,
        stderr_task=stderr_task,
        ready=True,
    )
    manager.current_job_id = "job-1"

    try:
        await manager.cancel_job("job-1", "user cancel")
    finally:
        stdout_task.cancel()
        stderr_task.cancel()

    assert process.stdin.messages == [
        {
            "type": "job.cancel",
            "job_id": "job-1",
            "reason": "user cancel",
        }
    ]
    assert manager.worker is not None
    assert manager.current_job_id == "job-1"
    assert manager.worker_status == "cancelling"
    assert messages == []


@pytest.mark.asyncio
async def test_handle_server_message_dispatches_job_controls():
    manager = FakeManager()

    await handle_server_message(
        manager,
        {
            "type": "job.start",
            "job_id": "job-1",
            "handler_type": "echo.request",
            "slave_app_id": "echo",
            "offer": {"type": "offer", "sdp": "v=0\r\n"},
        },
    )
    await handle_server_message(manager, {"type": "job.cancel", "job_id": "job-1", "reason": "user"})
    await handle_server_message(manager, {"type": "worker.reset", "reason": "reset"})

    assert manager.calls == [
        (
            "start_job",
            {
                "job_id": "job-1",
                "handler_type": "echo.request",
                "slave_app_id": "echo",
                "offer": {"type": "offer", "sdp": "v=0\r\n"},
            },
        ),
        ("cancel_job", "job-1", "user"),
        ("reset_worker", "reset"),
    ]


@pytest.mark.asyncio
async def test_record_subprocess_log_sends_control_message_and_stores_buffer():
    messages = []

    async def send_control(message):
        messages.append(message)

    manager = SessionManager(LauncherSettings(access_token="test-token"), send_control, SlaveAppRegistry([]))

    await manager.record_subprocess_log("session-1", "stderr", "loading model")

    logs = manager.get_session_logs("session-1")
    assert logs == [
        {
            "time": messages[0]["time"],
            "stream": "stderr",
            "line": "loading model",
        }
    ]
    assert messages[0]["type"] == "session.log"
    assert messages[0]["session_id"] == "session-1"
    assert messages[0]["stream"] == "stderr"
    assert messages[0]["line"] == "loading model"


@pytest.mark.asyncio
async def test_record_subprocess_log_can_disable_control_forwarding():
    messages = []

    async def send_control(message):
        messages.append(message)

    manager = SessionManager(
        LauncherSettings(access_token="test-token"),
        send_control,
        SlaveAppRegistry([]),
        forward_session_logs=False,
    )

    await manager.record_subprocess_log("session-1", "stderr", "loading model")

    assert manager.get_session_logs("session-1")[0]["line"] == "loading model"
    assert messages == []


@pytest.mark.asyncio
async def test_subprocess_log_buffer_discards_old_lines():
    messages = []

    async def send_control(message):
        messages.append(message)

    manager = SessionManager(LauncherSettings(access_token="test-token"), send_control, SlaveAppRegistry([]))

    for index in range(SESSION_LOG_LINE_LIMIT + 2):
        await manager.record_subprocess_log("session-1", "stderr", f"line-{index}")

    logs = manager.get_session_logs("session-1", limit=SESSION_LOG_LINE_LIMIT)
    assert len(logs) == SESSION_LOG_LINE_LIMIT
    assert logs[0]["line"] == "line-2"
    assert logs[-1]["line"] == f"line-{SESSION_LOG_LINE_LIMIT + 1}"


@pytest.mark.asyncio
async def test_server_error_message_prints_detail(capsys):
    await handle_server_message(
        object(),
        {
            "type": "error",
            "detail": "protocol mismatch",
        },
    )

    captured = capsys.readouterr()
    assert "Server control error: protocol mismatch" in captured.out


async def async_noop(message):
    return None


class FakeManager:
    def __init__(self):
        self.calls = []

    async def start_job(self, **kwargs):
        self.calls.append(("start_job", kwargs))

    async def cancel_job(self, job_id, reason):
        self.calls.append(("cancel_job", job_id, reason))

    async def reset_worker(self, reason):
        self.calls.append(("reset_worker", reason))


class FakeWorkerStdin:
    def __init__(self):
        self.messages = []

    def write(self, data):
        self.messages.append(json.loads(data.decode("utf-8")))

    async def drain(self):
        return None


class FakeWorkerProcess:
    def __init__(self):
        self.stdin = FakeWorkerStdin()
        self.returncode = None
