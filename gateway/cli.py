import os
import sys

from gateway.channels import create_channel
from gateway.compat import CommandError, ConfigError, GatewayError
from gateway.config import AppConfig
from gateway.core import GatewayApplication
from gateway.runners import create_runner


def usage(program_name):
    return """Usage:
  {0} send "hello"
  {0} claude-send "hello"
  {0} codex-send "hello"
  {0} receive
  {0} watch
  {0} watch-new
  {0} watch-reply
  {0} watch-claude-reply
  {0} watch-codex-reply
  {0} webhook-info
  {0} delete-webhook

Commands:
  send            Send a text message to TELEGRAM_CHAT_ID
  claude-send     Run Claude with the prompt and send the reply to TELEGRAM_CHAT_ID
  codex-send      Run Codex CLI with the prompt and send the reply to TELEGRAM_CHAT_ID
  receive         Fetch pending updates once
  watch           Long-poll for new messages continuously
  watch-new       Skip existing pending updates, then watch only new messages
  watch-reply     Watch messages and auto-reply to text messages
  watch-claude-reply
                  Skip existing pending updates, then use Claude to auto-reply to new text messages
  watch-codex-reply
                  Skip existing pending updates, then use Codex CLI to auto-reply to new text messages
  webhook-info    Show current webhook status
  delete-webhook  Remove webhook so getUpdates can work

Debug:
  RAW_OUTPUT=1    Print raw JSON responses instead of formatted output

Environment:
  ENV_FILE                   Path to the env file (default: ./.env next to the script)
  CLAUDE_EXECUTABLE          Claude executable name (default: claude)
  CLAUDE_SETTINGS_PATH       Claude settings path (default: ~/.claude/settings.json)
  CLAUDE_WORKDIR             Claude working root for cwd and --add-dir
                             (default: repository root)
  CLAUDE_NO_SESSION_PERSISTENCE
                             Set to 1 to append --no-session-persistence
                             (default: 0)
  CODEX_EXECUTABLE           Codex CLI executable name (default: codex)
  CODEX_MODEL                Codex model name (default: gpt-5.3-codex)
  CODEX_REASONING_EFFORT     Codex reasoning effort for model config
                             (default: high)
  CODEX_WORKDIR              Codex working root passed to --cd/-C
                             (default: repository root)
  TELEGRAM_MAX_MESSAGE_LENGTH
                             Max Telegram message length before truncation (default: 3500)
  WATCH_POLL_TIMEOUT         Telegram getUpdates long-poll seconds for watch commands
                             Lower values make Ctrl+C more responsive (default: 10)
  CLAUDE_PENDING_MESSAGE     Placeholder reply before Claude finishes
                             (default: [CLAUDE CODE] Processing your request...)
  CODEX_PENDING_MESSAGE      Placeholder reply before Codex finishes
                             (default: [CODEX CLI] Processing your request...)
  HEARTBEAT_KEYWORD          Direct reply keyword that skips Claude or Codex
                             (default: ping)
  HEARTBEAT_RESPONSE         Direct reply text for heartbeat keyword (default: pong)
""".format(program_name)


def run(argv=None, stdout=None, stderr=None, root_dir=None):
    if argv is None:
        argv = sys.argv

    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    program_name = os.path.basename(argv[0]) or "app.py"
    command = argv[1] if len(argv) > 1 else ""

    usage_text = usage(program_name)

    if command in ("", "-h", "--help", "help"):
        stdout.write(usage_text)
        if not usage_text.endswith("\n"):
            stdout.write("\n")
        stdout.flush()
        return 0

    if command not in (
        "send",
        "claude-send",
        "codex-send",
        "receive",
        "watch",
        "watch-new",
        "watch-reply",
        "watch-claude-reply",
        "watch-codex-reply",
        "webhook-info",
        "delete-webhook",
    ):
        stderr.write("Unknown command: {}\n\n".format(command))
        stdout.write(usage_text)
        if not usage_text.endswith("\n"):
            stdout.write("\n")
        stderr.flush()
        stdout.flush()
        return 1

    try:
        if root_dir is None:
            root_dir = os.path.dirname(os.path.abspath(argv[0]))
        config = AppConfig.load(root_dir)
        application = GatewayApplication(
            config=config,
            channel=create_channel("telegram", config),
            runner=create_runner("claude_cli", config),
            codex_runner=create_runner("codex_cli", config),
            stdout=stdout,
            stderr=stderr,
        )

        if command == "send":
            application.send(argv[2] if len(argv) > 2 else "")
        elif command == "claude-send":
            application.claude_send(argv[2] if len(argv) > 2 else "")
        elif command == "codex-send":
            application.codex_send(argv[2] if len(argv) > 2 else "")
        elif command == "receive":
            application.receive()
        elif command == "watch":
            application.watch()
        elif command == "watch-new":
            application.watch_new()
        elif command == "watch-reply":
            application.watch_reply()
        elif command == "watch-claude-reply":
            application.watch_claude_reply()
        elif command == "watch-codex-reply":
            application.watch_codex_reply()
        elif command == "webhook-info":
            application.webhook_info()
        elif command == "delete-webhook":
            application.delete_webhook()
        return 0
    except KeyboardInterrupt:
        stderr.write("\n")
        stderr.flush()
        return 130
    except (CommandError, ConfigError) as error:
        stderr.write(str(error))
        if not str(error).endswith("\n"):
            stderr.write("\n")
        stderr.flush()
        return 1
    except GatewayError as error:
        stderr.write(str(error))
        if not str(error).endswith("\n"):
            stderr.write("\n")
        stderr.flush()
        return 1
