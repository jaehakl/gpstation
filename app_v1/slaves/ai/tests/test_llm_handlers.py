from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from sdk.slave import DataChannelMessage, SlaveContext

from app import __main__ as ai_slave
from app.llm import chat as llm_chat
from app.llm import handlers as llm_handlers
from app.llm.models import ChatRequest, ChatResponse, LlmRequest, LlmResponse


def context() -> SlaveContext:
    return SlaveContext(session_id="session-1", ttl_seconds=60)


class LlmHandlerTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        ai_slave.app.memory.clear()

    async def test_llm_returns_answer_payload(self) -> None:
        generate_llm_answer = AsyncMock(return_value=LlmResponse(answer="hello"))

        with patch.object(llm_handlers, "generate_llm_answer", generate_llm_answer):
            response = await ai_slave.app.dispatch(
                DataChannelMessage(
                    id="call-1",
                    type="ai.llm",
                    payload={"system_prompt": "Answer briefly.", "prompt": "Say hello."},
                ),
                context(),
            )

        self.assertEqual(response.type, "ai.llm.result")
        self.assertEqual(response.payload, {"answer": "hello"})
        self.assertEqual(response.attachments, [])
        generate_llm_answer.assert_awaited_once()

    def test_llm_request_accepts_korean_text(self) -> None:
        request = LlmRequest(system_prompt="친절하게 답하세요.", prompt="한글 질문입니다.")

        self.assertEqual(request.prompt, "한글 질문입니다.")

    def test_llm_request_rejects_surrogate_text(self) -> None:
        with self.assertRaises(ValueError) as error:
            LlmRequest(system_prompt="system", prompt="bad\udcec")

        self.assertIn("invalid Unicode surrogate", str(error.exception))

    async def test_chat_streams_and_returns_answer_payload(self) -> None:
        events = []

        async def send_event(event_type, payload):
            events.append((event_type, payload))

        async def generate_chat_answer(request, messages, on_delta):
            self.assertEqual(
                messages,
                [
                    {"role": "system", "content": "Answer briefly."},
                    {"role": "user", "content": "Say hello."},
                ],
            )
            await on_delta("he")
            await on_delta("llo")
            return ChatResponse(
                answer="hello",
                context_window=4096,
                prompt_tokens=12,
                max_response_tokens=512,
                remaining_tokens=4078,
                cache_enabled=True,
            )

        with patch.object(llm_handlers, "generate_chat_answer", generate_chat_answer):
            response = await ai_slave.app.dispatch(
                DataChannelMessage(
                    id="call-1",
                    type="ai.chat",
                    payload={"system_prompt": "Answer briefly.", "prompt": "Say hello."},
                ),
                SlaveContext(
                    session_id="session-1",
                    ttl_seconds=60,
                    call_id="call-1",
                    _event_sender=send_event,
                ),
            )

        self.assertEqual(
            response.payload,
            {
                "answer": "hello",
                "context_window": 4096,
                "prompt_tokens": 12,
                "max_response_tokens": 512,
                "remaining_tokens": 4078,
                "cache_enabled": True,
            },
        )
        self.assertEqual(events, [("ai.chat.delta", {"delta": "he"}), ("ai.chat.delta", {"delta": "llo"})])
        self.assertEqual(
            ai_slave.app.memory[llm_chat.CHAT_MEMORY_KEY]["messages"],
            [
                {"role": "system", "content": "Answer briefly."},
                {"role": "user", "content": "Say hello."},
                {"role": "assistant", "content": "hello"},
            ],
        )

    async def test_chat_reuses_context_for_prompt_only_followup(self) -> None:
        calls = []

        async def generate_chat_answer(request, messages, on_delta):
            calls.append(messages)
            return ChatResponse(
                answer=f"answer {len(calls)}",
                context_window=4096,
                prompt_tokens=10 + len(calls),
                max_response_tokens=512,
                remaining_tokens=4000 - len(calls),
                cache_enabled=True,
            )

        with patch.object(llm_handlers, "generate_chat_answer", generate_chat_answer):
            first = await ai_slave.app.dispatch(
                DataChannelMessage(
                    id="call-1",
                    type="ai.chat",
                    payload={"system_prompt": "Stay concise.", "prompt": "First question."},
                ),
                context(),
            )
            second = await ai_slave.app.dispatch(
                DataChannelMessage(id="call-2", type="ai.chat", payload={"prompt": "Second question."}),
                context(),
            )

        self.assertEqual(first.payload["answer"], "answer 1")
        self.assertEqual(second.payload["answer"], "answer 2")
        self.assertEqual(
            calls[1],
            [
                {"role": "system", "content": "Stay concise."},
                {"role": "user", "content": "First question."},
                {"role": "assistant", "content": "answer 1"},
                {"role": "user", "content": "Second question."},
            ],
        )

    async def test_chat_requires_system_prompt_for_first_call(self) -> None:
        with self.assertRaises(ValueError) as error:
            await ai_slave.app.dispatch(
                DataChannelMessage(id="call-1", type="ai.chat", payload={"prompt": "Hello."}),
                context(),
            )

        self.assertEqual(str(error.exception), "system_prompt is required for the first ai.chat call")

    async def test_chat_rejects_system_prompt_change_in_active_session(self) -> None:
        async def generate_chat_answer(request, messages, on_delta):
            return ChatResponse(
                answer="ok",
                context_window=4096,
                prompt_tokens=8,
                max_response_tokens=512,
                remaining_tokens=4080,
                cache_enabled=True,
            )

        with patch.object(llm_handlers, "generate_chat_answer", generate_chat_answer):
            await ai_slave.app.dispatch(
                DataChannelMessage(
                    id="call-1",
                    type="ai.chat",
                    payload={"system_prompt": "Original system.", "prompt": "Hello."},
                ),
                context(),
            )
            with self.assertRaises(ValueError) as error:
                await ai_slave.app.dispatch(
                    DataChannelMessage(
                        id="call-2",
                        type="ai.chat",
                        payload={"system_prompt": "Changed system.", "prompt": "Hello again."},
                    ),
                    context(),
                )

        self.assertEqual(str(error.exception), "system_prompt cannot change within an active ai.chat session")

    async def test_chat_allows_enable_thinking_change_in_active_session(self) -> None:
        requests = []

        async def generate_chat_answer(request, messages, on_delta):
            requests.append(request)
            return ChatResponse(
                answer=f"answer {len(requests)}",
                context_window=4096,
                prompt_tokens=10,
                max_response_tokens=512,
                remaining_tokens=4000,
                cache_enabled=True,
            )

        with patch.object(llm_handlers, "generate_chat_answer", generate_chat_answer):
            await ai_slave.app.dispatch(
                DataChannelMessage(
                    id="call-1",
                    type="ai.chat",
                    payload={
                        "system_prompt": "Stay concise.",
                        "prompt": "First question.",
                        "enable_thinking": False,
                    },
                ),
                context(),
            )
            await ai_slave.app.dispatch(
                DataChannelMessage(
                    id="call-2",
                    type="ai.chat",
                    payload={"prompt": "Second question.", "enable_thinking": True},
                ),
                context(),
            )

        self.assertIs(requests[0].enable_thinking, False)
        self.assertIs(requests[1].enable_thinking, True)

    def test_chat_request_accepts_korean_text(self) -> None:
        request = ChatRequest(system_prompt="친절하게 답하세요.", prompt="한글 질문입니다.")

        self.assertEqual(request.prompt, "한글 질문입니다.")

    def test_chat_request_accepts_enable_thinking(self) -> None:
        request = ChatRequest(system_prompt="system", prompt="prompt", enable_thinking=True)

        self.assertIs(request.enable_thinking, True)

    def test_chat_request_rejects_surrogate_text(self) -> None:
        with self.assertRaises(ValueError) as error:
            ChatRequest(system_prompt="system", prompt="bad\udcec")

        self.assertIn("invalid Unicode surrogate", str(error.exception))


if __name__ == "__main__":
    unittest.main()
