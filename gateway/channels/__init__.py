from gateway.channels.telegram import TelegramChannel


def create_channel(name, config):
    if name != "telegram":
        raise ValueError("Unsupported channel: {}".format(name))

    return TelegramChannel(
        bot_token=config.telegram_bot_token,
        default_chat_id=config.telegram_chat_id,
        max_message_length=config.telegram_max_message_length,
    )

