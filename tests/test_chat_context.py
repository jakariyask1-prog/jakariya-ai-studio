import unittest
from unittest.mock import Mock

from app.api.ClaudeClient import ClaudeClient
from app.chat.worker import ChatRequest, ClaudeWorker


class _TextStream:
    def __init__(self, chunks):
        self.text_stream = chunks

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _RecordingMessagesApi:
    def __init__(self):
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        return _TextStream(["reply"])


class _FailingMessagesApi:
    def stream(self, **_kwargs):
        raise RuntimeError("connection failed")


def _client_with(messages_api):
    """Build a ClaudeClient without credentials or a real network client."""
    client = object.__new__(ClaudeClient)
    client.client = Mock(messages=messages_api)
    client.web = Mock()
    client.system_prompt = "system"
    client.messages = []
    return client


class ClaudeContextTests(unittest.TestCase):
    def test_supplied_history_is_used_for_only_that_request(self):
        messages_api = _RecordingMessagesApi()
        client = _client_with(messages_api)
        first_history = [{"role": "user", "content": "first chat"}]
        second_history = [{"role": "user", "content": "second chat"}]

        self.assertEqual(list(client.ask_stream("first follow-up", history=first_history)), ["reply"])
        self.assertEqual(list(client.ask_stream("second follow-up", history=second_history)), ["reply"])

        self.assertEqual(
            messages_api.calls[0]["messages"],
            [
                {"role": "user", "content": "first chat"},
                {"role": "user", "content": "first follow-up"},
            ],
        )
        self.assertEqual(
            messages_api.calls[1]["messages"],
            [
                {"role": "user", "content": "second chat"},
                {"role": "user", "content": "second follow-up"},
            ],
        )
        self.assertEqual(client.history(), [])
        self.assertEqual(first_history, [{"role": "user", "content": "first chat"}])

    def test_failed_stream_does_not_retain_a_user_turn(self):
        client = _client_with(_FailingMessagesApi())
        client.messages = [{"role": "user", "content": "saved turn"}]

        with self.assertRaisesRegex(RuntimeError, "connection failed"):
            list(client.ask_stream("failed turn"))

        self.assertEqual(client.history(), [{"role": "user", "content": "saved turn"}])

    def test_worker_passes_the_selected_conversation_history(self):
        worker = ClaudeWorker()
        worker.client = Mock()
        worker.client.ask_stream.return_value = iter(["reply"])
        history = ({"role": "assistant", "content": "prior answer"},)

        worker.process(ChatRequest("follow-up", history=history))

        worker.client.ask_stream.assert_called_once_with(
            "follow-up", model=None, history=history, provider_id=None
        )

    def test_worker_passes_the_selected_model(self):
        worker = ClaudeWorker()
        worker.client = Mock()
        worker.client.ask_stream.return_value = iter(["reply"])

        worker.process(ChatRequest("hello", model="claude-opus-4-5"))

        worker.client.ask_stream.assert_called_once_with(
            "hello", model="claude-opus-4-5", history=(), provider_id=None
        )

    def test_worker_passes_the_selected_provider_id(self):
        worker = ClaudeWorker()
        worker.client = Mock()
        worker.client.ask_stream.return_value = iter(["reply"])

        worker.process(ChatRequest("hello", provider_id="google_ai_studio"))

        worker.client.ask_stream.assert_called_once_with(
            "hello", model=None, history=(), provider_id="google_ai_studio"
        )


if __name__ == "__main__":
    unittest.main()
