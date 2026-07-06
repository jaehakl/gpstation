import json

import pytest

from gpstation_worker_v1.slave_registry import SlaveApp, SlaveAppRegistry, load_registry


def write_manifest(root, folder_name: str, slave_app_id: str) -> None:
    plugin_dir = root / folder_name
    plugin_dir.mkdir()
    (plugin_dir / "manifest.json").write_text(
        json.dumps(
            {
                "id": slave_app_id,
                "name": slave_app_id.title(),
                "module": f"slave_plugins.{folder_name}.app",
            }
        ),
        encoding="utf-8",
    )


def test_load_registry_from_manifests(tmp_path):
    write_manifest(tmp_path, "echo", "echo")
    write_manifest(tmp_path, "other", "other")

    registry = load_registry(tmp_path)

    assert registry.ids() == ["echo", "other"]
    assert registry.require("echo").module == "slave_plugins.echo.app"


def test_registry_rejects_duplicate_ids():
    with pytest.raises(ValueError):
        SlaveAppRegistry(
            [
                SlaveApp(id="echo", name="Echo", module="a"),
                SlaveApp(id="echo", name="Echo Again", module="b"),
            ]
        )


def test_registry_builds_subprocess_args():
    registry = SlaveAppRegistry([SlaveApp(id="echo", name="Echo", module="slave_plugins.echo.app")])

    args = registry.subprocess_args("python", "session-1", "echo", 60)

    assert args == [
        "python",
        "-m",
        "slave_plugins.echo.app",
        "--session-id",
        "session-1",
        "--ttl-seconds",
        "60",
    ]


def test_registry_rejects_unknown_launch_app():
    registry = SlaveAppRegistry([SlaveApp(id="echo", name="Echo", module="slave_plugins.echo.app")])

    with pytest.raises(KeyError):
        registry.subprocess_args("python", "session-1", "missing", 60)
