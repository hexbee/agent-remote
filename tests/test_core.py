import io
import unittest

from gateway.compat import ApiError
from gateway.core import GatewayApplication
from gateway.models import ApiResponse, IncomingMessage, SendResult, WebhookInfo


class DummyConfig(object):
    raw_output = False
    heartbeat_keyword = "ping"
    heartbeat_response = "pong"
    claude_pending_message = "[CLAUDE CODE] Processing your request..."
    codex_pending_message = "[CODEX CLI] Processing your request..."
    telegram_max_message_length = 3500
    watch_poll_timeout = 10


class FakeRunner(object):
    def __init__(self, reply):
        self.reply = reply
        self.prompts = []

    def run(self, prompt):
        self.prompts.append(prompt)
        return self.reply


class FakeChannel(object):
    default_chat_id = "1000"

    def __init__(self):
        self.sent = []
        self.deleted = 0
        self.update_response = ApiResponse('{"ok":true,"result":[]}', {"result": []})
        self.fail_on_text = set()

    def send_text(self, chat_id, text):
        if text in self.fail_on_text:
            raise RuntimeError("send failed for {}".format(text))
        self.sent.append((chat_id, text))
        return SendResult(
            ok=True,
            message_id=len(self.sent),
            chat_id=chat_id,
            text=text,
            raw={"ok": True},
            raw_text='{"ok":true}',
        )

    def delete_webhook(self, drop_pending_updates=False):
        self.deleted += 1
        return ApiResponse('{"ok":true}', {"ok": True})

    def get_updates(self, timeout, offset=None):
        return self.update_response

    def get_webhook_info(self):
        return WebhookInfo(
            ok=True,
            url="",
            pending_update_count=0,
            has_custom_certificate=False,
            raw={"ok": True},
            raw_text='{"ok":true}',
        )

    def iter_messages(self, response):
        return response.data.get("messages", [])


