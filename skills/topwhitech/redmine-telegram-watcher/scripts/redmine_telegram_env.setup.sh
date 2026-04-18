#!/bin/zsh

env_file="$HOME/.hermes_skills.env"

if [[ -f "$env_file" ]]; then
  source "$env_file"
fi

prompt_value() {
  local var_name="$1"
  local prompt_text="$2"
  local default_value="$3"
  local current_value="${(P)var_name}"
  local display_default="$default_value"
  if [[ -n "$current_value" ]]; then
    display_default="$current_value"
  fi
  printf "%s" "$prompt_text"
  if [[ -n "$display_default" ]]; then
    printf " [%s]" "$display_default"
  fi
  printf ": "
  local input_value
  IFS= read -r input_value
  if [[ -z "$input_value" ]]; then
    input_value="$display_default"
  fi
  typeset -g "$var_name=$input_value"
}

printf "Configure environment for redmine-telegram-watcher\n"
prompt_value REDMINE_BASE_URL "Redmine base URL" "${REDMINE_BASE_URL:-https://apredmine.topwhitech.com}"
prompt_value REDMINE_API_KEY "Redmine API key" "${REDMINE_API_KEY:-}"
prompt_value TELEGRAM_BOT_TOKEN "Telegram bot token" "${TELEGRAM_BOT_TOKEN:-}"
prompt_value TELEGRAM_CHAT_ID "Telegram chat id" "${TELEGRAM_CHAT_ID:-${TELEGRAM_HOME_CHANNEL:-}}"

export REDMINE_BASE_URL
export REDMINE_API_KEY
export TELEGRAM_BOT_TOKEN
export TELEGRAM_CHAT_ID

cat > "$env_file" <<EOF
export REDMINE_BASE_URL="${REDMINE_BASE_URL}"
export REDMINE_API_KEY="${REDMINE_API_KEY}"
export PMGR_BASE_URL="${PMGR_BASE_URL:-http://127.0.0.1:8710}"
export PMGR_API_TOKEN="${PMGR_API_TOKEN:-}"
export TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN}"
export TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID}"
EOF

printf "\nSaved watcher variables to %s\n" "$env_file"
