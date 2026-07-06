# GP Station v1 Slave Launcher

Python slave launcher process plus per-session slave app subprocess launch.

Built-in slave apps live under `slave_plugins/`. Each plugin manifest points at an executable Python module, and that module imports `gpstation_slave_sdk_v1` to build and run its own app.

## Install

```powershell
cd app_v1/slave
poetry install
```

## Run

```powershell
cd app_v1/slave
poetry run gpstation-v1-slave-launcher
```

Default settings point at `http://127.0.0.1:8100` and use `demo-worker-token`.
