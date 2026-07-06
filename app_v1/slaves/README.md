# GP Station v1 Slave Executables

`slaves/` contains independent slave executable projects:

- `echo/`: built-in echo slave executable. It imports `sdk.slave` and is launched with its own `.venv`.

## Install

```powershell
cd app_v1/slaves/echo
poetry install
```

## Run

```powershell
cd app_v1/launcher
poetry run gpstation-v1-slave-launcher
```

The launcher discovers `../slaves/*/manifest.json`. Each executable must have its own `.venv`; if it is missing, session startup fails with a clear `executable_venv_missing` error.
