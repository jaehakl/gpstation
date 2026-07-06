from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SlaveApp:
    id: str
    name: str
    module: str


class SlaveAppRegistry:
    def __init__(self, apps: list[SlaveApp]) -> None:
        self.apps = {app.id: app for app in apps}
        if len(self.apps) != len(apps):
            raise ValueError("duplicate slave app id")

    def ids(self) -> list[str]:
        return sorted(self.apps)

    def get(self, slave_app_id: str) -> SlaveApp | None:
        return self.apps.get(slave_app_id)

    def require(self, slave_app_id: str) -> SlaveApp:
        app = self.get(slave_app_id)
        if app is None:
            raise KeyError(slave_app_id)
        return app

    def subprocess_args(self, python_executable: str, session_id: str, slave_app_id: str, ttl_seconds: int) -> list[str]:
        app = self.require(slave_app_id)
        return [
            python_executable,
            "-m",
            app.module,
            "--session-id",
            session_id,
            "--ttl-seconds",
            str(ttl_seconds),
        ]


def load_default_registry() -> SlaveAppRegistry:
    return load_registry(default_plugins_dir())


def load_registry(plugins_dir: Path) -> SlaveAppRegistry:
    apps: list[SlaveApp] = []
    for manifest_path in sorted(plugins_dir.glob("*/manifest.json")):
        apps.append(load_manifest(manifest_path))
    return SlaveAppRegistry(apps)


def load_manifest(manifest_path: Path) -> SlaveApp:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return SlaveApp(
        id=str(payload["id"]),
        name=str(payload.get("name") or payload["id"]),
        module=str(payload["module"]),
    )


def default_plugins_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "slave_plugins"
