from pydantic import ValidationError

from sdk.protocol.messages import DataChannelAttachment, DataChannelMessage, parse_control_message


def test_parse_launcher_hello_message():
    message = parse_control_message(
        {
            "type": "launcher.hello",
            "launcher_name": "desktop-4090",
            "slave_app_ids": ["echo"],
            "metadata": {
                "slave_apps": {
                    "ai": {
                        "startup_timeout_seconds": 300,
                    }
                }
            },
        }
    )

    assert message.type == "launcher.hello"
    assert message.launcher_name == "desktop-4090"
    assert message.slave_app_ids == ["echo"]
    assert message.metadata["slave_apps"]["ai"]["startup_timeout_seconds"] == 300


def test_parse_launcher_accepted_capabilities():
    message = parse_control_message(
        {
            "type": "launcher.accepted",
            "launcher_session_id": "launcher-1",
            "server_time": "2026-07-07T00:00:00+00:00",
            "capabilities": {"session_logs": True},
        }
    )

    assert message.type == "launcher.accepted"
    assert message.capabilities == {"session_logs": True}


def test_parse_rejects_extra_fields():
    try:
        parse_control_message({"type": "ping", "extra": True})
    except ValidationError as exc:
        assert "extra" in str(exc)
    else:
        raise AssertionError("ValidationError was not raised")


def test_parse_session_log_message():
    message = parse_control_message(
        {
            "type": "session.log",
            "session_id": "session-1",
            "time": "2026-07-07T00:00:00+00:00",
            "stream": "stderr",
            "line": "model loading",
        }
    )

    assert message.type == "session.log"
    assert message.stream == "stderr"
    assert message.line == "model loading"


def test_parse_launcher_heartbeat_with_worker_state():
    message = parse_control_message(
        {
            "type": "launcher.heartbeat",
            "status": "busy",
            "active_session_ids": [],
            "current_job_id": "job-1",
            "loaded_slave_app_id": "ai",
            "worker_status": "busy",
            "metadata": {"gpu": "RTX"},
        }
    )

    assert message.type == "launcher.heartbeat"
    assert message.current_job_id == "job-1"
    assert message.loaded_slave_app_id == "ai"
    assert message.worker_status == "busy"


def test_parse_job_start_message():
    message = parse_control_message(
        {
            "type": "job.start",
            "job_id": "job-1",
            "handler_type": "echo.request",
            "slave_app_id": "echo",
            "input": {"text": "hello"},
            "offer": {"type": "offer", "sdp": "v=0\r\n"},
        }
    )

    assert message.type == "job.start"
    assert message.offer.type == "offer"
    assert message.input == {"text": "hello"}


def test_data_channel_echo_result_envelope():
    message = DataChannelMessage(
        id="msg-1",
        type="echo.result",
        payload={"text": "hello"},
    )

    assert message.payload == {"text": "hello"}


def test_data_channel_allows_plugin_message_type():
    message = DataChannelMessage(
        id="msg-2",
        type="custom.progress",
        payload={"percent": 50},
    )

    assert message.type == "custom.progress"


def test_data_channel_message_allows_binary_attachments():
    attachment = DataChannelAttachment(
        id="file-1",
        name="hello.txt",
        mimeType="text/plain",
        data=b"hello",
    )
    message = DataChannelMessage(
        id="msg-3",
        type="custom.result",
        payload={"ok": True},
        attachments=[attachment],
    )

    assert message.attachments[0].size == 5
    assert message.attachments[0].data == b"hello"
