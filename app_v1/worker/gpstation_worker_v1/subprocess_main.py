from __future__ import annotations

from gpstation_slave_sdk_v1.runtime import emit


def main() -> None:
    emit(
        {
            "type": "error",
            "code": "deprecated_launcher",
            "detail": "slave apps are launched directly from the manifest module",
        }
    )


if __name__ == "__main__":
    main()
