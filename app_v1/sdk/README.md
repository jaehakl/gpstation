# GP Station v1 SDK

The shared Python package contains protocol messages and the slave executable runtime.

```powershell
cd app_v1/sdk
python -m pip install -e ".[slave]"
python -m pytest
```

The async Python master SDK is an independent package alongside the browser TypeScript SDK:

```powershell
cd app_v1/sdk/master/python
poetry install
poetry run pytest
poetry build
```

```python
import asyncio
import os

from gpstation_master import GpStationClient


async def main() -> None:
    async with GpStationClient(
        api_base_url="https://gps.qutat.com",
        token=os.environ["GPSTATION_CLIENT_TOKEN"],
    ) as client:
        result = await client.run_job("ai.llm", {"prompt": "hello"})
        print(result.payload)


asyncio.run(main())
```

See `master/python/README.md` for sessions, events, attachments, prewarm, and cookie authentication.
