#!/usr/bin/env python3

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode, urlparse, urlunparse


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
PMGR_CLIENT = (
    SKILL_DIR.parent / "redmine-pmgr-opencode" / "scripts" / "pmgr_client.py"
)
PROJECT_MAP = (
    SKILL_DIR.parent / "redmine-pmgr-opencode" / "config" / "project_map.json"
)
BUILD_REMINDER = """<system-reminder>
Your operational mode has changed from plan to build.
You are no longer in read-only mode.
You are permitted to make file changes, run shell commands, and utilize your arsenal of tools as needed.
</system-reminder>"""


if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from parse_redmine_issue_list import parse_url  # noqa: E402


DEFAULT_OPENCODE_BASE_URL = os.environ.get("OPENCODE_BASE_URL", "http://175.178.89.45:4100")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve a Redmine issues URL and execute mtu in a main-branch OpenCode session."
    )
    parser.add_argument("--input-text", help="Raw pasted input text")
    parser.add_argument("--input-file", help="Read raw input text from file")
    parser.add_argument(
        "--opencode-base-url",
        default=DEFAULT_OPENCODE_BASE_URL,
        help="OpenCode shared server base URL for Open Web links",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Create session and execute mtu after printing the plan",
    )
    return parser.parse_args()


def read_input(args: argparse.Namespace) -> str:
    if args.input_text:
        return args.input_text
    if args.input_file:
        return Path(args.input_file).expanduser().resolve().read_text(encoding="utf-8")
    raise ValueError("input-text or input-file is required")


def load_project_map() -> dict[str, str]:
    payload = json.loads(PROJECT_MAP.read_text(encoding="utf-8"))
    return {
        str(key).upper(): str(value)
        for key, value in payload.items()
        if str(key) and str(value)
    }


def run_pmgr(*args: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(PMGR_CLIENT), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "pmgr call failed")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid pmgr response: {exc}") from exc


def get_directory(payload: dict[str, Any]) -> str:
    connection = payload.get("connection")
    if isinstance(connection, dict):
        directory = connection.get("directory")
        if isinstance(directory, str) and directory:
            return directory
    data = payload.get("data")
    if isinstance(data, dict):
        directory = data.get("directory")
        if isinstance(directory, str) and directory:
            return directory
    raise RuntimeError("Could not resolve workspace directory from pmgr response")


def get_session_id(payload: dict[str, Any]) -> str:
    candidates = [payload.get("session_id"), payload.get("id")]
    data = payload.get("data")
    if isinstance(data, dict):
        candidates.extend([data.get("session_id"), data.get("id")])
    for candidate in candidates:
        if isinstance(candidate, str) and candidate:
            return candidate
    raise RuntimeError("Could not extract session id from pmgr response")


def build_message(project_ref: str, issue_ids_csv: str, command: str) -> str:
    return "\n".join(
        [
            BUILD_REMINDER,
            f"Project: {project_ref}",
            f"Batch issue ids: {issue_ids_csv}",
            "Run in execution mode.",
            f"Shell command: {command}",
        ]
    )


def build_title(project_key: str, issue_ids: list[str]) -> str:
    preview = ",".join(issue_ids[:3])
    suffix = "..." if len(issue_ids) > 3 else ""
    return f"batch-mtu {project_key} {preview}{suffix}"


def base64url_encode(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def build_open_web(base_url: str, directory: str, session_id: str) -> str:
    parsed = urlparse(base_url)
    encoded_directory = base64url_encode(directory)
    path = f"/{encoded_directory}/session/{quote(session_id, safe='')}"
    query = urlencode({"directory": directory})
    return urlunparse((parsed.scheme, parsed.netloc, path, "", query, ""))


def build_session_command(session_id: str) -> str:
    return f"pmgr session {session_id}"


def main() -> int:
    args = parse_args()
    try:
        parsed = parse_url(read_input(args))
        project_key = str(parsed["project_key"])
        issue_ids = [str(item) for item in parsed["issue_ids"]]
        issue_ids_csv = str(parsed["issue_ids_csv"])
        project_ref = load_project_map().get(project_key)
        if not project_ref:
            raise ValueError(f"No pmgr project mapping found for Redmine project: {project_key}")
        command = f"mtu {issue_ids_csv}"
        result: dict[str, Any] = {
            "mode": "preview",
            "redmine_project": project_key,
            "pmgr_project": project_ref,
            "issue_ids": issue_ids,
            "issue_ids_csv": issue_ids_csv,
            "shell_command": command,
        }
        if not args.execute:
            print(json.dumps(result, ensure_ascii=True, indent=2))
            return 0

        run_pmgr("health")
        resolve_payload = run_pmgr(
            "resolve-workspace",
            "--project",
            project_ref,
            "--source-branch",
            "main",
        )
        directory = get_directory(resolve_payload)
        run_pmgr("opencode-health", "--project", project_ref, "--directory", directory)
        session_payload = run_pmgr(
            "opencode-create-session",
            "--project",
            project_ref,
            "--directory",
            directory,
            "--title",
            build_title(project_key, issue_ids),
        )
        session_id = get_session_id(session_payload)
        send_payload = run_pmgr(
            "opencode-send-message",
            "--project",
            project_ref,
            "--directory",
            directory,
            "--session-id",
            session_id,
            "--message",
            build_message(project_ref, issue_ids_csv, command),
        )
        shell_payload = run_pmgr(
            "opencode-run-shell",
            "--project",
            project_ref,
            "--directory",
            directory,
            "--session-id",
            session_id,
            "--shell-command",
            command,
        )
        result.update(
            {
                "mode": "execute",
                "directory": directory,
                "open_web": build_open_web(args.opencode_base_url, directory, session_id),
                "session_id": session_id,
                "session_command": build_session_command(session_id),
                "send_message_result": send_payload,
                "run_shell_result": shell_payload,
            }
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 3

    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
