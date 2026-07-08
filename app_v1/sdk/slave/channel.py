from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from sdk.protocol.constants import DATA_CHANNEL_LABEL
from sdk.protocol.messages import DataChannelAttachment, DataChannelMessage

from sdk.slave.app import SlaveApp, SlaveContext
from sdk.slave.io import log

CHUNK_SIZE = 16 * 1024


@dataclass
class PendingAttachment:
    meta: DataChannelAttachment
    chunks: list[bytes] = field(default_factory=list)
    received_size: int = 0
    next_index: int = 0
    complete: bool = False


@dataclass
class PendingCall:
    id: str
    type: str
    payload: Any
    attachments: dict[str, PendingAttachment]

    def is_complete(self) -> bool:
        return all(attachment.complete for attachment in self.attachments.values())

    def to_message(self) -> DataChannelMessage:
        attachments = [
            DataChannelAttachment(
                id=attachment.meta.id,
                name=attachment.meta.name,
                mimeType=attachment.meta.mimeType,
                size=attachment.meta.size,
                data=b"".join(attachment.chunks),
            )
            for attachment in self.attachments.values()
        ]
        return DataChannelMessage(id=self.id, type=self.type, payload=self.payload, attachments=attachments)


async def handle_datachannel_message(
    channel: Any,
    raw_message: Any,
    app: SlaveApp,
    context: SlaveContext,
    pending_calls: dict[str, PendingCall] | None = None,
) -> None:
    calls = pending_calls if pending_calls is not None else {}
    try:
        if channel.label != DATA_CHANNEL_LABEL:
            raise ValueError(f"unsupported data channel label: {channel.label}")
        if isinstance(raw_message, str):
            await handle_control_frame(channel, raw_message, app, context, calls)
            return
        await handle_binary_frame(channel, raw_message, app, context, calls)
    except Exception as exc:
        log(f"datachannel error: {exc}")
        send_error(channel, error_call_id(raw_message), str(exc))


async def handle_control_frame(
    channel: Any,
    raw_message: str,
    app: SlaveApp,
    context: SlaveContext,
    pending_calls: dict[str, PendingCall],
) -> None:
    frame = json.loads(raw_message)
    if frame.get("kind") != "call.request":
        raise ValueError(f"unsupported data channel frame: {frame.get('kind')}")
    call_id = str(frame["id"])
    attachments = {
        str(item["id"]): PendingAttachment(
            meta=DataChannelAttachment(
                id=str(item["id"]),
                name=item.get("name"),
                mimeType=item.get("mimeType"),
                size=int(item.get("size") or 0),
            )
        )
        for item in frame.get("attachments", [])
    }
    call = PendingCall(id=call_id, type=str(frame["type"]), payload=frame.get("payload"), attachments=attachments)
    if not attachments:
        await dispatch_call(channel, app, context, call)
        return
    pending_calls[call_id] = call


async def handle_binary_frame(
    channel: Any,
    raw_message: Any,
    app: SlaveApp,
    context: SlaveContext,
    pending_calls: dict[str, PendingCall],
) -> None:
    header, body = decode_binary_frame(raw_message)
    if header.get("kind") != "attachment.chunk":
        raise ValueError(f"unsupported binary frame: {header.get('kind')}")
    call_id = str(header["callId"])
    attachment_id = str(header["attachmentId"])
    call = pending_calls.get(call_id)
    if call is None:
        raise ValueError(f"unknown call for attachment chunk: {call_id}")
    attachment = call.attachments.get(attachment_id)
    if attachment is None:
        raise ValueError(f"unknown attachment chunk: {attachment_id}")
    index = int(header["index"])
    if index != attachment.next_index:
        raise ValueError(f"out-of-order attachment chunk: {attachment_id}")
    if attachment.complete:
        raise ValueError(f"attachment chunk after final: {attachment_id}")

    attachment.chunks.append(body)
    attachment.received_size += len(body)
    attachment.next_index += 1
    attachment.complete = bool(header.get("final"))

    expected_size = attachment.meta.size or 0
    if attachment.received_size > expected_size:
        raise ValueError(f"attachment exceeded declared size: {attachment_id}")
    if attachment.complete and attachment.received_size != expected_size:
        raise ValueError(f"attachment size mismatch: {attachment_id}")

    if call.is_complete():
        pending_calls.pop(call_id, None)
        await dispatch_call(channel, app, context, call)


