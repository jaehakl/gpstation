from __future__ import annotations

from dataclasses import dataclass

from gpstation_slave_sdk_v1 import DataChannelMessage, SlaveApp, SlaveContext, run_app


@dataclass
class EchoMemory:
    initialized: bool = False
    request_count: int = 0


app = SlaveApp(memory=EchoMemory())


@app.initialize
def initialize(memory: EchoMemory, context: SlaveContext) -> None:
    memory.initialized = True


@app.handler("echo.request")
def echo(message: DataChannelMessage, memory: EchoMemory, context: SlaveContext) -> DataChannelMessage:
    memory.request_count += 1
    return DataChannelMessage(
        id=message.id,
        type="echo.result",
        payload=message.payload,
        attachments=message.attachments,
    )


if __name__ == "__main__":
    run_app(app)
