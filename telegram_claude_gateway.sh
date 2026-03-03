#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

: "${TELEGRAM_BOT_TOKEN:?Missing TELEGRAM_BOT_TOKEN in .env}"
: "${TELEGRAM_CHAT_ID:?Missing TELEGRAM_CHAT_ID in .env}"

API_BASE="https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}"
RAW_OUTPUT="${RAW_OUTPUT:-0}"
CLAUDE_SETTINGS_PATH="${CLAUDE_SETTINGS_PATH:-$HOME/.claude/settings.json}"
TELEGRAM_MAX_MESSAGE_LENGTH="${TELEGRAM_MAX_MESSAGE_LENGTH:-3500}"
CLAUDE_PENDING_MESSAGE="${CLAUDE_PENDING_MESSAGE:-Processing your request...}"
HEARTBEAT_KEYWORD="${HEARTBEAT_KEYWORD:-ping}"
HEARTBEAT_RESPONSE="${HEARTBEAT_RESPONSE:-pong}"

usage() {
  cat <<'EOF'
Usage:
  ./telegram_claude_gateway.sh send "hello"
  ./telegram_claude_gateway.sh claude-send "hello"
  ./telegram_claude_gateway.sh receive
  ./telegram_claude_gateway.sh watch
  ./telegram_claude_gateway.sh watch-new
  ./telegram_claude_gateway.sh watch-reply
  ./telegram_claude_gateway.sh watch-claude-reply
  ./telegram_claude_gateway.sh webhook-info
  ./telegram_claude_gateway.sh delete-webhook

Commands:
  send            Send a text message to TELEGRAM_CHAT_ID
  claude-send     Run Claude with the prompt and send the reply to TELEGRAM_CHAT_ID
  receive         Fetch pending updates once
  watch           Long-poll for new messages continuously
  watch-new       Skip existing pending updates, then watch only new messages
  watch-reply     Watch messages and auto-reply to text messages
  watch-claude-reply
                  Skip existing pending updates, then use Claude to auto-reply to new text messages
  webhook-info    Show current webhook status
  delete-webhook  Remove webhook so getUpdates can work

Debug:
  RAW_OUTPUT=1    Print raw JSON responses instead of formatted output

Environment:
  ENV_FILE                   Path to the env file (default: ./\.env next to the script)
  CLAUDE_SETTINGS_PATH       Claude settings path (default: ~/.claude/settings.json)
  TELEGRAM_MAX_MESSAGE_LENGTH
                             Max Telegram message length before truncation (default: 3500)
  CLAUDE_PENDING_MESSAGE     Placeholder reply before Claude finishes
                             (default: Processing your request...)
  HEARTBEAT_KEYWORD          Direct reply keyword that skips Claude (default: ping)
  HEARTBEAT_RESPONSE         Direct reply text for heartbeat keyword (default: pong)
EOF
}

require_arg() {
  local value="${1:-}"
  local name="$2"
  if [[ -z "$value" ]]; then
    printf 'Missing %s\n' "$name" >&2
    exit 1
  fi
}

api_post() {
  local method="$1"
  shift
  curl --silent --show-error --fail \
    -X POST \
    "$API_BASE/$method" \
    "$@"
}

has_jq() {
  command -v jq >/dev/null 2>&1
}

has_claude() {
  command -v claude >/dev/null 2>&1
}

