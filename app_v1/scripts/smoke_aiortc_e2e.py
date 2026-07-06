from __future__ import annotations

import asyncio
from contextlib import suppress
import json
import sys
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import websockets
from aiortc import RTCPeerConnection, RTCSessionDescription

CHUNK_SIZE = 16 * 1024


async def main() -> int:
    base_url = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8100").rstrip("/")
    token = sys.argv[2] if len(sys.argv) > 2 else "demo-client-token"
    log("listing workers")
    worker = next(item for item in fetch_json(f"{base_url}/v1/workers", token) if item["status"] in {"ready", "busy"})
    log(f"creating session for {worker['id']}")
    descriptor = fetch_json(
        f"{base_url}/v1/sessions",
        token,
        method="POST",
        body={"worker_session_id": worker["id"], "slave_app_id": "echo"},
    )
    log(f"connecting signaling {descriptor['session_id']}")
    result = await run_call(descriptor["signaling_url"])
    summary = {
        "worker_session_id": worker["id"],
        "slave_app_id": descriptor["slave_app_id"],
        "session_id": descriptor["session_id"],
        "call": result,
    }
    log("call.response verified")
    print(json.dumps(summary, indent=2), flush=True)
    return 0


async def run_call(signaling_url: str) -> Any:
    pc = RTCPeerConnection()
    channel = pc.createDataChannel("gpstation.v1")
    channel_open = asyncio.Event()
    loop = asyncio.get_running_loop()
    result = loop.create_future()
    response: dict[str, Any] | None = None
    files: dict[str, bytearray] = {}
    file_meta: dict[str, dict[str, Any]] = {}

    @channel.on("open")
    def on_open() -> None:
        channel_open.set()

    @channel.on("message")
    def on_message(message: Any) -> None:
        try:
            log("client datachannel message received")
            nonlocal response
            if isinstance(message, str):
                payload = json.loads(message)
                if payload.get("kind") == "call.error":
                    raise RuntimeError(payload.get("detail") or "call error")
                if payload.get("kind") != "call.response":
                    return
                response = payload
                file_meta.clear()
                files.clear()
                for item in payload.get("attachments", []):
                    file_meta[item["id"]] = item
                    files[item["id"]] = bytearray()
                if not file_meta and not result.done():
                    loop.call_soon_threadsafe(result.set_result, {"response": response, "files": {}})
                return

            header, body = decode_binary_frame(message)
            if header.get("kind") != "attachment.chunk" or response is None:
                return
            attachment_id = header["attachmentId"]
            files[attachment_id].extend(body)
            if header.get("final") and all(len(files[item_id]) == item["size"] for item_id, item in file_meta.items()):
                if not result.done():
                    loop.call_soon_threadsafe(
                        result.set_result,
                        {"response": response, "files": {item_id: bytes(data) for item_id, data in files.items()}},
                    )
        except Exception as exc:
            if not result.done():
                loop.call_soon_threadsafe(result.set_exception, exc)

    async with websockets.connect(signaling_url) as websocket:
        listener = asyncio.create_task(read_signaling(websocket, pc))
        log("creating offer")
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        log("waiting for local ICE gathering")
        await wait_for_ice_gathering(pc)
        log("sending offer")
        await websocket.send(json.dumps({"signal": {"type": "offer", "sdp": pc.localDescription.sdp}}))

        log("waiting for data channel")
        await asyncio.wait_for(channel_open.wait(), timeout=20)
        await asyncio.sleep(0.5)
        log("sending call")
        attachment_data = bytes(index % 251 for index in range((96 * 1024) + 7))
        channel.send(
            json.dumps(
                {
                    "kind": "call.request",
                    "id": "smoke-1",
                    "type": "echo.request",
                    "payload": {"text": "smoke"},
                    "attachments": [
                        {
                            "id": "file-1",
                            "name": "smoke.txt",
                            "mimeType": "text/plain",
                            "size": len(attachment_data),
                        }
                    ],
                }
            )
        )
        for index, offset in enumerate(range(0, len(attachment_data), CHUNK_SIZE)):
            channel.send(
                encode_binary_frame(
                    {
                        "kind": "attachment.chunk",
                        "callId": "smoke-1",
                        "attachmentId": "file-1",
                        "index": index,
                        "final": offset + CHUNK_SIZE >= len(attachment_data),
                    },
                    attachment_data[offset : offset + CHUNK_SIZE],
                )
            )
        payload = await asyncio.wait_for(result, timeout=20)
        log("call payload assembled")
        listener.cancel()
        with suppress(asyncio.CancelledError):
            await listener
        try:
            await asyncio.wait_for(pc.close(), timeout=5)
        except TimeoutError:
            log("peer close timed out after verified call")

    response_payload = payload["response"]
    if response_payload.get("type") != "echo.result" or response_payload.get("payload", {}).get("text") != "smoke":
        raise RuntimeError(f"unexpected call payload: {payload}")
    if payload["files"].get("file-1") != attachment_data:
        raise RuntimeError(f"unexpected attachment payload: {payload}")
    returned_file = payload["files"]["file-1"]
    return {
        "response": response_payload,
        "files": {
            "file-1": {
                "name": "smoke.txt",
                "bytes": len(returned_file),
                "checksum": sum(returned_file) % 65536,
            }
        },
    }


async def read_signaling(websocket: Any, pc: RTCPeerConnection) -> None:
    async for raw_message in websocket:
        payload = json.loads(raw_message)
        if payload.get("type") == "session.error":
            raise RuntimeError(payload.get("detail") or "session error")
        signal = payload.get("signal")
        if not signal:
            continue
        if signal["type"] == "answer":
            log("received answer")
            await pc.setRemoteDescription(RTCSessionDescription(sdp=signal["sdp"], type="answer"))


async def wait_for_ice_gathering(pc: RTCPeerConnection) -> None:
    if pc.iceGatheringState == "complete":
        return
    done = asyncio.get_running_loop().create_future()

    @pc.on("icegatheringstatechange")
    def on_icegatheringstatechange() -> None:
        if pc.iceGatheringState == "complete" and not done.done():
            done.set_result(None)

    await asyncio.wait_for(done, timeout=10)


def fetch_json(url: str, token: str, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def log(message: str) -> None:
    print(message, flush=True)
    run_dir = Path(".run")
    if run_dir.exists():
        with (run_dir / "smoke-aiortc-e2e.log").open("a", encoding="utf-8") as file:
            file.write(message + "\n")


def encode_binary_frame(header: dict[str, Any], body: bytes) -> bytes:
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    return len(header_bytes).to_bytes(4, "big") + header_bytes + body


def decode_binary_frame(message: Any) -> tuple[dict[str, Any], bytes]:
    data = message if isinstance(message, bytes) else bytes(message)
    header_length = int.from_bytes(data[:4], "big")
    header = json.loads(data[4 : 4 + header_length].decode("utf-8"))
    return header, data[4 + header_length :]


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
