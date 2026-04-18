#!/usr/bin/env bash

set -euo pipefail

LOG_DIR="$HOME/.hermes/logs/redmine-watcher"
LOG_FILE="$LOG_DIR/$(date +%F).log"
SKILL_ROOT="$HOME/.hermes/skills/topwhitech/redmine-telegram-watcher/scripts"
RETENTION_DAYS=30

mkdir -p "$LOG_DIR"
find "$LOG_DIR" -type f -name '*.log' -mtime +$RETENTION_DAYS -delete

set -a
source "$HOME/.hermes_skills.env" 2>/dev/null || true
source "$HOME/.hermes/.env" 2>/dev/null || true
set +a

python3 "$SKILL_ROOT/poll_redmine_updates.py" >> "$LOG_FILE" 2>&1
