import sys
import time

from gateway.compat import CommandError
from gateway.formatting import (
    extract_next_offset,
    format_outgoing_log,
    format_send_result,
    format_updates,
    format_webhook_info,
    normalize_heartbeat_text,
)


class GatewayApplication(object):
    def __init__(self, config, channel, runner, stdout=None, stderr=None, sleeper=None):
        self.config = config
        self.channel = channel
        self.runner = runner
        self.stdout = stdout or sys.stdout
        self.stderr = stderr or sys.stderr
        self.sleeper = sleeper or time.sleep

    def send(self, text):
        self._require_arg(text, "message text")
        result = self.channel.send_text(self.channel.default_chat_id, text)
        self._write_output(
            result.raw_text if self.config.raw_output else format_send_result(result)
        )

    def claude_send(self, prompt):
        self._require_arg(prompt, "prompt")
        reply = self.runner.run(prompt)
        result = self.channel.send_text(self.channel.default_chat_id, reply)
        self._write_output(
            result.raw_text if self.config.raw_output else format_send_result(result)
        )

    def receive(self):
        self.channel.delete_webhook(drop_pending_updates=False)
        response = self.channel.get_updates(timeout=10)
        self._write_updates(response)

    def watch(self):
        self._watch_loop(initial_offset=None, reply_handler=None)

    def watch_new(self):
        self._watch_loop(initial_offset=self._get_next_offset(), reply_handler=None)

    def watch_reply(self):
        self._watch_loop(initial_offset=None, reply_handler=self._basic_reply_handler)

    def watch_claude_reply(self):
        self._watch_loop(
            initial_offset=self._get_next_offset(),
            reply_handler=self._claude_reply_handler,
        )

    def webhook_info(self):
        info = self.channel.get_webhook_info()
        self._write_output(
            info.raw_text if self.config.raw_output else format_webhook_info(info)
        )

    def delete_webhook(self):
        response = self.channel.delete_webhook(drop_pending_updates=False)
        self._write_output(response.raw_text)

    def _watch_loop(self, initial_offset, reply_handler):
        offset = initial_offset
        self.channel.delete_webhook(drop_pending_updates=False)

        while True:
            try:
                response = self.channel.get_updates(timeout=30, offset=offset)
                self._write_updates(response)
                offset, batch_error = self._consume_response(
                    response,
                    offset,
                    reply_handler,
                )
                if batch_error is not None:
                    self._write_error(str(batch_error))
                    self.sleeper(1)
            except KeyboardInterrupt:
                raise
            except Exception as error:
                self._write_error(str(error))
                self.sleeper(1)

    def _consume_response(self, response, offset, reply_handler):
        next_offset = self._next_offset_after_response(response, offset)
        if reply_handler is None:
            return next_offset, None

        next_offset = offset
        for message in self.channel.iter_messages(response):
            try:
                reply_handler(message)
            except Exception as error:
                return next_offset, self._format_message_error(message, error)
            next_offset = self._advance_offset(next_offset, message.update_id)

        return self._next_offset_after_response(response, next_offset), None

    def _basic_reply_handler(self, message):
        if message.is_bot or not message.has_text_message or not message.chat_id:
            return

        self.channel.send_text(
            message.chat_id,
            "Rcvd msg from {}".format(message.sender),
        )

    def _claude_reply_handler(self, message):
        if message.is_bot or not message.has_text_message or not message.chat_id:
            return

        normalized_keyword = normalize_heartbeat_text(self.config.heartbeat_keyword)
        normalized_text = normalize_heartbeat_text(message.text)
        if normalized_text == normalized_keyword:
            self.channel.send_text(message.chat_id, self.config.heartbeat_response)
            self._log_sent_message(
                message.chat_id,
                message.sender,
                "heartbeat",
                self.config.heartbeat_response,
            )
            return

        self.channel.send_text(message.chat_id, self.config.claude_pending_message)
        self._log_sent_message(
            message.chat_id,
            message.sender,
            "placeholder",
            self.config.claude_pending_message,
        )

        try:
            reply_text = self.runner.run(message.text)
            self.channel.send_text(message.chat_id, reply_text)
        except Exception as error:
            self._write_error(
                self._format_message_error(
                    message,
                    error,
                    prefix="Failed to complete Claude reply",
                )
            )
            return

        self._log_sent_message(
            message.chat_id,
            message.sender,
            "claude",
            reply_text,
        )

    def _get_next_offset(self):
        self.channel.delete_webhook(drop_pending_updates=False)
        response = self.channel.get_updates(timeout=1)
        next_offset = extract_next_offset(response.data)
        if next_offset is None:
            return None
        return next_offset + 1

    def _next_offset_after_response(self, response, offset):
        next_offset = extract_next_offset(response.data)
        if next_offset is None:
            return offset
        return self._advance_offset(offset, next_offset)

    def _advance_offset(self, offset, update_id):
        if not isinstance(update_id, int):
            return offset
        candidate = update_id + 1
        if offset is None or candidate > offset:
            return candidate
        return offset

    def _format_message_error(self, message, error, prefix="Failed to process update"):
        if isinstance(message.update_id, int):
            return "{} {}: {}".format(prefix, message.update_id, error)
        return "{}: {}".format(prefix, error)

    def _log_sent_message(self, chat_id, sender, kind, text):
        if self.config.raw_output:
            return

        self._write_output(
            format_outgoing_log(
                chat_id=chat_id,
                sender=sender,
                kind=kind,
                text=text,
                limit=self.config.telegram_max_message_length,
            )
        )

    def _write_updates(self, response):
        if self.config.raw_output:
            self._write_output(response.raw_text)
            return

        formatted = format_updates(response.data)
        if formatted:
            self._write_output(formatted)

    def _write_output(self, text):
        if text == "":
            return
        self.stdout.write(text)
        if not text.endswith("\n"):
            self.stdout.write("\n")
        self.stdout.flush()

    def _write_error(self, text):
        self.stderr.write(text)
        if not text.endswith("\n"):
            self.stderr.write("\n")
        self.stderr.flush()

    def _require_arg(self, value, name):
        if value:
            return
        raise CommandError("Missing {}".format(name))
