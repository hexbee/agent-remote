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
            self.assertEqual(
                config.claude_settings_path,
                "/tmp/example-home/.claude/test.json",
            )
            self.assertEqual(config.claude_pending_message, "Please wait")
            self.assertEqual(config.heartbeat_keyword, "PING")
            self.assertEqual(config.heartbeat_response, "ENV-PONG")

    def test_invalid_integer_env_raises_config_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = os.path.join(temp_dir, ".env")
            with open(env_path, "w") as handle:
                handle.write("TELEGRAM_BOT_TOKEN=file-token\n")
                handle.write("TELEGRAM_CHAT_ID=12345\n")
                handle.write("TELEGRAM_MAX_MESSAGE_LENGTH=oops\n")

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