limit_message_length() {
  local text="$1"
  local limit="${TELEGRAM_MAX_MESSAGE_LENGTH}"
  local suffix="\n\n[truncated]"

  if (( ${#text} <= limit )); then
    printf '%s' "$text"
    return
  fi

  if (( limit <= ${#suffix} )); then
    printf '%s' "${text:0:limit}"
    return
  fi

  printf '%s%s' "${text:0:limit-${#suffix}}" "$suffix"
}

preview_text() {
  local text="$1"
  local preview_limit="${2:-120}"
  local normalized=""

  normalized="$(printf '%s' "$text" | tr '\n' ' ' | tr '\r' ' ')"
  if (( ${#normalized} <= preview_limit )); then
    printf '%s' "$normalized"
    return
  fi

  printf '%s...' "${normalized:0:preview_limit}"
}

log_sent_message() {
  local chat_id="$1"
  local sender="$2"
  local kind="$3"
  local text="$4"
  local target="$chat_id"

  if [[ "$RAW_OUTPUT" == "1" ]]; then
    return
  fi

  if [[ -n "$sender" ]]; then
    target="${sender} (${chat_id})"
  fi

  printf -- '-> %s [%s]: %s\n' \
    "$target" \
    "$kind" \
    "$(preview_text "$(limit_message_length "$text")")"
}

extract_next_offset() {
  local response="$1"
  local lines=""

  lines="$(printf '%s\n' "$response" | grep -o '"update_id":[0-9]\+' || true)"
  if [[ -n "$lines" ]]; then
    printf '%s\n' "$(
      printf '%s\n' "$lines" \
        | sed 's/.*://g' \
        | sort -n \
        | tail -n 1
    )"
  fi
}

print_updates() {
  local response="$1"

  if [[ "$RAW_OUTPUT" == "1" ]] || ! has_jq; then
    printf '%s\n' "$response"
    return
  fi

  printf '%s\n' "$response" | jq -r '
    if (.result | length) == 0 then
      empty
    else
      .result[]
      | select(.message != null)
      | ((.message.date + 28800) | strftime("%Y-%m-%d %H:%M:%S")) + " "
        + (.message.from.username // .message.from.first_name // "unknown")
        + ": "
        + ((.message.text // .message.caption // "<non-text message>") | gsub("\n"; "\\n"))
    end
  '
}

print_send_response() {
  local response="$1"

  if [[ "$RAW_OUTPUT" == "1" ]] || ! has_jq; then
    printf '%s\n' "$response"
    return
  fi

  printf '%s\n' "$response" | jq -r '
    if .ok then
      [
        "sent",
        "message_id=" + (.result.message_id | tostring),
        "chat_id=" + (.result.chat.id | tostring),
        "text=" + ((.result.text // "") | gsub("\n"; "\\n"))
      ] | join(" ")
    else
      .
    end
  '
}

print_webhook_info() {
  local response="$1"

  if [[ "$RAW_OUTPUT" == "1" ]] || ! has_jq; then
    printf '%s\n' "$response"
    return
  fi

  printf '%s\n' "$response" | jq -r '
    if .ok then
      [
        "url=" + (.result.url // ""),
        "pending_update_count=" + (.result.pending_update_count | tostring),
        "has_custom_certificate=" + (.result.has_custom_certificate | tostring)
      ] | join(" ")
    else
      .
    end
  '
}

delete_webhook() {
  api_post "deleteWebhook" \
    --data-urlencode "drop_pending_updates=false"
}

get_webhook_info() {
  api_post "getWebhookInfo"
}

send_message() {
  local text="${1:-}"
  local limited_text=""
  local response=""
  require_arg "$text" "message text"
  limited_text="$(limit_message_length "$text")"

  response="$(api_post "sendMessage" \
    --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
    --data-urlencode "text=${limited_text}")"
  print_send_response "$response"
}

send_message_to_chat() {
  local chat_id="$1"
  local text="$2"
  local limited_text=""
  limited_text="$(limit_message_length "$text")"

  api_post "sendMessage" \
    --data-urlencode "chat_id=${chat_id}" \
    --data-urlencode "text=${limited_text}" >/dev/null
}

run_claude_prompt() {
  local prompt="$1"
  local output=""
  local status=0

  require_arg "$prompt" "prompt"

  if ! has_claude; then
    printf 'Claude CLI not found in PATH'
    return 0
  fi

  if [[ ! -f "$CLAUDE_SETTINGS_PATH" ]]; then
    printf 'Claude settings file not found: %s' "$CLAUDE_SETTINGS_PATH"
    return 0
  fi

  set +e
  output="$(claude -p "$prompt" \
    --settings "$CLAUDE_SETTINGS_PATH" \
    --permission-mode bypassPermissions \
    --dangerously-skip-permissions \
    --add-dir "$ROOT_DIR" \
    --no-session-persistence 2>&1)"
  status=$?
  set -e

  output="$(printf '%s' "$output" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"

  if [[ $status -ne 0 ]]; then
    if [[ -n "$output" ]]; then
      printf 'Claude command failed (%s): %s' "$status" "$output"
    else
      printf 'Claude command failed with exit code %s' "$status"
    fi
    return 0
  fi

  if [[ -z "$output" ]]; then
    printf 'Claude returned no output'
    return 0
  fi

  printf '%s' "$output"
}

receive_once() {
  local response=""

  delete_webhook >/dev/null
  response="$(api_post "getUpdates" \
    --data-urlencode "allowed_updates=[\"message\"]" \
    --data-urlencode "timeout=10")"
  print_updates "$response"
}

watch_messages() {
  local offset="${1:-}"
  local auto_reply="${2:-0}"
  local response=""
  local next_offset=""

  delete_webhook >/dev/null

  while true; do
    if [[ -n "$offset" ]]; then
      response="$(api_post "getUpdates" \
        --data-urlencode "allowed_updates=[\"message\"]" \
        --data-urlencode "timeout=30" \
        --data-urlencode "offset=${offset}")"
    else
      response="$(api_post "getUpdates" \
        --data-urlencode "allowed_updates=[\"message\"]" \
        --data-urlencode "timeout=30")"
    fi

    print_updates "$response"
    if [[ "$auto_reply" == "1" ]]; then
      auto_reply_to_updates "$response"
    fi

    next_offset="$(extract_next_offset "$response" || true)"
    if [[ -n "$next_offset" ]]; then
      offset=$((next_offset + 1))
    fi
  done
}

get_next_offset() {
  local response=""
  local offset=""

  delete_webhook >/dev/null
  response="$(api_post "getUpdates" \
    --data-urlencode "allowed_updates=[\"message\"]" \
    --data-urlencode "timeout=1")"

  offset="$(extract_next_offset "$response" || true)"
  if [[ -n "$offset" ]]; then
    printf '%s\n' $((offset + 1))
  fi
}

watch_new_messages() {
  local next_offset=""
  next_offset="$(get_next_offset || true)"
  watch_messages "$next_offset" "${1:-0}"
}

auto_reply_to_updates() {
  local response="$1"
  local line=""
  local chat_id=""
  local sender=""
  local text=""
  local preview=""
  local reply_text=""

  if ! has_jq; then
    printf 'jq is required for auto-reply commands\n' >&2
    exit 1
  fi

  while IFS= read -r line; do
    chat_id="$(printf '%s\n' "$line" | jq -r '.chat_id')"
    sender="$(printf '%s\n' "$line" | jq -r '.sender')"
    text="$(printf '%s\n' "$line" | jq -r '.text')"

    if [[ -z "$chat_id" || -z "$text" ]]; then
      continue
    fi

    preview="$(printf '%s' "$text" | cut -c1-10)"
    if [[ "${#text}" -gt 10 ]]; then
      reply_text="Rcvd msg from ${sender}: ${preview}..."
    else
      reply_text="Rcvd msg from ${sender}: ${preview}"
    fi

    send_message_to_chat "$chat_id" "$reply_text"
  done < <(
    printf '%s\n' "$response" | jq -c '
      .result[]
      | select(.message != null)
      | select(.message.from.is_bot != true)
      | select((.message.text // "") != "")
      | {
          chat_id: (.message.chat.id | tostring),
          sender: (.message.from.username // .message.from.first_name // "unknown"),
          text: .message.text
        }
    '
  )
}

auto_claude_reply_to_updates() {
  local response="$1"
  local line=""
  local chat_id=""
  local sender=""
  local text=""
  local normalized_text=""
  local normalized_heartbeat_keyword=""
  local reply_text=""

  if ! has_jq; then
    printf 'jq is required for Claude auto-reply commands\n' >&2
    exit 1
  fi

  while IFS= read -r line; do
    chat_id="$(printf '%s\n' "$line" | jq -r '.chat_id')"
    sender="$(printf '%s\n' "$line" | jq -r '.sender')"
    text="$(printf '%s\n' "$line" | jq -r '.text')"

    if [[ -z "$chat_id" || -z "$text" ]]; then
      continue
    fi

    normalized_text="$(printf '%s' "$text" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' | tr '[:upper:]' '[:lower:]')"
    normalized_heartbeat_keyword="$(printf '%s' "$HEARTBEAT_KEYWORD" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' | tr '[:upper:]' '[:lower:]')"

    if [[ "$normalized_text" == "$normalized_heartbeat_keyword" ]]; then
      send_message_to_chat "$chat_id" "$HEARTBEAT_RESPONSE"
      log_sent_message "$chat_id" "$sender" "heartbeat" "$HEARTBEAT_RESPONSE"
      continue
    fi

    send_message_to_chat "$chat_id" "$CLAUDE_PENDING_MESSAGE"
    log_sent_message "$chat_id" "$sender" "placeholder" "$CLAUDE_PENDING_MESSAGE"
    reply_text="$(run_claude_prompt "$text")"
    send_message_to_chat "$chat_id" "$reply_text"
    log_sent_message "$chat_id" "$sender" "claude" "$reply_text"
  done < <(
    printf '%s\n' "$response" | jq -c '
      .result[]
      | select(.message != null)
      | select(.message.from.is_bot != true)
      | select((.message.text // "") != "")
      | {
          chat_id: (.message.chat.id | tostring),
          sender: (.message.from.username // .message.from.first_name // "unknown"),
          text: .message.text
        }
    '
  )
}

watch_claude_replies() {
  local offset=""
  local response=""
  local next_offset=""

  offset="$(get_next_offset || true)"
  delete_webhook >/dev/null

  while true; do
    if [[ -n "$offset" ]]; then
      response="$(api_post "getUpdates" \
        --data-urlencode "allowed_updates=[\"message\"]" \
        --data-urlencode "timeout=30" \
        --data-urlencode "offset=${offset}")"
    else
      response="$(api_post "getUpdates" \
        --data-urlencode "allowed_updates=[\"message\"]" \
        --data-urlencode "timeout=30")"
    fi

    print_updates "$response"
    auto_claude_reply_to_updates "$response"

    next_offset="$(extract_next_offset "$response" || true)"
    if [[ -n "$next_offset" ]]; then
      offset=$((next_offset + 1))
    fi
  done
}

main() {
  local command="${1:-}"

  case "$command" in
    send)
      shift
      send_message "${1:-}"
      ;;
    claude-send)
      shift
      send_message "$(run_claude_prompt "${1:-}")"
      ;;
    receive)
      receive_once
      ;;
    watch)
      watch_messages
      ;;
    watch-new)
      watch_new_messages
      ;;
    watch-reply)
      watch_messages "" "1"
      ;;
    watch-claude-reply)
      watch_claude_replies
      ;;
    webhook-info)
      print_webhook_info "$(get_webhook_info)"
      ;;
    delete-webhook)
      delete_webhook
      printf '\n'
      ;;
    ""|-h|--help|help)
      usage
      ;;
    *)
      printf 'Unknown command: %s\n\n' "$command" >&2
      usage
      exit 1
      ;;
  esac
}

main "$@"
