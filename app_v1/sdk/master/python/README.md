# GP Station v1 Master Python SDK

Early master SDK scaffold for backend clients. Python WebRTC master support is a follow-up.

## Install

```powershell
cd app_v1/sdk/master/python
poetry install
```

```python
from gpstation_master_sdk_v1 import GpStationClient

client = GpStationClient("http://127.0.0.1:8100", "demo-client-token")
workers = client.list_workers()
session = client.create_session(workers[0].id, slave_app_id="echo")
```
