import os
import re

from gateway.compat import ConfigError


ENV_ASSIGNMENT_RE = re.compile(
    r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$"
)
ENV_INTERPOLATION_RE = re.compile(
    r"\$\{([A-Za-z_][A-Za-z0-9_]*)(:-([^}]*))?\}"
)


class AppConfig(object):
    __slots__ = (
        "root_dir",
        "env_file",
        "telegram_bot_token",
        "telegram_chat_id",
        "raw_output",
        "claude_executable",
        "claude_settings_path",
        "claude_workdir",
        "claude_no_session_persistence",
        "codex_executable",
        "codex_model",
        "codex_reasoning_effort",
        "codex_workdir",
        "telegram_max_message_length",
        "watch_poll_timeout",
        "claude_pending_message",
        "codex_pending_message",
        "heartbeat_keyword",
        "heartbeat_response",
        "environment",
    )

    def __init__(
        self,
        root_dir,
        env_file,
        telegram_bot_token,
        telegram_chat_id,
        raw_output,
        claude_executable,
        claude_settings_path,
        claude_workdir,
        claude_no_session_persistence,
        codex_executable,
        codex_model,
        codex_reasoning_effort,
        codex_workdir,
        telegram_max_message_length,
        watch_poll_timeout,
        claude_pending_message,
        codex_pending_message,
        heartbeat_keyword,
        heartbeat_response,
        environment,
    ):
        self.root_dir = root_dir
        self.env_file = env_file
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id
        self.raw_output = raw_output
        self.claude_executable = claude_executable
        self.claude_settings_path = claude_settings_path
        self.claude_workdir = claude_workdir
        self.claude_no_session_persistence = claude_no_session_persistence
        self.codex_executable = codex_executable
        self.codex_model = codex_model
        self.codex_reasoning_effort = codex_reasoning_effort
        self.codex_workdir = codex_workdir
        self.telegram_max_message_length = telegram_max_message_length
        self.watch_poll_timeout = watch_poll_timeout
        self.claude_pending_message = claude_pending_message
        self.codex_pending_message = codex_pending_message
        self.heartbeat_keyword = heartbeat_keyword
        self.heartbeat_response = heartbeat_response
        self.environment = environment

    @classmethod
    def load(cls, root_dir, environ=None):
        base_environment = dict(os.environ if environ is None else environ)
        env_file = base_environment.get("ENV_FILE", os.path.join(root_dir, ".env"))
        env_file = os.path.expanduser(env_file)

        merged_environment = {}
        if os.path.isfile(env_file):
            merged_environment.update(load_env_file(env_file, base_environment))
        merged_environment.update(base_environment)

        telegram_bot_token = merged_environment.get("TELEGRAM_BOT_TOKEN", "")
        if not telegram_bot_token:
            raise ConfigError("Missing TELEGRAM_BOT_TOKEN in .env")

        telegram_chat_id = merged_environment.get("TELEGRAM_CHAT_ID", "")
        if not telegram_chat_id:
            raise ConfigError("Missing TELEGRAM_CHAT_ID in .env")

        claude_settings_path = merged_environment.get(
            "CLAUDE_SETTINGS_PATH",
            os.path.join("~", ".claude", "settings.json"),
        )
        claude_settings_path = os.path.expanduser(claude_settings_path)
        claude_workdir = _parse_dir_env(
            merged_environment,
            "CLAUDE_WORKDIR",
            root_dir,
        )
        codex_workdir = _parse_dir_env(
            merged_environment,
            "CODEX_WORKDIR",
            root_dir,
        )

        telegram_max_message_length = _parse_int_env(
            merged_environment,
            "TELEGRAM_MAX_MESSAGE_LENGTH",
            3500,
        )
        watch_poll_timeout = _parse_int_env(
            merged_environment,
            "WATCH_POLL_TIMEOUT",
            10,
        )
        if watch_poll_timeout < 1:
            raise ConfigError("Invalid WATCH_POLL_TIMEOUT: {}".format(watch_poll_timeout))

        return cls(
            root_dir=root_dir,
            env_file=env_file,
            telegram_bot_token=telegram_bot_token,
            telegram_chat_id=telegram_chat_id,
            raw_output=merged_environment.get("RAW_OUTPUT", "0") == "1",
            claude_executable=merged_environment.get("CLAUDE_EXECUTABLE", "claude"),
            claude_settings_path=claude_settings_path,
            claude_workdir=claude_workdir,
            claude_no_session_persistence=_parse_bool_env(
                merged_environment,
                "CLAUDE_NO_SESSION_PERSISTENCE",
                False,
            ),
            codex_executable=merged_environment.get("CODEX_EXECUTABLE", "codex"),
            codex_model=merged_environment.get("CODEX_MODEL", "gpt-5.3-codex"),
            codex_reasoning_effort=merged_environment.get(
                "CODEX_REASONING_EFFORT",
                "high",
            ),
            codex_workdir=codex_workdir,
            telegram_max_message_length=telegram_max_message_length,
            watch_poll_timeout=watch_poll_timeout,
            claude_pending_message=merged_environment.get(
                "CLAUDE_PENDING_MESSAGE",
                "[CLAUDE CODE] Processing your request...",
            ),
            codex_pending_message=merged_environment.get(
                "CODEX_PENDING_MESSAGE",
                "[CODEX CLI] Processing your request...",
            ),
            heartbeat_keyword=merged_environment.get("HEARTBEAT_KEYWORD", "ping"),
            heartbeat_response=merged_environment.get("HEARTBEAT_RESPONSE", "pong"),
            environment=merged_environment,
        )


