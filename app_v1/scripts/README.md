# GP Station v1 Scripts

Local helpers for the MVP.

- `smoke_rest.py`: checks server health and authenticated worker listing.
- `smoke_aiortc_e2e.py`: creates an `echo` slave app session and verifies a generic WebRTC handler call with JSON plus a tiny binary attachment.
- `start_demo.bat`: opens server, worker, and web client command windows.

## Install

```powershell
cd app_v1/scripts
poetry install
```

## Run

```powershell
cd app_v1/scripts
poetry run python smoke_rest.py http://127.0.0.1:8100 demo-client-token
poetry run python smoke_aiortc_e2e.py http://127.0.0.1:8100 demo-client-token
```
