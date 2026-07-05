from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import websockets
from aiortc import RTCPeerConnection, RTCSessionDescription


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
        body={"worker_session_id": worker["id"]},
    )
    log(f"connecting signaling {descriptor['session_id']}")
    result = await run_echo(descriptor["signaling_url"])
    summary = {"worker_session_id": worker["id"], "session_id": descriptor["session_id"], "echo": result}
    log("echo.result verified")
    print(json.dumps(summary, indent=2), flush=True)
    return 0


async def run_echo(signaling_url: str) -> Any:
    pc = RTCPeerConnection()
    channel = pc.createDataChannel("gpstation.v1")
    channel_open = asyncio.Event()
    loop = asyncio.get_running_loop()
    result = loop.create_future()

    @channel.on("open")
    def on_open() -> None:
        channel_open.set()

    @channel.on("message")
    def on_message(message: Any) -> None:
        try:
            log("client datachannel message received")
            payload = json.loads(message if isinstance(message, str) else message.decode("utf-8"))
            if not result.done():
                loop.call_soon_threadsafe(result.set_result, payload)
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
        log("sending echo")
        channel.send(json.dumps({"id": "smoke-1", "type": "echo.request", "payload": {"text": "smoke"}}))
        payload = await asyncio.wait_for(result, timeout=10)
        listener.cancel()
        await pc.close()

    if payload.get("type") != "echo.result" or payload.get("payload", {}).get("text") != "smoke":
        raise RuntimeError(f"unexpected echo payload: {payload}")
    return payload


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


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
