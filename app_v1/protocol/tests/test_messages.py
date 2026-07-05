from pydantic import ValidationError

from gpstation_protocol.messages import DataChannelMessage, parse_control_message


def test_parse_worker_hello_message():
    message = parse_control_message(
        {
            "type": "worker.hello",
            "worker_name": "desktop-4090",
            "capabilities": ["echo"],
        }
    )

    assert message.type == "worker.hello"
    assert message.worker_name == "desktop-4090"


def test_parse_rejects_extra_fields():
    try:
        parse_control_message({"type": "ping", "extra": True})
    except ValidationError as exc:
        assert "extra" in str(exc)
    else:
        raise AssertionError("ValidationError was not raised")


def test_data_channel_echo_result_envelope():
    message = DataChannelMessage(
        id="msg-1",
        type="echo.result",
        payload={"text": "hello"},
    )

    assert message.payload == {"text": "hello"}
