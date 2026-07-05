from __future__ import annotations

import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> int:
    base_url = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8100").rstrip("/")
    token = sys.argv[2] if len(sys.argv) > 2 else "demo-client-token"
    print(fetch_json(f"{base_url}/health"))
    print(fetch_json(f"{base_url}/v1/workers", token))
    return 0


def fetch_json(url: str, token: str | None = None) -> str:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=5) as response:
            return json.dumps(json.load(response), ensure_ascii=False, indent=2)
    except (HTTPError, URLError) as exc:
        raise SystemExit(f"request failed: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
