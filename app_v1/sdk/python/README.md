# GP Station v1 Python SDK

Early SDK scaffold for backend clients. The MVP browser path is implemented first; Python WebRTC support is a follow-up.

## Install

```powershell
cd app_v1/sdk/python
poetry install
```

```python
from gpstation_sdk_v1 import GpStationClient

client = GpStationClient("http://127.0.0.1:8100", "demo-client-token")
workers = client.list_workers()
```
