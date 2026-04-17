#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = os.environ.get("PMGR_BASE_URL", "http://127.0.0.1:8710")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Call project-manager Hermes endpoints."
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="project-manager base URL",
    )
    parser.add_argument(
        "--api-token",
        default=os.environ.get("PMGR_API_TOKEN"),
        help="project-manager API token",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("health", help="Check project-manager system health")
    subparsers.add_parser("list-projects", help="List managed projects")

    resolve = subparsers.add_parser(
        "resolve-workspace", help="Resolve existing workspace"
    )
    resolve.add_argument("--project", required=True)
    resolve.add_argument("--task")
    resolve.add_argument("--source-branch")
    resolve.add_argument("--branch-prefix", default="fix")

    create = subparsers.add_parser("create-workspace", help="Create task workspace")
    create.add_argument("--project", required=True)
    create.add_argument("--task", required=True)
    create.add_argument("--source-branch", default="main")
    create.add_argument("--branch-prefix", default="fix")

    oc_health = subparsers.add_parser("opencode-health", help="Check OpenCode health")
    oc_health.add_argument("--project", required=True)
    oc_health.add_argument("--task")
    oc_health.add_argument("--directory")

    create_session = subparsers.add_parser(
        "opencode-create-session", help="Create OpenCode session"
    )
    create_session.add_argument("--project", required=True)
    create_session.add_argument("--task")
    create_session.add_argument("--directory")
    create_session.add_argument("--title", required=True)

    send = subparsers.add_parser(
        "opencode-send-message", help="Send message to OpenCode session"
    )
    send.add_argument("--project", required=True)
    send.add_argument("--task")
    send.add_argument("--directory")
    send.add_argument("--session-id", required=True)
    send.add_argument("--message", help="Inline message")
    send.add_argument("--message-file", help="Read message from file")

    run_shell = subparsers.add_parser(
        "opencode-run-shell", help="Run shell in OpenCode session"
    )
    run_shell.add_argument("--project", required=True)
    run_shell.add_argument("--task")
    run_shell.add_argument("--directory")
    run_shell.add_argument("--session-id", required=True)
    run_shell.add_argument("--shell-command", required=True)
    run_shell.add_argument("--agent", default="build")

    get_messages = subparsers.add_parser(
        "opencode-get-messages", help="Get OpenCode session messages"
    )
    get_messages.add_argument("--project")
    get_messages.add_argument("--task")
    get_messages.add_argument("--directory")
    get_messages.add_argument("--session-id", required=True)
    get_messages.add_argument("--after-message-id")
    get_messages.add_argument("--limit", type=int)

    list_sessions = subparsers.add_parser(
        "opencode-list-sessions", help="List OpenCode sessions for a workspace"
    )
    list_sessions.add_argument("--project")
    list_sessions.add_argument("--task")
    list_sessions.add_argument("--directory")
    list_sessions.add_argument("--limit", type=int)

    return parser.parse_args()


def request_json(
    base_url: str,
    path: str,
    payload: dict[str, Any] | None,
    api_token: str | None,
    method: str = "POST",
) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    body: bytes | None = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"
    request = Request(
        f"{base_url.rstrip('/')}{path}", data=body, headers=headers, method=method
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def build_workspace_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if getattr(args, "project", None):
        payload["project_ref"] = args.project
    if getattr(args, "task", None):
        payload["task_ref"] = args.task
    if getattr(args, "directory", None):
        payload["directory"] = args.directory
    return payload


def read_message(args: argparse.Namespace) -> str:
    if args.message:
        return args.message
    if args.message_file:
        with open(args.message_file, "r", encoding="utf-8") as handle:
            return handle.read()
    raise ValueError("message or message-file is required")


def print_http_error(prefix: str, exc: HTTPError) -> None:
    details = ""
    try:
        body = exc.read().decode("utf-8", errors="replace")
        if body:
            details = f": {body}"
    except OSError:
        details = ""
    print(f"{prefix}: HTTP {exc.code}{details}", file=sys.stderr)


def main() -> int:
    args = parse_args()
    try:
        if args.command == "health":
            result = request_json(
                args.base_url, "/health", None, args.api_token, method="GET"
            )
        elif args.command == "list-projects":
            result = request_json(
                args.base_url,
                "/hermes/tools/pm_list_projects",
                {},
                args.api_token,
            )
        elif args.command == "resolve-workspace":
            payload: dict[str, Any] = {
                "project_ref": args.project,
                "branch_prefix": args.branch_prefix,
            }
            if args.task:
                payload["task_ref"] = args.task
            if args.source_branch:
                payload["source_branch"] = args.source_branch
            result = request_json(
                args.base_url,
                "/hermes/tools/pm_resolve_workspace",
                payload,
                args.api_token,
            )
        elif args.command == "create-workspace":
            result = request_json(
                args.base_url,
                "/hermes/tools/pm_create_task_workspace",
                {
                    "project_ref": args.project,
                    "task_ref": args.task,
                    "source_branch": args.source_branch,
                    "branch_prefix": args.branch_prefix,
                },
                args.api_token,
            )
        elif args.command == "opencode-health":
            result = request_json(
                args.base_url,
                "/hermes/tools/opencode_health",
                build_workspace_payload(args),
                args.api_token,
            )
        elif args.command == "opencode-create-session":
            payload = build_workspace_payload(args)
            payload["payload"] = {"title": args.title}
            result = request_json(
                args.base_url,
                "/hermes/tools/opencode_create_session",
                payload,
                args.api_token,
            )
        elif args.command == "opencode-send-message":
            payload = build_workspace_payload(args)
            payload["session_id"] = args.session_id
            payload["payload"] = {
                "parts": [{"type": "text", "text": read_message(args)}]
            }
            result = request_json(
                args.base_url,
                "/hermes/tools/opencode_send_message",
                payload,
                args.api_token,
            )
        elif args.command == "opencode-run-shell":
            payload = build_workspace_payload(args)
            payload["session_id"] = args.session_id
            payload["payload"] = {
                "agent": args.agent,
                "command": args.shell_command,
            }
            result = request_json(
                args.base_url,
                "/hermes/tools/opencode_run_shell",
                payload,
                args.api_token,
            )
        elif args.command == "opencode-get-messages":
            payload = build_workspace_payload(args)
            payload["session_id"] = args.session_id
            if args.after_message_id:
                payload["after_message_id"] = args.after_message_id
            if args.limit is not None:
                payload["limit"] = args.limit
            result = request_json(
                args.base_url,
                "/hermes/tools/opencode_get_messages",
                payload,
                args.api_token,
            )
        elif args.command == "opencode-list-sessions":
            payload = build_workspace_payload(args)
            if args.limit is not None:
                payload["limit"] = args.limit
            result = request_json(
                args.base_url,
                "/hermes/tools/opencode_list_sessions",
                payload,
                args.api_token,
            )
        else:
            raise ValueError(f"Unsupported command: {args.command}")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except HTTPError as exc:
        print_http_error("project-manager request failed", exc)
        return 3
    except URLError as exc:
        print(f"project-manager request failed: {exc}", file=sys.stderr)
        return 4

    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
