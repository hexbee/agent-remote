# Telegram Agent Gateway

`app.py` is the primary entrypoint for this repository. It runs a Telegram bot gateway that can send and receive messages, watch updates, and delegate replies to local agent CLIs such as Claude Code and Codex CLI.

`telegram_claude_gateway.sh` is still included, but it is now a secondary legacy PoC. It remains useful for quick Claude-only experiments and for comparing the newer Python path against the original shell prototype, but it is not the main interface and is not kept at feature parity with `app.py`.

## What It Does

- Sends plain text messages to a Telegram chat
- Receives Telegram updates through long polling
- Watches new messages continuously
- Auto-replies with a simple built-in acknowledgement mode
- Auto-replies with Claude Code through `app.py`
- Auto-replies with Codex CLI through `app.py`
- Responds to a heartbeat keyword without calling a provider CLI

## Requirements

Primary runtime:

- `python3.6+`
- A Telegram bot token and target chat ID
- `claude` CLI if you want to use Claude-backed commands
- `codex` CLI if you want to use Codex-backed commands

Legacy PoC only:

- `bash`
- `curl`
- `jq` for formatted shell output

`app.py` itself depends only on the Python standard library plus whichever external provider CLIs you choose to use.

## Quick Start

Copy `.env.example` to `.env`, then set at least:

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

Run the Python gateway:

```bash
python3 app.py watch-codex-reply
```

or:

```bash
python3 app.py watch-claude-reply
```

## Environment

All variables below are described for `app.py` unless explicitly noted otherwise.

Shared Telegram and reply settings:

- `ENV_FILE`: path to the env file. Default: `./.env` next to `app.py`.
- `TELEGRAM_BOT_TOKEN`: Telegram bot token. Required.
- `TELEGRAM_CHAT_ID`: default Telegram chat ID. Required for send commands.
- `TELEGRAM_MAX_MESSAGE_LENGTH`: max Telegram message length before truncation. Default: `3500`.
- `HEARTBEAT_KEYWORD`: direct reply keyword that skips provider execution. Default: `ping`.
- `HEARTBEAT_RESPONSE`: direct reply text for the heartbeat keyword. Default: `pong`.
- `RAW_OUTPUT=1`: print raw Telegram JSON instead of formatted output.

Claude Code settings for `app.py`:

- `CLAUDE_EXECUTABLE`: Claude executable name. Default: `claude`.
- `CLAUDE_SETTINGS_PATH`: Claude settings file path. Default: `~/.claude/settings.json`.
- `CLAUDE_WORKDIR`: Claude working root. `app.py` uses it as process `cwd` and also passes it via `--add-dir`. Default: repository root.
- `CLAUDE_PENDING_MESSAGE`: placeholder reply sent before Claude finishes. Default: `[CLAUDE CODE] Processing your request...`.

Codex CLI settings for `app.py`:

- `CODEX_EXECUTABLE`: Codex executable name. Default: `codex`.
- `CODEX_MODEL`: Codex model name. Default: `gpt-5.3-codex`.
- `CODEX_REASONING_EFFORT`: Codex reasoning effort. Default: `high`.
- `CODEX_WORKDIR`: working root passed to `codex exec -C`. Default: repository root.
- `CODEX_PENDING_MESSAGE`: placeholder reply sent before Codex finishes. Default: `[CODEX CLI] Processing your request...`.

`app.py` uses a dotenv-style parser, not shell `source` semantics:

- environment variables from the parent process override values from `.env`
- `${VAR}` and `${VAR:-default}` are supported
- bare `$VAR` is treated literally
- single-quoted values stay literal and are not interpolated
- the file is configuration only; shell execution syntax is not supported

Legacy shell PoC support:

- `telegram_claude_gateway.sh` is Claude-only
- it supports the older shared subset such as `ENV_FILE`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `RAW_OUTPUT`, `CLAUDE_SETTINGS_PATH`, `TELEGRAM_MAX_MESSAGE_LENGTH`, `CLAUDE_PENDING_MESSAGE`, `HEARTBEAT_KEYWORD`, and `HEARTBEAT_RESPONSE`
- it does not support `CLAUDE_EXECUTABLE`, `CLAUDE_WORKDIR`, or any `CODEX_*` variables

## `app.py` Commands

```bash
python3 app.py send "hello"
python3 app.py claude-send "hello"
python3 app.py codex-send "hello"
python3 app.py receive
python3 app.py watch
python3 app.py watch-new
python3 app.py watch-reply
python3 app.py watch-claude-reply
python3 app.py watch-codex-reply
python3 app.py webhook-info
python3 app.py delete-webhook
```

## Reply Modes

`watch-reply` watches incoming text messages and sends a lightweight acknowledgement reply:

```text
Rcvd msg from <sender>
```

`watch-claude-reply` skips existing pending updates, then only handles new incoming text messages:

- If the normalized message matches `HEARTBEAT_KEYWORD`, the bot replies with `HEARTBEAT_RESPONSE`
- Otherwise the bot immediately sends `CLAUDE_PENDING_MESSAGE`
- Then it runs Claude and sends the final response as a second message

`app.py` runs Claude with:

```bash
claude -p "$prompt" \
  --settings "$CLAUDE_SETTINGS_PATH" \
  --permission-mode bypassPermissions \
  --dangerously-skip-permissions \
  --add-dir "$CLAUDE_WORKDIR" \
  --no-session-persistence
```

It also starts the Claude process with `cwd="$CLAUDE_WORKDIR"`.

`watch-codex-reply` skips existing pending updates, then only handles new incoming text messages:

- If the normalized message matches `HEARTBEAT_KEYWORD`, the bot replies with `HEARTBEAT_RESPONSE`
- Otherwise the bot immediately sends `CODEX_PENDING_MESSAGE`
- Then it runs Codex and sends the final response as a second message

`app.py` runs Codex with:

```bash
codex exec \
  --dangerously-bypass-approvals-and-sandbox \
  --ephemeral \
  --skip-git-repo-check \
  -m "$CODEX_MODEL" \
  -c "model_reasoning_effort=\"$CODEX_REASONING_EFFORT\"" \
  -C "$CODEX_WORKDIR" \
  -- "$prompt"
```

The `--` separator is intentional. It ensures prompts that start with `-`, such as `--help` or `--fix`, are passed to Codex as user input instead of being parsed as extra CLI flags.

## Legacy PoC

The original shell entrypoint is still available:

```bash
./telegram_claude_gateway.sh watch-claude-reply
```

Use it when you specifically want the old shell-based Claude-only flow. It is not the recommended path for new work.

## Notes

- Non-text messages are ignored in auto-reply modes
- Long Claude or Codex responses are truncated before sending to Telegram
- Terminal output shows both incoming messages and outgoing placeholder or provider replies
- On Windows/Git Bash, formatted incoming-message logs prefer `python` or `python3` over `jq` to avoid Chinese text garbling in the terminal
- Telegram sends message text through stdin instead of shell arguments to avoid UTF-8 encoding errors with non-ASCII content
