from __future__ import annotations

import json

import pytest

from sdk.protocol.constants import DATA_CHANNEL_LABEL
from sdk.slave import DataChannelAttachment, DataChannelMessage, SlaveApp, SlaveContext
from sdk.slave.runtime import (
    CHUNK_SIZE,
    decode_binary_frame,
    encode_binary_frame,
    handle_datachannel_message,
    load_rtc_ice_servers,
    summarize_sdp_candidates,
)


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


def test_load_rtc_ice_servers_uses_default_stun(monkeypatch):
    monkeypatch.delenv("GPSTATION_V1_RTC_ICE_SERVERS_JSON", raising=False)

    assert load_rtc_ice_servers() == [{"urls": "stun:stun.l.google.com:19302"}]


def test_load_rtc_ice_servers_accepts_turn_credentials(monkeypatch):
    monkeypatch.setenv(
        "GPSTATION_V1_RTC_ICE_SERVERS_JSON",
        json.dumps(
            [
                {"urls": ["stun:stun.example.com:3478"]},
                {
                    "urls": "turn:turn.example.com:3478",
                    "username": "user",
                    "credential": "password",
                },
            ]
        ),
    )

    assert load_rtc_ice_servers() == [
        {"urls": ["stun:stun.example.com:3478"]},
        {"urls": "turn:turn.example.com:3478", "username": "user", "credential": "password"},
    ]


def test_load_rtc_ice_servers_rejects_invalid_json(monkeypatch):
    monkeypatch.setenv("GPSTATION_V1_RTC_ICE_SERVERS_JSON", "{not-json")

    with pytest.raises(ValueError, match="valid JSON"):
        load_rtc_ice_servers()


def test_summarize_sdp_candidates_counts_candidate_types():
    summary = summarize_sdp_candidates(
        "\r\n".join(
            [
                "v=0",
                "a=candidate:1 1 udp 1 10.0.0.2 5000 typ host",
                "a=candidate:2 1 udp 1 203.0.113.2 5001 typ srflx",
                "a=candidate:3 1 udp 1 198.51.100.2 5002 typ relay",
                "a=candidate:4 1 udp 1 198.51.100.3 5003 typ prflx",
                "a=candidate:5 1 udp 1 198.51.100.4 5004",
            ]
        )
    )

    assert summary == {"host": 1, "srflx": 1, "relay": 1, "prflx": 1, "unknown": 1, "total": 5}


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
async def test_call_dispatch_logs_to_stderr_without_stdout(capsys):
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

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "call dispatch start" in captured.err
    assert "call dispatch complete" in captured.err
    assert json.loads(channel.sent[0])["kind"] == "call.response"


@pytest.mark.asyncio
async def test_call_dispatch_failure_logs_to_stderr_without_stdout(capsys):
    app = SlaveApp(memory={})
    channel = DummyChannel()

    @app.handler("sync.request")
    def sync_handler(message, memory, context):
        raise ValueError("boom")

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

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "call dispatch failed" in captured.err
    assert json.loads(channel.sent[0])["kind"] == "call.error"


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
