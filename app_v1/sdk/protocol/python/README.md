# GP Station v1 Protocol

Shared constants and Pydantic models for the v1 control, signaling, and DataChannel JSON envelopes.

The runtime still treats messages as JSON objects on the wire. These models keep the MVP contracts explicit and testable.

## Install For Protocol Development

```powershell
cd app_v1/sdk/protocol/python
poetry install
```

Normal server and slave launcher installs do not require this manual step. `server` and `slave` install this package automatically as an editable Poetry path dependency.

## Test

```powershell
poetry run pytest
```
