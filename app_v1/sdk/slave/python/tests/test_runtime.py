from __future__ import annotations

import json

import pytest

from gpstation_protocol.constants import DATA_CHANNEL_LABEL
from gpstation_slave_sdk_v1 import DataChannelAttachment, DataChannelMessage, SlaveApp, SlaveContext
from gpstation_slave_sdk_v1.runtime import CHUNK_SIZE, decode_binary_frame, encode_binary_frame, handle_datachannel_message


class DummyChannel:
    label = DATA_CHANNEL_LABEL

    def __init__(self) -> None:
        self.sent: list[str | bytes] = []

    def send(self, message: str | bytes) -> None:
        self.sent.append(message)


def test_handler_decorators_preserve_registration_order():
    app = SlaveApp(memory={})

    @app.handler("first")
    def first(message, memory, context):
        return None

    @app.handler("second")
    def second(message, memory, context):
        return None

    assert [handler.message_type for handler in app.handlers] == ["first", "second"]


@pytest.mark.asyncio
async def test_initialize_hook_runs_with_memory_and_context():
    memory = {"initialized_for": None}
    app = SlaveApp(memory=memory)
    context = SlaveContext(session_id="session-1", ttl_seconds=60)

    @app.initialize
    async def initialize(memory, context):
        memory["initialized_for"] = context.session_id

    await app.run_initialize(context)

    assert memory["initialized_for"] == "session-1"


@pytest.mark.asyncio
async def test_json_only_call_dispatches_response_frame():
    app = SlaveApp(memory={})
    channel = DummyChannel()

    @app.handler("sync.request")
    def sync_handler(message, memory, context):
        return DataChannelMessage(id=message.id, type="sync.result", payload=message.payload)

    await handle_datachannel_message(
        channel,
        json.dumps(
            {
                "kind": "call.request",
                "id": "sync-1",
                "type": "sync.request",
                "payload": {"value": 1},
                "attachments": [],
            }
        ),
        app,
        SlaveContext(session_id="session-1", ttl_seconds=60),
    )

    response = json.loads(channel.sent[0])
    assert response == {
        "kind": "call.response",
        "id": "sync-1",
        "type": "sync.result",
        "payload": {"value": 1},
        "attachments": [],
    }


@pytest.mark.asyncio
async def test_call_with_attachment_assembles_bytes_and_sends_response_chunks():
    app = SlaveApp(memory={})
    channel = DummyChannel()
    pending_calls = {}

    @app.handler("file.request")
    async def file_handler(message, memory, context):
        assert message.attachments[0].data == b"hello file"
        return DataChannelMessage(
            id=message.id,
            type="file.result",
            payload={"count": len(message.attachments)},
            attachments=[
                DataChannelAttachment(
                    id="out-1",
                    name="copy.txt",
                    mimeType="text/plain",
                    data=message.attachments[0].data,
                )
            ],
        )

    await handle_datachannel_message(
        channel,
        json.dumps(
            {
                "kind": "call.request",
                "id": "file-1",
                "type": "file.request",
                "payload": None,
                "attachments": [{"id": "in-1", "name": "in.txt", "mimeType": "text/plain", "size": 10}],
            }
        ),
        app,
        SlaveContext(session_id="session-1", ttl_seconds=60),
        pending_calls,
    )
    assert channel.sent == []

    await handle_datachannel_message(
        channel,
        encode_binary_frame(
            {"kind": "attachment.chunk", "callId": "file-1", "attachmentId": "in-1", "index": 0, "final": True},
            b"hello file",
        ),
        app,
        SlaveContext(session_id="session-1", ttl_seconds=60),
        pending_calls,
    )

    response = json.loads(channel.sent[0])
    assert response["kind"] == "call.response"
    assert response["payload"] == {"count": 1}
    assert response["attachments"] == [{"id": "out-1", "size": 10, "name": "copy.txt", "mimeType": "text/plain"}]
    header, body = decode_binary_frame(channel.sent[1])
    assert header == {"kind": "attachment.chunk", "callId": "file-1", "attachmentId": "out-1", "index": 0, "final": True}
    assert body == b"hello file"