class GatewayApplicationTest(unittest.TestCase):
    def test_claude_reply_handler_short_circuits_heartbeat(self):
        stdout = io.StringIO()
        channel = FakeChannel()
        runner = FakeRunner("unused")
        app = GatewayApplication(DummyConfig(), channel, runner, stdout=stdout)

        response = ApiResponse(
            "",
            {
                "messages": [
                    IncomingMessage(
                        update_id=1,
                        chat_id="2000",
                        sender="alice",
                        text="  PING  ",
                        is_bot=False,
                        timestamp=0,
                        raw={},
                        has_text_message=True,
                    )
                ]
            },
        )

        app._claude_reply_handler(response.data["messages"][0])

        self.assertEqual(channel.sent, [("2000", "pong")])
        self.assertEqual(runner.prompts, [])
        self.assertIn("-> alice (2000) [heartbeat]: pong", stdout.getvalue())

    def test_codex_reply_handler_short_circuits_heartbeat(self):
        stdout = io.StringIO()
        channel = FakeChannel()
        claude_runner = FakeRunner("unused")
        codex_runner = FakeRunner("unused")
        app = GatewayApplication(
            DummyConfig(),
            channel,
            claude_runner,
            codex_runner=codex_runner,
            stdout=stdout,
        )
        message = IncomingMessage(
            update_id=6,
            chat_id="2003",
            sender="erin",
            text="  PING  ",
            is_bot=False,
            timestamp=0,
            raw={},
            has_text_message=True,
        )

        app._codex_reply_handler(message)

        self.assertEqual(channel.sent, [("2003", "pong")])
        self.assertEqual(codex_runner.prompts, [])
        self.assertEqual(claude_runner.prompts, [])
        self.assertIn("-> erin (2003) [heartbeat]: pong", stdout.getvalue())

    def test_claude_reply_handler_sends_placeholder_then_runner_output(self):
        stdout = io.StringIO()
        channel = FakeChannel()
        runner = FakeRunner("final reply")
        app = GatewayApplication(DummyConfig(), channel, runner, stdout=stdout)

        response = ApiResponse(
            "",
            {
                "messages": [
                    IncomingMessage(
                        update_id=2,
                        chat_id="2001",
                        sender="bob",
                        text="hello",
                        is_bot=False,
                        timestamp=0,
                        raw={},
                        has_text_message=True,
                    )
                ]
            },
        )

        app._claude_reply_handler(response.data["messages"][0])

        self.assertEqual(
            channel.sent,
            [
                ("2001", "[CLAUDE CODE] Processing your request..."),
                ("2001", "final reply"),
            ],
        )
        self.assertEqual(runner.prompts, ["hello"])
        self.assertIn(
            "[placeholder]: [CLAUDE CODE] Processing your request...",
            stdout.getvalue(),
        )
        self.assertIn("[claude]: final reply", stdout.getvalue())

    def test_codex_reply_handler_sends_placeholder_then_runner_output(self):
        stdout = io.StringIO()
        channel = FakeChannel()
        claude_runner = FakeRunner("unused")
        codex_runner = FakeRunner("codex reply")
        app = GatewayApplication(
            DummyConfig(),
            channel,
            claude_runner,
            codex_runner=codex_runner,
            stdout=stdout,
        )
        message = IncomingMessage(
            update_id=3,
            chat_id="2002",
            sender="dave",
            text="solve this",
            is_bot=False,
            timestamp=0,
            raw={},
            has_text_message=True,
        )

        app._codex_reply_handler(message)

        self.assertEqual(
            channel.sent,
            [
                ("2002", "[CODEX CLI] Processing your request..."),
                ("2002", "codex reply"),
            ],
        )
        self.assertEqual(codex_runner.prompts, ["solve this"])
        self.assertEqual(claude_runner.prompts, [])
        self.assertIn(
            "[placeholder]: [CODEX CLI] Processing your request...",
            stdout.getvalue(),
        )
        self.assertIn("[codex]: codex reply", stdout.getvalue())

    def test_codex_send_uses_codex_runner_output(self):
        stdout = io.StringIO()
        channel = FakeChannel()
        claude_runner = FakeRunner("unused")
        codex_runner = FakeRunner("codex send reply")
        app = GatewayApplication(
            DummyConfig(),
            channel,
            claude_runner,
            codex_runner=codex_runner,
            stdout=stdout,
        )

        app.codex_send("describe the repo")

        self.assertEqual(channel.sent, [("1000", "codex send reply")])
        self.assertEqual(codex_runner.prompts, ["describe the repo"])
        self.assertEqual(claude_runner.prompts, [])
        self.assertIn("sent message_id=1 chat_id=1000 text=codex send reply", stdout.getvalue())

    def test_get_next_offset_returns_next_update_id(self):
        channel = FakeChannel()
        runner = FakeRunner("unused")
        channel.update_response = ApiResponse(
            "",
            {
                "result": [
                    {"update_id": 8},
                    {"update_id": 11},
                ]
            },
        )
        app = GatewayApplication(DummyConfig(), channel, runner)

        self.assertEqual(app._get_next_offset(), 12)
        self.assertEqual(channel.deleted, 1)

    def test_consume_response_advances_offset_after_successful_message_before_failure(self):
        channel = FakeChannel()
        channel.fail_on_text.add("Rcvd msg from bob")
        runner = FakeRunner("unused")
        app = GatewayApplication(DummyConfig(), channel, runner, stderr=io.StringIO())
        response = ApiResponse(
            "",
            {
                "result": [
                    {"update_id": 1},
                    {"update_id": 2},
                ],
                "messages": [
                    IncomingMessage(
                        update_id=1,
                        chat_id="3000",
                        sender="alice",
                        text="hello",
                        is_bot=False,
                        timestamp=0,
                        raw={},
                        has_text_message=True,
                    ),
                    IncomingMessage(
                        update_id=2,
                        chat_id="3001",
                        sender="bob",
                        text="hi",
                        is_bot=False,
                        timestamp=0,
                        raw={},
                        has_text_message=True,
                    ),
                ],
            },
        )

        next_offset, error = app._consume_response(
            response,
            None,
            app._basic_reply_handler,
        )

        self.assertEqual(next_offset, 2)
        self.assertEqual(channel.sent, [("3000", "Rcvd msg from alice")])
        self.assertEqual(str(error), "Failed to process update 2: send failed for Rcvd msg from bob")

    def test_claude_reply_handler_logs_and_swallows_final_send_failure_after_placeholder(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        channel = FakeChannel()
        channel.fail_on_text.add("final reply")
        runner = FakeRunner("final reply")
        app = GatewayApplication(DummyConfig(), channel, runner, stdout=stdout, stderr=stderr)
        message = IncomingMessage(
            update_id=5,
            chat_id="4000",
            sender="carol",
            text="hello",
            is_bot=False,
            timestamp=0,
            raw={},
            has_text_message=True,
        )

        app._claude_reply_handler(message)

        self.assertEqual(channel.sent, [("4000", "[CLAUDE CODE] Processing your request...")])
        self.assertIn(
            "[placeholder]: [CLAUDE CODE] Processing your request...",
            stdout.getvalue(),
        )
        self.assertIn("Failed to complete Claude reply 5: send failed for final reply", stderr.getvalue())

    def test_watch_loop_exits_on_get_updates_conflict(self):
        stderr = io.StringIO()
        channel = FakeChannel()
        runner = FakeRunner("unused")
        sleeper_calls = []

        def raise_conflict(timeout, offset=None):
            raise ApiError(
                '{"ok":false,"error_code":409,"description":"Conflict: terminated by other getUpdates request; make sure that only one bot instance is running"}'
            )

        channel.get_updates = raise_conflict
        app = GatewayApplication(
            DummyConfig(),
            channel,
            runner,
            stderr=stderr,
            sleeper=lambda seconds: sleeper_calls.append(seconds),
        )

        app.watch_codex_reply()

        self.assertEqual(channel.deleted, 1)
        self.assertEqual(sleeper_calls, [])
        self.assertIn(
            "Telegram getUpdates conflict: another gateway instance is already polling this bot token.",
            stderr.getvalue(),
        )

    def test_watch_reply_uses_configured_poll_timeout(self):
        channel = FakeChannel()
        runner = FakeRunner("unused")
        app = GatewayApplication(DummyConfig(), channel, runner)
        observed = []

        def interrupting_get_updates(timeout, offset=None):
            observed.append((timeout, offset))
            raise KeyboardInterrupt()

        channel.get_updates = interrupting_get_updates

        with self.assertRaises(KeyboardInterrupt):
            app.watch_reply()

        self.assertEqual(observed, [(10, None)])


if __name__ == "__main__":
    unittest.main()
