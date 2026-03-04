from datetime import datetime, timedelta, timezone


DISPLAY_TIMEZONE = timezone(timedelta(hours=8))
TRUNCATION_SUFFIX = "\n\n[truncated]"


def limit_message_length(text, limit):
    if len(text) <= limit:
        return text

    if limit <= len(TRUNCATION_SUFFIX):
        return text[:limit]

    return text[: limit - len(TRUNCATION_SUFFIX)] + TRUNCATION_SUFFIX


def preview_text(text, preview_limit=120):
    normalized = text.replace("\n", " ").replace("\r", " ")
    if len(normalized) <= preview_limit:
        return normalized
    return normalized[:preview_limit] + "..."


def normalize_heartbeat_text(text):
    return (text or "").strip().lower()


def extract_next_offset(response_data):
    next_offset = None
    for item in response_data.get("result", []):
        if not isinstance(item, dict):
            continue
        update_id = item.get("update_id")
        if not isinstance(update_id, int):
            continue
        if next_offset is None or update_id > next_offset:
            next_offset = update_id
    return next_offset


def format_updates(response_data):
    lines = []
    for item in response_data.get("result", []):
        if not isinstance(item, dict):
            continue
        message = item.get("message")
        if not isinstance(message, dict):
            continue

        timestamp = message.get("date", 0)
        try:
            dt = datetime.fromtimestamp(int(timestamp), tz=DISPLAY_TIMEZONE)
        except Exception:
            dt = datetime.fromtimestamp(0, tz=DISPLAY_TIMEZONE)

        sender_info = message.get("from") or {}
        sender = sender_info.get("username") or sender_info.get("first_name") or "unknown"
        text = message.get("text") or message.get("caption") or "<non-text message>"
        text = text.replace("\n", "\\n")
        lines.append("{:%Y-%m-%d %H:%M:%S} {}: {}".format(dt, sender, text))
    return "\n".join(lines)


def format_send_result(result):
    if not result.ok:
        return result.raw_text

    text = (result.text or "").replace("\n", "\\n")
    return "sent message_id={} chat_id={} text={}".format(
        result.message_id,
        result.chat_id,
        text,
    )


def format_webhook_info(info):
    if not info.ok:
        return info.raw_text

    return "url={} pending_update_count={} has_custom_certificate={}".format(
        info.url or "",
        info.pending_update_count,
        str(bool(info.has_custom_certificate)).lower(),
    )


def format_outgoing_log(chat_id, sender, kind, text, limit):
    target = chat_id
    if sender:
        target = "{} ({})".format(sender, chat_id)
    return "-> {} [{}]: {}".format(
        target,
        kind,
        preview_text(limit_message_length(text, limit)),
    )