async def dispatch_call(channel: Any, app: SlaveApp, context: SlaveContext, call: PendingCall) -> None:
    started_at = time.perf_counter()
    log(f"call dispatch start: id={call.id} type={call.type} attachments={len(call.attachments)}")
    try:
        response = await app.dispatch(call.to_message(), context)
        if response is None:
            response = DataChannelMessage(id=call.id, type=f"{call.type}.result", payload=None)
        send_response(channel, response)
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        log(f"call dispatch complete: id={call.id} type={call.type} duration_ms={duration_ms}")
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        log(f"call dispatch failed: id={call.id} type={call.type} duration_ms={duration_ms} error={exc}")
        send_error(channel, call.id, str(exc))


def send_response(channel: Any, message: DataChannelMessage) -> None:
    attachments = [attachment_metadata(attachment) for attachment in message.attachments]
    channel.send(
        json.dumps(
            {
                "kind": "call.response",
                "id": message.id,
                "type": message.type,
                "payload": message.payload,
                "attachments": attachments,
            },
            ensure_ascii=False,
        )
    )
    for attachment in message.attachments:
        send_attachment(channel, message.id, attachment)


def send_job_result(channel: Any, job_id: str, message: DataChannelMessage) -> None:
    attachments = [attachment_metadata(attachment) for attachment in message.attachments]
    channel.send(
        json.dumps(
            {
                "kind": "job.result",
                "id": job_id,
                "type": message.type,
                "payload": message.payload,
                "attachments": attachments,
            },
            ensure_ascii=False,
        )
    )
    for attachment in message.attachments:
        send_attachment(channel, job_id, attachment)


def send_error(channel: Any, call_id: str, detail: str, code: str = "call_error") -> None:
    channel.send(json.dumps({"kind": "call.error", "id": call_id, "code": code, "detail": detail}, ensure_ascii=False))


def send_attachment(channel: Any, call_id: str, attachment: DataChannelAttachment) -> None:
    data = attachment.data
    if not data:
        channel.send(encode_binary_frame({"kind": "attachment.chunk", "callId": call_id, "attachmentId": attachment.id, "index": 0, "final": True}, b""))
        return
    index = 0
    for offset in range(0, len(data), CHUNK_SIZE):
        chunk = data[offset : offset + CHUNK_SIZE]
        final = offset + CHUNK_SIZE >= len(data)
        channel.send(
            encode_binary_frame(
                {
                    "kind": "attachment.chunk",
                    "callId": call_id,
                    "attachmentId": attachment.id,
                    "index": index,
                    "final": final,
                },
                chunk,
            )
        )
        index += 1


def attachment_metadata(attachment: DataChannelAttachment) -> dict[str, Any]:
    metadata: dict[str, Any] = {"id": attachment.id, "size": attachment.size or len(attachment.data)}
    if attachment.name is not None:
        metadata["name"] = attachment.name
    if attachment.mimeType is not None:
        metadata["mimeType"] = attachment.mimeType
    return metadata


def encode_binary_frame(header: dict[str, Any], body: bytes) -> bytes:
    header_bytes = json.dumps(header, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return len(header_bytes).to_bytes(4, "big") + header_bytes + body


def decode_binary_frame(raw_message: Any) -> tuple[dict[str, Any], bytes]:
    data = bytes(raw_message)
    if len(data) < 4:
        raise ValueError("binary frame is too short")
    header_length = int.from_bytes(data[:4], "big")
    if header_length <= 0 or len(data) < 4 + header_length:
        raise ValueError("invalid binary frame header length")
    header = json.loads(data[4 : 4 + header_length].decode("utf-8"))
    return header, data[4 + header_length :]


def error_call_id(raw_message: Any) -> str:
    try:
        if isinstance(raw_message, str):
            return str(json.loads(raw_message).get("id") or "error")
        header, _body = decode_binary_frame(raw_message)
        return str(header.get("callId") or "error")
    except Exception:
        return "error"
