# GP Station v1 Slave Python SDK

Authoring SDK for Python slave subprocess apps.

Plugin programs import this SDK, create a `SlaveApp`, register initialize and message handlers, then call `run_app(app)`.

```python
from gpstation_slave_sdk_v1 import DataChannelMessage, SlaveApp, run_app

app = SlaveApp(memory={})

@app.initialize
def initialize(memory, context):
    memory["ready_for"] = context.session_id

@app.handler("echo.request")
def echo(message, memory, context):
    return DataChannelMessage(
        id=message.id,
        type="echo.result",
        payload=message.payload,
        attachments=message.attachments,
    )

if __name__ == "__main__":
    run_app(app)
```

The SDK owns WebRTC signaling over stdin/stdout JSON-lines, routes `gpstation.v1` DataChannel calls to the registered handlers, and assembles/sends binary attachments as Python `bytes`.
