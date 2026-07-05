from __future__ import annotations

import uvicorn

from gpstation_server.settings import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "gpstation_server.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )


if __name__ == "__main__":
    main()
