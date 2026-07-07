from __future__ import annotations

import asyncio
import json
import sys
from io import BytesIO
from types import SimpleNamespace

import pytest

from sdk.protocol.constants import DATA_CHANNEL_LABEL
from sdk.slave import DataChannelAttachment, DataChannelMessage, SlaveApp, SlaveContext
from sdk.slave.runtime import (
    CHUNK_SIZE,
    configure_aioice_gather_timeout,
    decode_binary_frame,
    encode_binary_frame,
    handle_datachannel_message,
    emit,
    load_rtc_ice_gather_timeout_seconds,
    load_rtc_memory_cache_enabled,
    load_rtc_ice_servers,
    parse_job_ready_message,
    prepare_worker_peer,
    read_stdin_line,
    send_job_result,
    summarize_sdp_candidates,
    warm_rtc_runtime,
    wait_for_job_result_ack,
)


class DummyChannel:
    label = DATA_CHANNEL_LABEL

    def __init__(self) -> None:
        self.sent: list[str | bytes] = []

    def send(self, message: str | bytes) -> None:
        self.sent.append(message)


class FakeWarmPeerConnection:
    created_with = None
    data_channel_label = None
    closed = False

    def __init__(self, configuration) -> None:
        self.configuration = configuration
        self.iceGatheringState = "complete"
        self.localDescription = SimpleNamespace(sdp="")
        FakeWarmPeerConnection.created_with = configuration
        FakeWarmPeerConnection.closed = False

    def createDataChannel(self, label: str) -> None:
        FakeWarmPeerConnection.data_channel_label = label

    async def createOffer(self):
        return SimpleNamespace(type="offer", sdp="v=0")

    async def setLocalDescription(self, _offer) -> None:
        self.localDescription = SimpleNamespace(
            sdp="\r\n".join(["v=0", "a=candidate:1 1 udp 1 10.0.0.2 5000 typ host"])
        )

    async def close(self) -> None:
        FakeWarmPeerConnection.closed = True


class FakeAioIceConnection:
    observed_timeouts: list[float] = []

    async def get_component_candidates(self, component: int, addresses: list[str], timeout: float = 5):
        FakeAioIceConnection.observed_timeouts.append(timeout)
        return []


class FakeCandidate:
    def __init__(self, candidate_type: str) -> None:
        self.type = candidate_type


class FakeGatherer:
    gathered = False

    async def gather(self):
        FakeGatherer.gathered = True

    def getLocalCandidates(self):
        return [FakeCandidate("host"), FakeCandidate("srflx")]


class FakeIceTransport:
    def __init__(self) -> None:
        self.iceGatherer = FakeGatherer()


class FakePreparedPeerConnection:
    closed = False
    created = False

    def __init__(self, configuration) -> None:
        self.configuration = configuration
        FakePreparedPeerConnection.created = True
        FakePreparedPeerConnection.closed = False
        FakeGatherer.gathered = False
        setattr(self, "_RTCPeerConnection__iceTransports", set())

    def _RTCPeerConnection__createSctpTransport(self) -> None:
        getattr(self, "_RTCPeerConnection__iceTransports").add(FakeIceTransport())

    async def close(self) -> None:
        FakePreparedPeerConnection.closed = True


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


def test_load_rtc_ice_gather_timeout_defaults_to_one_second_for_stun_only(monkeypatch):
    monkeypatch.delenv("GPSTATION_V1_RTC_ICE_GATHER_TIMEOUT_SECONDS", raising=False)

    timeout = load_rtc_ice_gather_timeout_seconds([{"urls": "stun:stun.example.com:3478"}])

    assert timeout == 1.0


def test_load_rtc_ice_gather_timeout_defaults_to_five_seconds_for_turn(monkeypatch):
    monkeypatch.delenv("GPSTATION_V1_RTC_ICE_GATHER_TIMEOUT_SECONDS", raising=False)

    timeout = load_rtc_ice_gather_timeout_seconds(
        [{"urls": ["stun:stun.example.com:3478", "turn:turn.example.com:3478"]}]
    )

    assert timeout == 5.0


def test_load_rtc_ice_gather_timeout_uses_explicit_env(monkeypatch):
    monkeypatch.setenv("GPSTATION_V1_RTC_ICE_GATHER_TIMEOUT_SECONDS", "2.5")

    timeout = load_rtc_ice_gather_timeout_seconds([{"urls": "turn:turn.example.com:3478"}])

    assert timeout == 2.5


@pytest.mark.parametrize("value", ["0", "-1", "abc"])
def test_load_rtc_ice_gather_timeout_rejects_invalid_env(monkeypatch, value):
    monkeypatch.setenv("GPSTATION_V1_RTC_ICE_GATHER_TIMEOUT_SECONDS", value)

    with pytest.raises(ValueError, match="positive number"):
        load_rtc_ice_gather_timeout_seconds([{"urls": "stun:stun.example.com:3478"}])


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", True),
        ("true", True),
        ("1", True),
        ("false", False),
        ("0", False),
    ],
)
def test_load_rtc_memory_cache_enabled(monkeypatch, value, expected):
    if value:
        monkeypatch.setenv("GPSTATION_V1_RTC_MEMORY_CACHE_ENABLED", value)
    else:
        monkeypatch.delenv("GPSTATION_V1_RTC_MEMORY_CACHE_ENABLED", raising=False)

    assert load_rtc_memory_cache_enabled() is expected


