#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FETCH_SCRIPT="$SCRIPT_DIR/fetch_redmine_issue.py"
PMGR_CLIENT="$SCRIPT_DIR/pmgr_client.py"
WATCHER="$SCRIPT_DIR/watch_opencode_progress.py"
PROJECT_MAP="$SCRIPT_DIR/../config/project_map.json"
ENV_FILE="$HOME/.hermes_skills.env"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

usage() {
  cat <<'EOF'
Usage:
  watch_redmine_issue_progress.sh --issue-url <url> [--interval 30]
  watch_redmine_issue_progress.sh --session-id <id> --directory <path> [--interval 30]
  watch_redmine_issue_progress.sh --session-id <id> --project <ref> --task <ref> [--interval 30]

Behavior:
  - issue_url mode:
    1. 读取 Redmine 工单元数据
    2. 映射 pmgr 项目
    3. 解析 issue worktree
    4. 取该 workspace 最近的 OpenCode session
    5. 自动 bootstrap 到最新消息
    6. 开始轮询新增进展

  - session_id mode:
    1. 直接对指定 session 做 bootstrap
    2. 开始轮询新增进展

Options:
  --issue-url URL      Redmine issue URL
  --session-id ID      OpenCode session id
  --directory PATH     Workspace directory
  --project REF        pmgr project ref
  --task REF           pmgr task ref
  --interval SEC       Polling interval, default 30
  --limit N            Per-poll message limit, default 20
  --state-file PATH    Override watcher state file
  --skip-bootstrap     Do not bootstrap latest before polling
  -h, --help           Show help
EOF
}

ISSUE_URL=""
SESSION_ID=""
DIRECTORY=""
PROJECT_REF=""
TASK_REF=""
INTERVAL=30
LIMIT=20
STATE_FILE=""
SKIP_BOOTSTRAP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --issue-url)
      ISSUE_URL="$2"
      shift 2
      ;;
    --session-id)
      SESSION_ID="$2"
      shift 2
      ;;
    --directory)
      DIRECTORY="$2"
      shift 2
      ;;
    --project)
      PROJECT_REF="$2"
      shift 2
      ;;
    --task)
      TASK_REF="$2"
      shift 2
      ;;
    --interval)
      INTERVAL="$2"
      shift 2
      ;;
    --limit)
      LIMIT="$2"
      shift 2
      ;;
    --state-file)
      STATE_FILE="$2"
      shift 2
      ;;
    --skip-bootstrap)
      SKIP_BOOTSTRAP=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$ISSUE_URL" && -z "$SESSION_ID" ]]; then
  printf 'Either --issue-url or --session-id is required.\n' >&2
  exit 1
fi

if [[ -n "$ISSUE_URL" && -n "$SESSION_ID" ]]; then
  printf 'Use either --issue-url or --session-id, not both.\n' >&2
  exit 1
fi

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    printf 'Missing required environment variable: %s\n' "$name" >&2
    exit 1
  fi
}

json_get() {
  local file="$1"
  local expr="$2"
  python3 - "$file" "$expr" <<'PY'
import json, sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
expr = sys.argv[2]
value = eval(expr, {}, {'payload': payload})
if value is None:
    raise SystemExit(1)
print(value)
PY
}

pick_latest_session() {
  local sessions_json="$1"
  python3 - <<'PY' "$sessions_json"
import json, sys

payload = json.loads(sys.argv[1])
sessions = ((payload.get('data') or {}).get('sessions') or [])
print((sessions[0] or {}).get('id', '') if sessions else '')
PY
}

print_session_candidates() {
  local sessions_json="$1"
  python3 - <<'PY' "$sessions_json"
import json, sys
from datetime import datetime

payload = json.loads(sys.argv[1])
sessions = ((payload.get('data') or {}).get('sessions') or [])
if not sessions:
    raise SystemExit(0)
print('Candidate sessions (newest first):', file=sys.stderr)
for idx, item in enumerate(sessions, start=1):
    if not isinstance(item, dict):
        continue
    session_id = str(item.get('id') or '')
    title = str(item.get('title') or '')
    updated = ((item.get('time') or {}).get('updated'))
    updated_label = str(updated)
    if isinstance(updated, (int, float)) and updated:
        try:
            updated_label = datetime.fromtimestamp(updated / 1000).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            updated_label = str(updated)
    print(f"  {idx}. {session_id} | {title or '-'} | updated={updated_label}", file=sys.stderr)
PY
}

guess_worktree_directory() {
  local project_ref="$1"
  local task_ref="$2"
  local projects_json repo_path
  projects_json="$(python3 "$PMGR_CLIENT" list-projects)"
  repo_path="$(python3 - <<'PY' "$projects_json" "$project_ref"
import json, sys

payload = json.loads(sys.argv[1])
project_ref = sys.argv[2]
projects = payload.get('projects') or []
repo_path = ''
for item in projects:
    if not isinstance(item, dict):
        continue
    candidates = {str(item.get('id') or ''), str(item.get('name') or ''), str(item.get('slug') or '')}
    if project_ref in candidates:
        repo_path = str(item.get('repo_path') or '')
        break
print(repo_path)
PY
)"
  if [[ -z "$repo_path" ]]; then
    return 1
  fi
  python3 - <<'PY' "$repo_path" "$task_ref"
