from pydantic import ValidationError

from sdk.protocol.messages import DataChannelAttachment, DataChannelMessage, parse_control_message


def test_parse_launcher_hello_message():
    message = parse_control_message(
        {
            "type": "launcher.hello",
            "launcher_name": "desktop-4090",
            "slave_app_ids": ["echo"],
        }
    )

    assert message.type == "launcher.hello"
    assert message.launcher_name == "desktop-4090"
    assert message.slave_app_ids == ["echo"]


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
