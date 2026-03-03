# Telegram Claude Gateway

`telegram_claude_gateway.sh` is a small Telegram bot gateway for testing Telegram Bot API flows and forwarding incoming messages to Claude Code.

## What It Does

- Sends plain text messages to a Telegram chat
- Receives Telegram updates through long polling
- Watches new messages continuously
- Auto-replies with a simple built-in acknowledgement mode
- Auto-replies with Claude output
- Responds to a heartbeat keyword without calling Claude

## Requirements

- `bash`
- `curl`
- `jq` for formatted output and auto-reply modes
- `python` or `python3` recommended for reliable formatted update output on Windows/Git Bash
- `claude` CLI for Claude-backed commands
- A Telegram bot token and target chat ID

## Environment

Create a `.env` file next to the script:

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

Supported environment variables:

- `ENV_FILE`: path to the env file. Default: `./.env` next to the script.
- `CLAUDE_SETTINGS_PATH`: Claude settings file path. Default: `~/.claude/settings.json`.
- `TELEGRAM_MAX_MESSAGE_LENGTH`: max Telegram message length before truncation. Default: `3500`.
- `CLAUDE_PENDING_MESSAGE`: placeholder reply sent before Claude finishes. Default: `Processing your request...`.
- `HEARTBEAT_KEYWORD`: keyword that skips Claude and returns a direct response. Default: `ping`.
- `HEARTBEAT_RESPONSE`: direct response for the heartbeat keyword. Default: `pong`.
- `RAW_OUTPUT=1`: prints raw Telegram JSON instead of formatted output.

## Commands

```bash
./telegram_claude_gateway.sh send "hello"
./telegram_claude_gateway.sh claude-send "hello"
./telegram_claude_gateway.sh receive
./telegram_claude_gateway.sh watch
./telegram_claude_gateway.sh watch-new
./telegram_claude_gateway.sh watch-reply
./telegram_claude_gateway.sh watch-claude-reply
./telegram_claude_gateway.sh webhook-info
./telegram_claude_gateway.sh delete-webhook
```

## Claude Mode

`watch-claude-reply` skips existing pending updates, then only handles new incoming text messages.

Behavior:

- If the normalized message matches `HEARTBEAT_KEYWORD`, the bot replies with `HEARTBEAT_RESPONSE`
- Otherwise the bot immediately sends `CLAUDE_PENDING_MESSAGE`
- Then it runs Claude and sends the final response as a second message

Claude is called with:

```bash
claude -p "$prompt" \
  --settings "$CLAUDE_SETTINGS_PATH" \
  --permission-mode bypassPermissions \
  --dangerously-skip-permissions \
  --add-dir "$ROOT_DIR" \
  --no-session-persistence
```

## Example

Run the gateway with a custom Claude settings file:

```bash
CLAUDE_SETTINGS_PATH=~/.claude/k2.settings.json ./telegram_claude_gateway.sh watch-claude-reply
```

Example heartbeat:

```text
User: ping
Bot: pong
```

## Auto Reply Mode

`watch-reply` watches incoming text messages and sends a lightweight acknowledgement reply:

```text
Rcvd msg from <sender>
```

It does not echo the original message text back to Telegram. This avoids UTF-8 issues seen in some Windows/Git Bash setups when non-ASCII text is re-sent through shell argument encoding.

## Notes

- Non-text messages are ignored in auto-reply modes
- Long Claude responses are truncated before sending to Telegram
- Terminal output shows both incoming messages and outgoing placeholder or Claude replies
- On Windows/Git Bash, formatted incoming-message logs prefer `python` or `python3` over `jq` to avoid Chinese text garbling in the terminal
- Telegram sends message text through stdin instead of shell arguments to avoid UTF-8 encoding errors with non-ASCII content
