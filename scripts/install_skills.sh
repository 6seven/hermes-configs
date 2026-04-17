#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE_ROOT="$REPO_ROOT/skills"
TARGET_ROOT="${HERMES_HOME:-$HOME/.hermes}/skills"

usage() {
  cat <<'EOF'
Usage:
  install_skills.sh [--dry-run] [--list] [skill-relative-path]

Examples:
  ./scripts/install_skills.sh
  ./scripts/install_skills.sh topwhitech/redmine-pmgr-opencode
  ./scripts/install_skills.sh --dry-run
  ./scripts/install_skills.sh --list

Notes:
  - 默认把仓库内所有 skills 同步到 ~/.hermes/skills
  - 只会同步当前仓库里的 skill 目录，不会删除 ~/.hermes/skills 下其他来源的 skills
  - 同步单个 skill 时，参数使用相对 skills/ 的路径
EOF
}

if [[ ! -d "$SOURCE_ROOT" ]]; then
  printf 'Source skills directory not found: %s\n' "$SOURCE_ROOT" >&2
  exit 1
fi

DRY_RUN=0
LIST_ONLY=0
SKILL_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --list)
      LIST_ONLY=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -n "$SKILL_PATH" ]]; then
        printf 'Only one skill path is supported.\n' >&2
        exit 1
      fi
      SKILL_PATH="$1"
      shift
      ;;
  esac
done

list_skills() {
  find "$SOURCE_ROOT" -name SKILL.md -print | while IFS= read -r skill_file; do
    skill_dir="$(dirname "$skill_file")"
    rel_path="${skill_dir#$SOURCE_ROOT/}"
    printf '%s\n' "$rel_path"
  done | sort
}

sync_skill() {
  local rel_path="$1"
  local src_dir="$SOURCE_ROOT/$rel_path"
  local dst_dir="$TARGET_ROOT/$rel_path"

  if [[ ! -f "$src_dir/SKILL.md" ]]; then
    printf 'Skill not found: %s\n' "$rel_path" >&2
    exit 1
  fi

  mkdir -p "$(dirname "$dst_dir")"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    rsync -av --delete --dry-run \
      --exclude '__pycache__/' \
      --exclude '*.pyc' \
      "$src_dir/" "$dst_dir/"
  else
    rsync -av --delete \
      --exclude '__pycache__/' \
      --exclude '*.pyc' \
      "$src_dir/" "$dst_dir/"
  fi
}

if [[ "$LIST_ONLY" -eq 1 ]]; then
  list_skills
  exit 0
fi

mkdir -p "$TARGET_ROOT"

if [[ -n "$SKILL_PATH" ]]; then
  sync_skill "$SKILL_PATH"
  exit 0
fi

list_skills | while IFS= read -r rel_path; do
  [[ -n "$rel_path" ]] || continue
  sync_skill "$rel_path"
done
