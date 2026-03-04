import os
import tempfile
import unittest

from gateway.compat import ConfigError
from gateway.config import AppConfig, load_env_file


class AppConfigTest(unittest.TestCase):
    def test_process_environment_overrides_dotenv_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = os.path.join(temp_dir, ".env")
            with open(env_path, "w") as handle:
                handle.write("TELEGRAM_BOT_TOKEN=file-token\n")
                handle.write("TELEGRAM_CHAT_ID=12345\n")
                handle.write("CLAUDE_SETTINGS_PATH=${HOME}/.claude/test.json\n")
                handle.write("TELEGRAM_MAX_MESSAGE_LENGTH=42\n")
                handle.write('CLAUDE_PENDING_MESSAGE="Please wait"\n')
                handle.write("HEARTBEAT_KEYWORD=PING\n")
                handle.write("HEARTBEAT_RESPONSE=PONG\n")

            config = AppConfig.load(
                temp_dir,
                environ={
                    "HOME": "/tmp/example-home",
                    "TELEGRAM_BOT_TOKEN": "env-token",
                    "HEARTBEAT_RESPONSE": "ENV-PONG",
                },
            )

            self.assertEqual(config.telegram_bot_token, "env-token")
            self.assertEqual(config.telegram_chat_id, "12345")
            self.assertEqual(config.telegram_max_message_length, 42)
            self.assertEqual(config.watch_poll_timeout, 10)
            self.assertEqual(config.claude_executable, "claude")
            self.assertEqual(
                config.claude_settings_path,
                "/tmp/example-home/.claude/test.json",
            )
            self.assertEqual(config.claude_workdir, temp_dir)
            self.assertFalse(config.claude_no_session_persistence)
            self.assertEqual(config.codex_executable, "codex")
            self.assertEqual(config.codex_model, "gpt-5.3-codex")
            self.assertEqual(config.codex_reasoning_effort, "high")
            self.assertEqual(config.codex_workdir, temp_dir)
            self.assertEqual(config.claude_pending_message, "Please wait")
            self.assertEqual(
                config.codex_pending_message,
                "[CODEX CLI] Processing your request...",
            )
            self.assertEqual(config.heartbeat_keyword, "PING")
            self.assertEqual(config.heartbeat_response, "ENV-PONG")

    def test_codex_env_overrides_defaults_and_resolves_relative_workdir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = os.path.join(temp_dir, ".env")
            with open(env_path, "w") as handle:
                handle.write("TELEGRAM_BOT_TOKEN=file-token\n")
                handle.write("TELEGRAM_CHAT_ID=12345\n")
                handle.write("CODEX_EXECUTABLE=codex-beta\n")
                handle.write("CODEX_MODEL=gpt-5.4-codex\n")
                handle.write("CODEX_REASONING_EFFORT=medium\n")
                handle.write("CODEX_WORKDIR=workspace\n")
                handle.write("WATCH_POLL_TIMEOUT=2\n")
                handle.write('CODEX_PENDING_MESSAGE="[CODEX CLI] Working..."\n')

            os.mkdir(os.path.join(temp_dir, "workspace"))

            config = AppConfig.load(temp_dir, environ={"HOME": "/tmp/example-home"})

            self.assertEqual(config.codex_executable, "codex-beta")
            self.assertEqual(config.codex_model, "gpt-5.4-codex")
            self.assertEqual(config.codex_reasoning_effort, "medium")
            self.assertEqual(
                config.codex_workdir,
                os.path.join(temp_dir, "workspace"),
            )
            self.assertEqual(config.watch_poll_timeout, 2)
            self.assertEqual(config.codex_pending_message, "[CODEX CLI] Working...")

    def test_claude_env_overrides_defaults_and_resolves_relative_workdir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = os.path.join(temp_dir, ".env")
            with open(env_path, "w") as handle:
                handle.write("TELEGRAM_BOT_TOKEN=file-token\n")
                handle.write("TELEGRAM_CHAT_ID=12345\n")
                handle.write("CLAUDE_EXECUTABLE=claude-beta\n")
                handle.write("CLAUDE_WORKDIR=workspace\n")
                handle.write("CLAUDE_NO_SESSION_PERSISTENCE=1\n")

            os.mkdir(os.path.join(temp_dir, "workspace"))

            config = AppConfig.load(temp_dir, environ={"HOME": "/tmp/example-home"})

            self.assertEqual(config.claude_executable, "claude-beta")
            self.assertEqual(
                config.claude_workdir,
                os.path.join(temp_dir, "workspace"),
            )
            self.assertTrue(config.claude_no_session_persistence)

    def test_invalid_boolean_env_raises_config_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = os.path.join(temp_dir, ".env")
            with open(env_path, "w") as handle:
                handle.write("TELEGRAM_BOT_TOKEN=file-token\n")
                handle.write("TELEGRAM_CHAT_ID=12345\n")
                handle.write("CLAUDE_NO_SESSION_PERSISTENCE=maybe\n")

            with self.assertRaises(ConfigError):
                AppConfig.load(temp_dir, environ={"HOME": "/tmp/example-home"})

    def test_invalid_integer_env_raises_config_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = os.path.join(temp_dir, ".env")
            with open(env_path, "w") as handle:
                handle.write("TELEGRAM_BOT_TOKEN=file-token\n")
                handle.write("TELEGRAM_CHAT_ID=12345\n")
                handle.write("TELEGRAM_MAX_MESSAGE_LENGTH=oops\n")

            with self.assertRaises(ConfigError):
                AppConfig.load(temp_dir, environ={"HOME": "/tmp/example-home"})

    def test_invalid_watch_poll_timeout_raises_config_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = os.path.join(temp_dir, ".env")
            with open(env_path, "w") as handle:
                handle.write("TELEGRAM_BOT_TOKEN=file-token\n")
                handle.write("TELEGRAM_CHAT_ID=12345\n")
                handle.write("WATCH_POLL_TIMEOUT=0\n")

            with self.assertRaises(ConfigError):
                AppConfig.load(temp_dir, environ={"HOME": "/tmp/example-home"})

    def test_load_env_file_keeps_single_quotes_literal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = os.path.join(temp_dir, ".env")
            with open(env_path, "w") as handle:
                handle.write("CLAUDE_PENDING_MESSAGE='$HOME literal'\n")

            loaded = load_env_file(env_path, {"HOME": "/tmp/example-home"})

            self.assertEqual(loaded["CLAUDE_PENDING_MESSAGE"], "$HOME literal")

    def test_load_env_file_supports_default_interpolation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = os.path.join(temp_dir, ".env")
            with open(env_path, "w") as handle:
                handle.write("CLAUDE_SETTINGS_PATH=${HOME:-/tmp}/.claude/settings.json\n")

            loaded = load_env_file(env_path, {})

            self.assertEqual(
                loaded["CLAUDE_SETTINGS_PATH"],
                "/tmp/.claude/settings.json",
            )

    def test_load_env_file_does_not_expand_bare_dollar_names(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = os.path.join(temp_dir, ".env")
            with open(env_path, "w") as handle:
                handle.write("CLAUDE_PENDING_MESSAGE=$HOME literal\n")

            loaded = load_env_file(env_path, {"HOME": "/tmp/example-home"})

            self.assertEqual(loaded["CLAUDE_PENDING_MESSAGE"], "$HOME literal")

    def test_load_env_file_keeps_backslashes_in_single_quoted_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = os.path.join(temp_dir, ".env")
            with open(env_path, "w") as handle:
                handle.write(r"VALUE='C:\tmp\logs'" + "\n")

            loaded = load_env_file(env_path, {})

            self.assertEqual(loaded["VALUE"], r"C:\tmp\logs")

    def test_load_env_file_keeps_unknown_backslash_escapes_in_double_quotes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = os.path.join(temp_dir, ".env")
            with open(env_path, "w") as handle:
                handle.write(r'VALUE="keep\qbackslash"' + "\n")

            loaded = load_env_file(env_path, {})

            self.assertEqual(loaded["VALUE"], r"keep\qbackslash")


if __name__ == "__main__":
    unittest.main()
