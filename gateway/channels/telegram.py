import json
import time

try:
    import socket
except ImportError:  # pragma: no cover
    socket = None  # type: ignore

try:
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
except ImportError:  # pragma: no cover
    from urllib2 import HTTPError, URLError, Request, urlopen  # type: ignore
    from urllib import urlencode  # type: ignore

from gateway.compat import ApiError
from gateway.formatting import limit_message_length
from gateway.models import ApiResponse, IncomingMessage, SendResult, WebhookInfo


class TelegramChannel(object):
    def __init__(
        self,
        bot_token,
        default_chat_id,
        max_message_length,
        send_retry_attempts=3,
        send_retry_delay_seconds=1,
        sleeper=None,
    ):
        self.bot_token = bot_token
        self.default_chat_id = default_chat_id
        self.max_message_length = max_message_length
        self.send_retry_attempts = max(int(send_retry_attempts), 1)
        self.send_retry_delay_seconds = max(float(send_retry_delay_seconds), 0.0)
        self.sleeper = sleeper or time.sleep
        self.api_base = "https://api.telegram.org/bot{}".format(bot_token)

    def send_text(self, chat_id, text):
        limited_text = limit_message_length(text, self.max_message_length)
        payload = {
            "chat_id": chat_id,
            "text": limited_text,
        }
        response = self._post_with_send_retries(
            "sendMessage",
            payload,
        )
        result = response.data.get("result") or {}
        chat = result.get("chat") or {}
        return SendResult(
            ok=bool(response.data.get("ok")),
            message_id=result.get("message_id"),
            chat_id=chat.get("id"),
            text=result.get("text") or "",
            raw=response.data,
            raw_text=response.raw_text,
        )

    def delete_webhook(self, drop_pending_updates=False):
        return self._post(
            "deleteWebhook",
            {"drop_pending_updates": "true" if drop_pending_updates else "false"},
        )

    def get_webhook_info(self):
        response = self._post("getWebhookInfo", {})
        result = response.data.get("result") or {}
        return WebhookInfo(
            ok=bool(response.data.get("ok")),
            url=result.get("url") or "",
            pending_update_count=result.get("pending_update_count", 0),
            has_custom_certificate=result.get("has_custom_certificate", False),
            raw=response.data,
            raw_text=response.raw_text,
        )

    def get_updates(self, timeout, offset=None):
        payload = {
            "allowed_updates": json.dumps(["message"]),
            "timeout": str(timeout),
        }
        if offset is not None:
            payload["offset"] = str(offset)
        request_timeout = max(int(timeout) + 10, 30)
        return self._post("getUpdates", payload, request_timeout=request_timeout)

    def iter_messages(self, response):
        messages = []
        for item in response.data.get("result", []):
            if not isinstance(item, dict):
                continue

            message = item.get("message")
            if not isinstance(message, dict):
                continue

            sender_info = message.get("from") or {}
            sender = sender_info.get("username") or sender_info.get("first_name") or "unknown"
            raw_text = message.get("text")
            caption = message.get("caption")
            chat = message.get("chat") or {}
            chat_id = chat.get("id")

            messages.append(
                IncomingMessage(
                    update_id=item.get("update_id"),
                    chat_id="" if chat_id is None else str(chat_id),
                    sender=sender,
                    text=raw_text if raw_text is not None else (caption or ""),
                    is_bot=bool(sender_info.get("is_bot")),
                    timestamp=message.get("date"),
                    raw=item,
                    has_text_message=isinstance(raw_text, str) and raw_text != "",
                )
            )
        return messages

    def _post_with_send_retries(self, method, payload):
        attempt = 0
        while True:
            attempt += 1
            try:
                return self._post(method, payload)
            except Exception as error:
                if not self._is_retryable_send_error(error):
                    raise
                if attempt >= self.send_retry_attempts:
                    raise ApiError(
                        "Telegram {} failed after {} attempts: {}".format(
                            method,
                            self.send_retry_attempts,
                            error,
                        )
                    )
                if self.send_retry_delay_seconds > 0:
                    self.sleeper(self.send_retry_delay_seconds)

    def _post(self, method, payload, request_timeout=30):
        data = urlencode(payload).encode("utf-8")
        request = Request(
            "{}/{}".format(self.api_base, method),
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        try:
            response = urlopen(request, timeout=request_timeout)
            raw_bytes = response.read()
        except HTTPError as error:
            body = error.read().decode("utf-8", "replace")
            raise ApiError(body or str(error))
        except URLError as error:
            raise ApiError(str(error))

        raw_text = raw_bytes.decode("utf-8", "replace")
        try:
            data = json.loads(raw_text)
        except ValueError as error:
            raise ApiError("Failed to parse Telegram response: {}".format(error))

        if not isinstance(data, dict):
            raise ApiError("Unexpected Telegram response payload")

        return ApiResponse(raw_text=raw_text, data=data)

    def _is_retryable_send_error(self, error):
        if isinstance(error, HTTPError):
            return False

        if socket is not None and isinstance(error, socket.timeout):
            return True

        if isinstance(error, URLError):
            return True

        if isinstance(error, ApiError):
            lowered = str(error).lower()
            return any(
                fragment in lowered
                for fragment in (
                    "remote end closed connection without response",
                    "timed out",
                    "connection aborted",
                    "connection reset",
                    "temporarily unavailable",
                    "connection refused",
                )
            )

        return any(
            fragment in str(error).lower()
            for fragment in (
                "remote end closed connection without response",
                "timed out",
                "connection aborted",
                "connection reset",
                "temporarily unavailable",
                "connection refused",
            )
        )