@pytest.mark.asyncio
async def test_large_attachment_roundtrip_uses_multiple_chunks():
    app = SlaveApp(memory={})
    channel = DummyChannel()
    pending_calls = {}
    data = bytes(index % 251 for index in range((64 * 1024) + 123))

    @app.handler("large.request")
    def large_handler(message, memory, context):
        assert message.attachments[0].data == data
        return DataChannelMessage(
            id=message.id,
            type="large.result",
            payload={"bytes": len(message.attachments[0].data)},
            attachments=[
                DataChannelAttachment(
                    id="out-large",
                    name="large.bin",
                    mimeType="application/octet-stream",
                    data=message.attachments[0].data,
                )
            ],
        )

    await handle_datachannel_message(
        channel,
        json.dumps(
            {
                "kind": "call.request",
                "id": "large-1",
                "type": "large.request",
                "payload": None,
                "attachments": [{"id": "in-large", "name": "large.bin", "size": len(data)}],
            }
        ),
        app,
        SlaveContext(session_id="session-1", ttl_seconds=60),
        pending_calls,
    )

    for index, offset in enumerate(range(0, len(data), CHUNK_SIZE)):
        chunk = data[offset : offset + CHUNK_SIZE]
        await handle_datachannel_message(
            channel,
            encode_binary_frame(
                {
                    "kind": "attachment.chunk",
                    "callId": "large-1",
                    "attachmentId": "in-large",
                    "index": index,
                    "final": offset + CHUNK_SIZE >= len(data),
                },
                chunk,
            ),
            app,
            SlaveContext(session_id="session-1", ttl_seconds=60),
            pending_calls,
        )

    response = json.loads(channel.sent[0])
    assert response["payload"] == {"bytes": len(data)}
    assert response["attachments"] == [
        {"id": "out-large", "size": len(data), "name": "large.bin", "mimeType": "application/octet-stream"}
    ]

    chunks = []
    for index, message in enumerate(channel.sent[1:]):
        header, body = decode_binary_frame(message)
        assert header["callId"] == "large-1"
        assert header["attachmentId"] == "out-large"
        assert header["index"] == index
        assert header["final"] is (index == len(channel.sent[1:]) - 1)
        assert len(body) <= CHUNK_SIZE
        chunks.append(body)
    assert len(chunks) > 1
    assert b"".join(chunks) == data


@pytest.mark.asyncio
async def test_unknown_message_type_sends_call_error():
    app = SlaveApp(memory={})
    channel = DummyChannel()

    await handle_datachannel_message(
        channel,
        json.dumps(
            {
                "kind": "call.request",
                "id": "missing-1",
                "type": "missing.request",
                "payload": None,
                "attachments": [],
            }
        ),
        app,
        SlaveContext(session_id="session-1", ttl_seconds=60),
    )

    payload = json.loads(channel.sent[0])
    assert payload["kind"] == "call.error"
    assert payload["id"] == "missing-1"
    assert "missing.request" in payload["detail"]


@pytest.mark.asyncio
async def test_malformed_attachment_chunk_sends_error():
    app = SlaveApp(memory={})
    channel = DummyChannel()
    pending_calls = {}

    await handle_datachannel_message(
        channel,
        json.dumps(
            {
                "kind": "call.request",
                "id": "file-1",
                "type": "file.request",
                "payload": None,
                "attachments": [{"id": "in-1", "size": 1}],
            }
        ),
        app,
        SlaveContext(session_id="session-1", ttl_seconds=60),
        pending_calls,
    )
    await handle_datachannel_message(
        channel,
        encode_binary_frame(
            {"kind": "attachment.chunk", "callId": "file-1", "attachmentId": "in-1", "index": 1, "final": True},
            b"x",
        ),
        app,
        SlaveContext(session_id="session-1", ttl_seconds=60),
        pending_calls,
    )

    payload = json.loads(channel.sent[0])
    assert payload["kind"] == "call.error"
    assert payload["id"] == "file-1"
    assert "out-of-order" in payload["detail"]


@pytest.mark.asyncio
async def test_unknown_attachment_chunk_sends_error_with_chunk_call_id():
    app = SlaveApp(memory={})
    channel = DummyChannel()

    await handle_datachannel_message(
        channel,
        encode_binary_frame(
            {"kind": "attachment.chunk", "callId": "missing-1", "attachmentId": "in-1", "index": 0, "final": True},
            b"x",
        ),
        app,
        SlaveContext(session_id="session-1", ttl_seconds=60),
        {},
    )

    payload = json.loads(channel.sent[0])
    assert payload["kind"] == "call.error"
    assert payload["id"] == "missing-1"
    assert "unknown call" in payload["detail"]
