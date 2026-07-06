import json

import pytest

from app.settings import LauncherSettings
from app.slave_registry import SlaveApp, SlaveAppRegistry, load_registry
from app.subprocess_manager import SessionManager


def write_manifest(root, folder_name: str, slave_app_id: str) -> None:
    plugin_dir = root / folder_name
    plugin_dir.mkdir()
    (plugin_dir / "manifest.json").write_text(
        json.dumps(
            {
                "id": slave_app_id,
                "name": slave_app_id.title(),
                "module": "app",
            }
        ),
        encoding="utf-8",
    )


def test_load_registry_from_manifests(tmp_path):
    write_manifest(tmp_path, "echo", "echo")
    write_manifest(tmp_path, "other", "other")

    registry = load_registry(tmp_path)

    assert registry.ids() == ["echo", "other"]
    assert registry.require("echo").module == "app"
    assert registry.require("echo").project_dir == tmp_path / "echo"


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
    manager = SessionManager(LauncherSettings(), send_control, registry)

    await manager.start_session("session-1", "echo", 60)

    assert messages[0]["type"] == "session.error"
    assert messages[0]["session_id"] == "session-1"
    assert messages[0]["code"] == "executable_venv_missing"
    assert str(project_dir) in messages[0]["detail"]
    assert "poetry install" in messages[0]["detail"]
    assert manager.sessions == {}