def test_load_rtc_memory_cache_enabled_rejects_invalid_env(monkeypatch):
    monkeypatch.setenv("GPSTATION_V1_RTC_MEMORY_CACHE_ENABLED", "maybe")

    with pytest.raises(ValueError, match="true or false"):
        load_rtc_memory_cache_enabled()


@pytest.mark.asyncio
async def test_configure_aioice_gather_timeout_patches_default_timeout():
    FakeAioIceConnection.observed_timeouts = []

    configure_aioice_gather_timeout(FakeAioIceConnection, 1.25)
    await FakeAioIceConnection().get_component_candidates(component=1, addresses=["10.0.0.2"])

    assert FakeAioIceConnection.observed_timeouts == [1.25]


@pytest.mark.asyncio
async def test_prepare_worker_peer_keeps_live_gathered_peer(capsys):
    configuration = object()

    prepared = await prepare_worker_peer(FakePreparedPeerConnection, configuration, label="test")

    assert prepared.pc.configuration is configuration
    assert FakePreparedPeerConnection.created is True
    assert FakePreparedPeerConnection.closed is False
    assert FakeGatherer.gathered is True
    captured = capsys.readouterr()
    assert "test ICE memory cache prepared" in captured.err
    assert "srflx=1" in captured.err


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
async def test_warm_rtc_runtime_creates_offer_gathers_and_closes(capsys):
    configuration = object()

    await warm_rtc_runtime(FakeWarmPeerConnection, configuration, label="test")

    assert FakeWarmPeerConnection.created_with is configuration
    assert FakeWarmPeerConnection.data_channel_label == DATA_CHANNEL_LABEL
    assert FakeWarmPeerConnection.closed is True
    captured = capsys.readouterr()
    assert "test ICE warmup complete" in captured.err
    assert "host=1" in captured.err


def test_send_job_result_uses_job_result_envelope():
    channel = DummyChannel()

    send_job_result(
        channel,
        "job-1",
        DataChannelMessage(id="job-1", type="echo.result", payload={"text": "hello"}),
    )

    assert json.loads(channel.sent[0]) == {
        "kind": "job.result",
        "id": "job-1",
        "type": "echo.result",
        "payload": {"text": "hello"},
        "attachments": [],
    }


def test_read_stdin_line_decodes_utf8_bytes(monkeypatch):
    class FakeStdin:
        buffer = BytesIO(json.dumps({"prompt": "한글"}, ensure_ascii=False).encode("utf-8") + b"\n")

    monkeypatch.setattr(sys, "stdin", FakeStdin())

    line = read_stdin_line()

    assert json.loads(line)["prompt"] == "한글"


def test_emit_writes_utf8_json_line(monkeypatch):
    class FakeStdout:
        def __init__(self) -> None:
            self.buffer = BytesIO()

    stdout = FakeStdout()
    monkeypatch.setattr(sys, "stdout", stdout)

    emit({"type": "test", "payload": "한글"})

    output = stdout.buffer.getvalue()
    assert "한글".encode("utf-8") in output
    assert json.loads(output.decode("utf-8")) == {"type": "test", "payload": "한글"}


def test_parse_job_ready_message_extracts_input_payload():
    is_ready, input_payload, error = parse_job_ready_message(
        json.dumps({"kind": "job.ready", "id": "job-1", "input": {"text": "한글"}}),
        "job-1",
    )

    assert is_ready is True
    assert input_payload == {"text": "한글"}
    assert error is None


def test_parse_job_ready_message_rejects_wrong_job_id():
    is_ready, input_payload, error = parse_job_ready_message(
        json.dumps({"kind": "job.ready", "id": "other", "input": {"text": "hello"}}),
        "job-1",
    )

    assert is_ready is True
    assert input_payload is None
    assert error == "job.ready id mismatch: expected job-1, got other"


def test_parse_job_ready_message_reports_malformed_frame():
    is_ready, input_payload, error = parse_job_ready_message("{not-json", "job-1")

    assert is_ready is True
    assert input_payload is None
    assert error is not None
    assert "malformed job.ready frame" in error


@pytest.mark.asyncio
async def test_wait_for_job_result_ack_succeeds_when_ack_arrives():
    ack_event = asyncio.Event()
    closed_event = asyncio.Event()
    task = asyncio.create_task(wait_for_job_result_ack("job-1", ack_event, closed_event, timeout_seconds=1))

    await asyncio.sleep(0)
    ack_event.set()

    await task


@pytest.mark.asyncio
async def test_wait_for_job_result_ack_times_out():
    with pytest.raises(RuntimeError, match="result delivery ack timeout"):
        await wait_for_job_result_ack("job-1", asyncio.Event(), asyncio.Event(), timeout_seconds=0.01)


@pytest.mark.asyncio
async def test_wait_for_job_result_ack_fails_when_channel_closes_first():
    closed_event = asyncio.Event()
    closed_event.set()

    with pytest.raises(RuntimeError, match="closed before result delivery ack"):
        await wait_for_job_result_ack("job-1", asyncio.Event(), closed_event, timeout_seconds=1)


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
