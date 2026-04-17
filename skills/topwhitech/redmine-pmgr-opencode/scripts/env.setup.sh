#!/bin/zsh

redmine_base_default="https://apredmine.topwhitech.com"
pmgr_base_default="http://127.0.0.1:8710"
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

printf "Configure environment for redmine-pmgr-opencode\n"
prompt_value REDMINE_BASE_URL "Redmine base URL" "$redmine_base_default"
prompt_value REDMINE_API_KEY "Redmine API key" "${REDMINE_API_KEY:-}"
prompt_value PMGR_BASE_URL "project-manager base URL" "$pmgr_base_default"
prompt_value PMGR_API_TOKEN "project-manager API token (optional)" "${PMGR_API_TOKEN:-}"

export REDMINE_BASE_URL
export REDMINE_API_KEY
export PMGR_BASE_URL
export PMGR_API_TOKEN

cat > "$env_file" <<EOF
export REDMINE_BASE_URL="${REDMINE_BASE_URL}"
export REDMINE_API_KEY="${REDMINE_API_KEY}"
export PMGR_BASE_URL="${PMGR_BASE_URL}"
export PMGR_API_TOKEN="${PMGR_API_TOKEN}"
EOF

printf "\nExported variables for current shell and saved to %s\n" "$env_file"
printf "Reuse later with: source %s\n" "$env_file"
printf "Ensure ~/.config/zsh/zshrc loads it with: [ -f \"$HOME/.hermes_skills.env\" ] && source \"$HOME/.hermes_skills.env\"\n"
