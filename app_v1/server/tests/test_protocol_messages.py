import pytest
from pydantic import ValidationError

from app.models import JobCreateRequest
from sdk.protocol.messages import (
    DataChannelAttachment,
    DataChannelMessage,
    parse_launcher_message,
    parse_server_message,
)


def test_parse_launcher_hello_message():
    message = parse_launcher_message(
        {
            "type": "launcher.hello",
            "launcher_name": "desktop-4090",
            "slave_app_ids": ["ai"],
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
    assert message.slave_app_ids == ["ai"]
    assert message.metadata["slave_apps"]["ai"]["startup_timeout_seconds"] == 300


def test_parse_launcher_accepted_capabilities():
    message = parse_server_message(
        {
            "type": "launcher.accepted",
            "launcher_id": "launcher-1",
            "server_time": "2026-07-07T00:00:00+00:00",
            "capabilities": {"job_logs": True},
        }
    )

    assert message.type == "launcher.accepted"
    assert message.capabilities == {"job_logs": True}


def test_parse_rejects_extra_fields():
    try:
        parse_launcher_message({"type": "launcher.heartbeat", "extra": True})
    except ValidationError as exc:
        assert "extra" in str(exc)
    else:
        raise AssertionError("ValidationError was not raised")


def test_parse_job_log_message():
    message = parse_launcher_message(
        {
            "type": "job.log",
            "job_id": "job-1",
            "time": "2026-07-07T00:00:00+00:00",
            "stream": "stderr",
            "line": "model loading",
        }
    )

    assert message.type == "job.log"
    assert message.job_id == "job-1"
    assert message.stream == "stderr"
    assert message.line == "model loading"


def test_parse_launcher_heartbeat_with_worker_state():
    message = parse_launcher_message(
        {
            "type": "launcher.heartbeat",
            "status": "busy",
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
    message = parse_server_message(
        {
            "type": "job.start",
            "job_id": "job-1",
            "handler_type": "ai.llm",
            "slave_app_id": "ai",
            "offer": {"type": "offer", "sdp": "v=0\r\n"},
        }
    )

    assert message.type == "job.start"
    assert message.offer.type == "offer"


def test_parse_job_start_rejects_input_body():
    with pytest.raises(ValidationError):
        parse_server_message(
            {
                "type": "job.start",
                "job_id": "job-1",
                "handler_type": "ai.llm",
                "slave_app_id": "ai",
                "input": {"text": "hello"},
                "offer": {"type": "offer", "sdp": "v=0\r\n"},
            }
        )


def test_launcher_parser_rejects_server_to_launcher_message():
    with pytest.raises(ValidationError):
        parse_launcher_message(
            {
                "type": "job.start",
                "job_id": "job-1",
                "handler_type": "ai.llm",
                "slave_app_id": "ai",
                "offer": {"type": "offer", "sdp": "v=0\r\n"},
            }
        )


def test_server_parser_rejects_launcher_to_server_message():
    with pytest.raises(ValidationError):
        parse_server_message({"type": "launcher.heartbeat"})


def test_job_create_request_rejects_input_body():
    with pytest.raises(ValidationError):
        JobCreateRequest.model_validate(
            {
                "handler_type": "ai.llm",
                "slave_app_id": "ai",
                "input": {"text": "hello"},
                "offer": {"type": "offer", "sdp": "v=0\r\n"},
            }
        )


def test_data_channel_job_result_envelope():
    message = DataChannelMessage(
        id="msg-1",
        type="ai.llm.result",
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
