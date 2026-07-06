# GP Station v1 Slave Projects

`slave/` contains independent Python projects:

- `launcher/`: connects to the server, advertises available slave executables, and launches per-session subprocesses.
- `executables/echo/`: built-in echo slave executable. It imports `sdk.slave` and is launched with its own `.venv`.

## Install

```powershell
cd app_v1/slave/launcher
poetry install

cd ../executables/echo
poetry install
```

## Run

```powershell
cd app_v1/slave/launcher
poetry run gpstation-v1-slave-launcher
```

The launcher discovers `../executables/*/manifest.json`. Each executable must have its own `.venv`; if it is missing, session startup fails with a clear `executable_venv_missing` error.
