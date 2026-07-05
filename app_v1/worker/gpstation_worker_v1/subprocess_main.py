from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from gpstation_protocol.constants import DATA_CHANNEL_LABEL
from gpstation_protocol.messages import DataChannelMessage


async def main() -> None:
    args = parse_args()
    try:
        from aiortc import RTCSessionDescription
        from aiortc.sdp import candidate_from_sdp
    except Exception as exc:
        emit({"type": "error", "code": "aiortc_import_failed", "detail": str(exc)})
        return

    from aiortc import RTCPeerConnection

    pc = RTCPeerConnection()
    closed = asyncio.Event()

    @pc.on("datachannel")
    def on_datachannel(channel: Any) -> None:
        log(f"datachannel: {channel.label}")

        @channel.on("message")
        def on_message(message: Any) -> None:
            log("datachannel message received")
            asyncio.create_task(handle_datachannel_message(channel, message))

    @pc.on("connectionstatechange")
    async def on_connectionstatechange() -> None:
        if pc.connectionState in {"closed", "failed", "disconnected"}:
            closed.set()

    emit({"type": "ready", "session_id": args.session_id})

    try:
        while not closed.is_set():
            line = await asyncio.to_thread(sys.stdin.readline)
            if not line:
                break
            message = json.loads(line)
            if message.get("type") == "stop":
                break
            if message.get("type") == "signal":
                await handle_signal(pc, message["signal"], RTCSessionDescription, candidate_from_sdp)
    except Exception as exc:
        emit({"type": "error", "code": "runtime_error", "detail": str(exc)})
    finally:
        await pc.close()
        emit({"type": "closed", "session_id": args.session_id})


async def handle_signal(
    pc: Any,
    signal: dict[str, Any],
    rtc_session_description: Any,
    candidate_from_sdp: Any,
) -> None:
    signal_type = signal.get("type")
    if signal_type == "offer":
        await pc.setRemoteDescription(rtc_session_description(sdp=signal["sdp"], type="offer"))
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        await wait_for_ice_gathering(pc)
        emit(
            {
                "type": "signal",
                "signal": {
                    "type": "answer",
                    "sdp": pc.localDescription.sdp,
                },
            }
        )
        return
    if signal_type == "ice":
        candidate_text = signal.get("candidate")
        if not candidate_text:
            await pc.addIceCandidate(None)
            return
        if candidate_text.startswith("candidate:"):
            candidate_text = candidate_text.removeprefix("candidate:")
        candidate = candidate_from_sdp(candidate_text)
        candidate.sdpMid = signal.get("sdpMid")
        candidate.sdpMLineIndex = signal.get("sdpMLineIndex")
        await pc.addIceCandidate(candidate)


async def wait_for_ice_gathering(pc: Any) -> None:
    if pc.iceGatheringState == "complete":
        return
    loop = asyncio.get_running_loop()
    done = loop.create_future()

    @pc.on("icegatheringstatechange")
    def on_icegatheringstatechange() -> None:
        if pc.iceGatheringState == "complete" and not done.done():
            done.set_result(None)

    try:
        await asyncio.wait_for(done, timeout=5)
    except TimeoutError:
        return


async def handle_datachannel_message(channel: Any, raw_message: Any) -> None:
    try:
        if channel.label != DATA_CHANNEL_LABEL:
            raise ValueError(f"unsupported data channel label: {channel.label}")
        payload = json.loads(raw_message if isinstance(raw_message, str) else raw_message.decode("utf-8"))
        message = DataChannelMessage.model_validate(payload)
        if message.type != "echo.request":
            raise ValueError(f"unsupported data channel message: {message.type}")
        response = DataChannelMessage(id=message.id, type="echo.result", payload=message.payload)
        channel.send(response.model_dump_json())
        log("echo.result sent")
    except Exception as exc:
        log(f"datachannel error: {exc}")
        channel.send(DataChannelMessage(id="error", type="error", payload={"detail": str(exc)}).model_dump_json())


def emit(message: dict[str, Any]) -> None:
    print(json.dumps(message, ensure_ascii=False), flush=True)


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--ttl-seconds", type=int, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main())
