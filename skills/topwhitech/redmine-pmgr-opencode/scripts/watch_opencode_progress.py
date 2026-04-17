#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PMGR_CLIENT = SCRIPT_DIR / "pmgr_client.py"
SUMMARIZER = SCRIPT_DIR / "summarize_opencode_progress.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Poll OpenCode session messages and print Chinese progress summaries."
    )
    parser.add_argument("--session-id", required=True, help="OpenCode session id")
    parser.add_argument("--directory", required=True, help="Workspace directory")
    parser.add_argument("--project", help="Optional project ref")
    parser.add_argument("--task", help="Optional task ref")
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Polling interval in seconds, default 30",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max messages to fetch per poll, default 20",
    )
    parser.add_argument(
        "--state-file",
        help="Optional cursor state file path. Defaults to ~/.hermes_skills_progress/<session>.json",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Fetch once and exit",
    )
    parser.add_argument(
        "--bootstrap",
        choices=["latest"],
        help="Initialize cursor before polling. 'latest' skips all existing messages and watches only future updates.",
    )
    return parser.parse_args()


def default_state_file(session_id: str) -> Path:
    root = Path.home() / ".hermes_skills_progress"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{session_id}.json"


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def build_pmgr_command(
    args: argparse.Namespace, after_message_id: str | None
) -> list[str]:
    command = [
        sys.executable,
        str(PMGR_CLIENT),
        "opencode-get-messages",
        "--session-id",
        args.session_id,
        "--directory",
        args.directory,
        "--limit",
        str(args.limit),
    ]
    if args.project:
        command.extend(["--project", args.project])
    if args.task:
        command.extend(["--task", args.task])
    if after_message_id:
        command.extend(["--after-message-id", after_message_id])
    return command


def extract_last_message_id(raw: str) -> str | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    last_message_id = data.get("last_message_id")
    return (
        last_message_id
        if isinstance(last_message_id, str) and last_message_id
        else None
    )


def extract_count(raw: str) -> int:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 0
    data = payload.get("data")
    if not isinstance(data, dict):
        return 0
    count = data.get("count")
    return count if isinstance(count, int) else 0


def summarize(raw_json: str) -> str:
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", suffix=".json", delete=False
    ) as temp:
        temp.write(raw_json)
        temp_path = temp.name
    proc = run_command([sys.executable, str(SUMMARIZER), "--messages-json", temp_path])
    Path(temp_path).unlink(missing_ok=True)
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or proc.stdout.strip() or "summary failed"
        raise RuntimeError(stderr)
    return proc.stdout.strip()


def main() -> int:
    args = parse_args()
    state_path = (
        Path(args.state_file).expanduser().resolve()
        if args.state_file
        else default_state_file(args.session_id)
    )
    state = load_state(state_path)
    after_message_id = (
        state.get("last_message_id")
        if isinstance(state.get("last_message_id"), str)
        else None
    )

    if args.bootstrap == "latest":
        proc = run_command(build_pmgr_command(args, None))
        if proc.returncode != 0:
            error = proc.stderr.strip() or proc.stdout.strip() or "bootstrap failed"
            print(f"[watch_opencode_progress] {error}", file=sys.stderr)
            return proc.returncode
        last_message_id = extract_last_message_id(proc.stdout)
        if last_message_id:
            state["last_message_id"] = last_message_id
            save_state(state_path, state)
            after_message_id = last_message_id
            print(
                f"[watch_opencode_progress] bootstrapped to latest message: {last_message_id}",
                file=sys.stderr,
            )
        if args.once:
            return 0

    while True:
        proc = run_command(build_pmgr_command(args, after_message_id))
        if proc.returncode != 0:
            error = proc.stderr.strip() or proc.stdout.strip() or "poll failed"
            print(f"[watch_opencode_progress] {error}", file=sys.stderr)
            return proc.returncode

        raw_json = proc.stdout
        count = extract_count(raw_json)
        last_message_id = extract_last_message_id(raw_json)
        if last_message_id:
            state["last_message_id"] = last_message_id
            save_state(state_path, state)

        if count > 0:
            try:
                summary = summarize(raw_json)
            except RuntimeError as exc:
                print(f"[watch_opencode_progress] {exc}", file=sys.stderr)
                return 1
            print(summary)
            print()

        if args.once:
            break

        time.sleep(args.interval)
        after_message_id = (
            state.get("last_message_id")
            if isinstance(state.get("last_message_id"), str)
            else None
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