def load_env_file(path, base_environment):
    loaded = {}

    with open(path, "r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, 1):
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            match = ENV_ASSIGNMENT_RE.match(raw_line.rstrip("\n"))
            if not match:
                raise ConfigError(
                    "Invalid env assignment at {}:{}".format(path, line_number)
                )

            key, raw_value = match.groups()
            value = _parse_env_value(raw_value, loaded, base_environment)
            loaded[key] = value

    return loaded


def _parse_env_value(raw_value, loaded_values, base_environment):
    raw_value = raw_value.lstrip()
    if raw_value == "":
        return ""

    if raw_value[0] == "'":
        value, end_index = _parse_quoted_value(raw_value, "'", _SINGLE_QUOTE_ESCAPES)
        _validate_trailing_content(raw_value[end_index:])
        return value

    if raw_value[0] == '"':
        value, end_index = _parse_quoted_value(raw_value, '"', _DOUBLE_QUOTE_ESCAPES)
        _validate_trailing_content(raw_value[end_index:])
        return _interpolate_value(value, loaded_values, base_environment)

    value = _parse_unquoted_value(raw_value)
    return _interpolate_value(value, loaded_values, base_environment)


_SINGLE_QUOTE_ESCAPES = {
    "\\": "\\",
    "'": "'",
}

_DOUBLE_QUOTE_ESCAPES = {
    "\\": "\\",
    '"': '"',
    "'": "'",
    "a": "\a",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "v": "\v",
}


def _parse_quoted_value(raw_value, quote_char, escape_map):
    value_chars = []
    index = 1

    while index < len(raw_value):
        char = raw_value[index]
        if char == quote_char:
            return "".join(value_chars), index + 1

        if char == "\\":
            index += 1
            if index >= len(raw_value):
                value_chars.append("\\")
                break
            escaped = raw_value[index]
            if escaped in escape_map:
                value_chars.append(escape_map[escaped])
            else:
                value_chars.append("\\")
                value_chars.append(escaped)
            index += 1
            continue

        value_chars.append(char)
        index += 1

    raise ConfigError("Missing closing quote in env value")


def _validate_trailing_content(trailing):
    trailing = trailing.strip()
    if trailing == "" or trailing.startswith("#"):
        return
    raise ConfigError("Unexpected trailing characters in env value")


def _parse_unquoted_value(raw_value):
    value_chars = []
    index = 0

    while index < len(raw_value):
        char = raw_value[index]
        if char == "#" and index > 0 and raw_value[index - 1].isspace():
            break
        value_chars.append(char)
        index += 1

    return "".join(value_chars).rstrip()


def _interpolate_value(value, loaded_values, base_environment):
    current = value
    for _ in range(10):
        updated = ENV_INTERPOLATION_RE.sub(
            lambda match: _resolve_interpolation(
                match,
                loaded_values,
                base_environment,
            ),
            current,
        )
        if updated == current:
            return updated
        current = updated
    return current


def _resolve_interpolation(match, loaded_values, base_environment):
    key = match.group(1)
    default = match.group(3)
    resolved = _lookup_env_value(key, loaded_values, base_environment)

    if default is not None:
        if resolved in (None, ""):
            return _interpolate_value(default, loaded_values, base_environment)
        return resolved

    if resolved is None:
        return ""
    return resolved


def _lookup_env_value(key, loaded_values, base_environment):
    if key in base_environment:
        return base_environment.get(key)
    return loaded_values.get(key)


def _parse_int_env(environment, key, default):
    raw_value = environment.get(key, "")
    if raw_value == "":
        return default

    try:
        return int(raw_value)
    except ValueError:
        raise ConfigError("Invalid {}: {}".format(key, raw_value))


def _parse_dir_env(environment, key, default):
    raw_value = environment.get(key, "")
    if raw_value == "":
        return default

    resolved = os.path.expanduser(raw_value)
    if not os.path.isabs(resolved):
        resolved = os.path.join(default, resolved)
    return os.path.abspath(resolved)


def _parse_bool_env(environment, key, default):
    raw_value = environment.get(key, "")
    if raw_value == "":
        return default

    normalized = str(raw_value).strip().lower()
    if normalized in ("1", "true", "yes", "on"):
        return True
    if normalized in ("0", "false", "no", "off"):
        return False

    raise ConfigError("Invalid {}: {}".format(key, raw_value))
