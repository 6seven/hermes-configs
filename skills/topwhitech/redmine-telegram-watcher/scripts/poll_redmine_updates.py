#!/usr/bin/env python3

from __future__ import annotations

import argparse
import http.client
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR.parent / "config" / "watch_projects.json"
SEND_SCRIPT = SCRIPT_DIR / "send_telegram_message.py"
DEFAULT_STATE_FILE = Path.home() / ".hermes_redmine_watcher_state.json"
DEFAULT_BASE_URL = os.environ.get(
    "REDMINE_BASE_URL", "https://apredmine.topwhitech.com"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Poll Redmine updates and push them to Telegram."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Redmine base URL")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("REDMINE_API_KEY", ""),
        help="Redmine API key",
    )
    parser.add_argument(
        "--state-file",
        default=str(DEFAULT_STATE_FILE),
        help="State file path",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print updates without sending Telegram"
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Save baseline without sending notifications",
    )
    parser.add_argument(
        "--test-telegram",
        action="store_true",
        help="Send a Telegram test message and exit",
    )
    return parser.parse_args()


def load_projects() -> list[str]:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return [str(item) for item in payload.get("projects", []) if str(item)]


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"issues": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        backup = path.with_suffix(path.suffix + ".broken")
        path.replace(backup)
        return {"issues": {}}
    if not isinstance(payload, dict):
        return {"issues": {}}
    issues = payload.get("issues")
    if not isinstance(issues, dict):
        payload["issues"] = {}
    return payload


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=True, indent=2), encoding="utf-8")


def fetch_issues(base_url: str, api_key: str) -> list[dict[str, Any]]:
    if not api_key:
        raise ValueError("Missing REDMINE_API_KEY")
    offset = 0
    limit = 50
    issues: list[dict[str, Any]] = []
    while True:
        query = urlencode(
            {
                "limit": limit,
                "offset": offset,
                "status_id": "*",
                "assigned_to_id": "me",
            }
        )
        request = Request(
            f"{base_url.rstrip('/')}/issues.json?{query}",
            headers={"Accept": "application/json", "X-Redmine-API-Key": api_key},
        )
        payload: dict[str, Any] | None = None
        last_error: Exception | None = None
        for _ in range(5):
            try:
                with urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                break
            except (
                http.client.IncompleteRead,
                http.client.RemoteDisconnected,
                URLError,
            ) as exc:
                last_error = exc
        if payload is None:
            if last_error:
                raise last_error
            raise ValueError("Empty Redmine response")
        batch = payload.get("issues", [])
        if not isinstance(batch, list):
            raise ValueError("Unexpected Redmine response: issues is not a list")
        issues.extend(item for item in batch if isinstance(item, dict))
        total_count = int(payload.get("total_count", len(issues)))
        offset += len(batch)
        if offset >= total_count or not batch:
            break
    return issues


def normalize_issue(issue: dict[str, Any], base_url: str) -> dict[str, str]:
    project = issue.get("project") or {}
    status = issue.get("status") or {}
    priority = issue.get("priority") or {}
    issue_id = str(issue.get("id") or "")
    return {
        "id": issue_id,
        "subject": str(issue.get("subject") or ""),
        "project": str(project.get("name") or ""),
        "status": str(status.get("name") or ""),
        "priority": str(priority.get("name") or ""),
        "updated_on": str(issue.get("updated_on") or ""),
        "url": f"{base_url.rstrip('/')}/issues/{issue_id}",
    }


def filter_issues(
    issues: list[dict[str, Any]], base_url: str, projects: list[str]
) -> list[dict[str, str]]:
    allowed = set(projects)
    return [
        normalized
        for normalized in (normalize_issue(issue, base_url) for issue in issues)
        if normalized["project"] in allowed and normalized["id"]
    ]


def format_message(issue: dict[str, str]) -> str:
    return "\n".join(
        [
            "[Redmine 增量]",
            f"#{issue['id']} {issue['subject']}",
            f"项目: {issue['project']}",
            f"状态: {issue['status']}",
            f"优先级: {issue['priority']}",
            f"更新时间: {issue['updated_on']}",
            f"链接: {issue['url']}",
        ]
    )


def collect_updates(
    current: list[dict[str, str]], previous: dict[str, Any]
) -> list[dict[str, str]]:
    saved = previous.get("issues")
    if not isinstance(saved, dict):
        saved = {}
    updates: list[dict[str, str]] = []
    for issue in current:
        key = issue["id"]
        before = saved.get(key)
        if not isinstance(before, dict):
            updates.append(issue)
            continue
        if before.get("updated_on") != issue["updated_on"]:
            updates.append(issue)
    return updates


def build_state(current: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "issues": {
            issue["id"]: {
                "updated_on": issue["updated_on"],
                "project": issue["project"],
            }
            for issue in current
        }
    }


def send_message(text: str) -> None:
    proc = subprocess.run(
        [sys.executable, str(SEND_SCRIPT), "--message", text],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            proc.stderr.strip() or proc.stdout.strip() or "Telegram send failed"
        )


def main() -> int:
    args = parse_args()
    if args.test_telegram:
        send_message("[Redmine Watcher] Telegram test message")
        print("Telegram test message sent")
        return 0

    state_path = Path(args.state_file).expanduser().resolve()
    projects = load_projects()
    try:
        issues = fetch_issues(args.base_url, args.api_key)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except HTTPError as exc:
        print(f"Redmine request failed: HTTP {exc.code}", file=sys.stderr)
        return 3
    except URLError as exc:
        print(f"Redmine request failed: {exc}", file=sys.stderr)
        return 4

    current = filter_issues(issues, args.base_url, projects)
    state = load_state(state_path)

    updates = collect_updates(current, state)
    if args.dry_run:
        for issue in updates:
            print(format_message(issue))
            print()
        print(
            json.dumps({"mode": "dry-run", "updates": len(updates)}, ensure_ascii=True)
        )
        return 0

    if args.bootstrap or not state.get("issues"):
        save_state(state_path, build_state(current))
        print(
            json.dumps({"mode": "bootstrap", "count": len(current)}, ensure_ascii=True)
        )
        return 0

    for issue in updates:
        send_message(format_message(issue))

    save_state(state_path, build_state(current))
    print(json.dumps({"mode": "normal", "updates": len(updates)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
