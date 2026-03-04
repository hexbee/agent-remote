import unittest
from unittest import mock

from gateway.compat import ApiError
from gateway.channels.telegram import TelegramChannel
from gateway.models import ApiResponse

try:
    from http.client import RemoteDisconnected
except ImportError:  # pragma: no cover
    from httplib import BadStatusLine as RemoteDisconnected  # type: ignore


class TelegramChannelTest(unittest.TestCase):
    def test_send_text_retries_transient_disconnect_and_succeeds(self):
        sleeps = []
        channel = TelegramChannel(
            bot_token="token",
            default_chat_id="1000",
            max_message_length=3500,
            send_retry_attempts=3,
            send_retry_delay_seconds=1,
            sleeper=lambda seconds: sleeps.append(seconds),
        )
        success = ApiResponse(
            raw_text='{"ok":true,"result":{"message_id":7,"chat":{"id":1000},"text":"hello"}}',
            data={
                "ok": True,
                "result": {
                    "message_id": 7,
                    "chat": {"id": 1000},
                    "text": "hello",
                },
            },
        )

        with mock.patch.object(
            channel,
            "_post",
            side_effect=[
                RemoteDisconnected("Remote end closed connection without response"),
                success,
            ],
        ) as post:
            result = channel.send_text("1000", "hello")

        self.assertEqual(post.call_count, 2)
        self.assertEqual(sleeps, [1])
        self.assertTrue(result.ok)
        self.assertEqual(result.message_id, 7)
        self.assertEqual(result.chat_id, 1000)
        self.assertEqual(result.text, "hello")

    def test_send_text_raises_api_error_after_exhausting_retries(self):
        sleeps = []
        channel = TelegramChannel(
            bot_token="token",
            default_chat_id="1000",
            max_message_length=3500,
            send_retry_attempts=2,
            send_retry_delay_seconds=1,
            sleeper=lambda seconds: sleeps.append(seconds),
        )

        with mock.patch.object(
            channel,
            "_post",
            side_effect=ApiError("Remote end closed connection without response"),
        ) as post:
            with self.assertRaises(ApiError) as error:
                channel.send_text("1000", "hello")

        self.assertEqual(post.call_count, 2)
        self.assertEqual(sleeps, [1])
        self.assertIn(
            "Telegram sendMessage failed after 2 attempts",
            str(error.exception),
        )

    def test_send_text_does_not_retry_non_retryable_api_error(self):
        channel = TelegramChannel(
            bot_token="token",
            default_chat_id="1000",
            max_message_length=3500,
        )

        with mock.patch.object(
            channel,
            "_post",
            side_effect=ApiError('{"ok":false,"error_code":400,"description":"Bad Request: chat not found"}'),
        ) as post:
            with self.assertRaises(ApiError) as error:
                channel.send_text("1000", "hello")

        self.assertEqual(post.call_count, 1)
        self.assertIn("chat not found", str(error.exception))


if __name__ == "__main__":
    unittest.main()