from pathlib import Path
import sys

repo_path = Path(sys.argv[1])
task_ref = sys.argv[2]
print(str(repo_path.parent / 'worktrees' / task_ref))
PY
}

if [[ -n "$ISSUE_URL" ]]; then
  require_env REDMINE_API_KEY
  tmp_dir="$(mktemp -d "/tmp/redmine-watch-XXXXXX")"
  python3 "$FETCH_SCRIPT" --issue-url "$ISSUE_URL" --output-dir "$tmp_dir" --metadata-only >/dev/null
  bundle="$tmp_dir/issue_bundle.json"
  issue_id="$(json_get "$bundle" "payload['issue_id']")"
  redmine_project="$(json_get "$bundle" "payload['issue']['project']['name']")"
  PROJECT_REF="$(python3 - "$PROJECT_MAP" "$redmine_project" <<'PY'
import json, sys
from pathlib import Path

mapping = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
print(mapping.get(sys.argv[2], ''))
PY
)"
  if [[ -z "$PROJECT_REF" ]]; then
    printf 'No pmgr project mapping found for Redmine project: %s\n' "$redmine_project" >&2
    exit 1
  fi
  TASK_REF="issue-${issue_id}"

  resolve_json=""
  if resolve_json="$(python3 "$PMGR_CLIENT" resolve-workspace --project "$PROJECT_REF" --task "$TASK_REF" 2>/dev/null)"; then
    DIRECTORY="$(python3 - <<'PY' "$resolve_json"
import json, sys
payload = json.loads(sys.argv[1])
connection = payload.get('connection') or {}
print(connection.get('directory') or '')
PY
)"
  else
    DIRECTORY="$(guess_worktree_directory "$PROJECT_REF" "$TASK_REF" || true)"
    if [[ -n "$DIRECTORY" ]]; then
      if [[ -d "$DIRECTORY" ]]; then
        printf 'Task record missing, guessed worktree directory: %s\n' "$DIRECTORY" >&2
      else
        printf 'Task record missing, guessed historical worktree directory: %s\n' "$DIRECTORY" >&2
      fi
    else
      printf 'Could not resolve workspace directory for %s/%s\n' "$PROJECT_REF" "$TASK_REF" >&2
      exit 1
    fi
  fi

  sessions_json="$(python3 "$PMGR_CLIENT" opencode-list-sessions --directory "$DIRECTORY" --limit 5)"
  print_session_candidates "$sessions_json"
  SESSION_ID="$(pick_latest_session "$sessions_json")"
  if [[ -z "$SESSION_ID" ]]; then
    printf 'No OpenCode session found for workspace: %s\n' "$DIRECTORY" >&2
    exit 1
  fi
  printf 'Resolved issue #%s -> project=%s task=%s session=%s (selected latest)\n' "$issue_id" "$PROJECT_REF" "$TASK_REF" "$SESSION_ID" >&2
fi

if [[ -n "$SESSION_ID" && -z "$DIRECTORY" && -n "$PROJECT_REF" ]]; then
  resolve_args=(python3 "$PMGR_CLIENT" resolve-workspace --project "$PROJECT_REF")
  if [[ -n "$TASK_REF" ]]; then
    resolve_args+=(--task "$TASK_REF")
  fi
  resolve_json="$("${resolve_args[@]}")"
  DIRECTORY="$(python3 - <<'PY' "$resolve_json"
import json, sys
payload = json.loads(sys.argv[1])
connection = payload.get('connection') or {}
print(connection.get('directory') or '')
PY
)"
fi

if [[ -z "$DIRECTORY" ]]; then
  printf 'Directory is required when using --session-id directly.\n' >&2
  exit 1
fi

watch_args=(
  python3 "$WATCHER"
  --session-id "$SESSION_ID"
  --directory "$DIRECTORY"
  --interval "$INTERVAL"
  --limit "$LIMIT"
)

if [[ -n "$PROJECT_REF" ]]; then
  watch_args+=(--project "$PROJECT_REF")
fi
if [[ -n "$TASK_REF" ]]; then
  watch_args+=(--task "$TASK_REF")
fi
if [[ -n "$STATE_FILE" ]]; then
  watch_args+=(--state-file "$STATE_FILE")
fi

if [[ "$SKIP_BOOTSTRAP" -eq 0 ]]; then
  bootstrap_args=(
    python3 "$WATCHER"
    --session-id "$SESSION_ID"
    --directory "$DIRECTORY"
    --limit "$LIMIT"
    --bootstrap latest
    --once
  )
  if [[ -n "$PROJECT_REF" ]]; then
    bootstrap_args+=(--project "$PROJECT_REF")
  fi
  if [[ -n "$TASK_REF" ]]; then
    bootstrap_args+=(--task "$TASK_REF")
  fi
  if [[ -n "$STATE_FILE" ]]; then
    bootstrap_args+=(--state-file "$STATE_FILE")
  fi
  "${bootstrap_args[@]}"
fi

exec "${watch_args[@]}"
