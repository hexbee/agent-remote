class ApiResponse(object):
    __slots__ = ("raw_text", "data")

    def __init__(self, raw_text, data):
        self.raw_text = raw_text
        self.data = data


class IncomingMessage(object):
    __slots__ = (
        "update_id",
        "chat_id",
        "sender",
        "text",
        "is_bot",
        "timestamp",
        "raw",
        "has_text_message",
    )

    def __init__(
        self,
        update_id,
        chat_id,
        sender,
        text,
        is_bot,
        timestamp,
        raw,
        has_text_message,
    ):
        self.update_id = update_id
        self.chat_id = chat_id
        self.sender = sender
        self.text = text
        self.is_bot = is_bot
        self.timestamp = timestamp
        self.raw = raw
        self.has_text_message = has_text_message


class SendResult(object):
    __slots__ = ("ok", "message_id", "chat_id", "text", "raw", "raw_text")

    def __init__(self, ok, message_id, chat_id, text, raw, raw_text):
        self.ok = ok
        self.message_id = message_id
        self.chat_id = chat_id
        self.text = text
        self.raw = raw
        self.raw_text = raw_text


class WebhookInfo(object):
    __slots__ = (
        "ok",
        "url",
        "pending_update_count",
        "has_custom_certificate",
        "raw",
        "raw_text",
    )

    def __init__(
        self,
        ok,
        url,
        pending_update_count,
        has_custom_certificate,
        raw,
        raw_text,
    ):
        self.ok = ok
        self.url = url
        self.pending_update_count = pending_update_count
        self.has_custom_certificate = has_custom_certificate
        self.raw = raw
        self.raw_text = raw_text

