from __future__ import annotations

import json
from typing import Any

from sdk.protocol.messages import DataChannelAttachment, DataChannelMessage

CHUNK_SIZE = 16 * 1024


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


def send_attachment(channel: Any, call_id: str, attachment: DataChannelAttachment) -> None:
    data = attachment.data
    if not data:
        channel.send(
            encode_binary_frame(
                {
                    "kind": "attachment.chunk",
                    "callId": call_id,
                    "attachmentId": attachment.id,
                    "index": 0,
                    "final": True,
                },
                b"",
            )
        )
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
