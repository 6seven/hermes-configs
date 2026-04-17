#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize incremental OpenCode session messages for Hermes review."
    )
    parser.add_argument(
        "--messages-json",
        required=True,
        help="Path to the JSON response from pmgr_client.py opencode-get-messages",
    )
    parser.add_argument(
        "--output",
        help="Optional output markdown path",
    )
    return parser.parse_args()


def load_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def clean_text(value: str) -> str:
    compact = " ".join(value.split())
    return compact.strip()


def summarize_tool(part: dict[str, Any]) -> str | None:
    tool_name = part.get("tool")
    state = part.get("state")
    if not isinstance(tool_name, str) or not isinstance(state, dict):
        return None
    status = state.get("status")
    title = state.get("title") or ""
    if isinstance(title, str) and title.strip():
        return f"工具 `{tool_name}` 已{status}：{clean_text(title)}"
    metadata = state.get("metadata")
    if isinstance(metadata, dict):
        description = metadata.get("description") or metadata.get("output") or ""
        if isinstance(description, str) and description.strip():
            snippet = clean_text(description)[:180]
            return f"工具 `{tool_name}` 已{status}：{snippet}"
    return f"工具 `{tool_name}` 已{status}"


def summarize_patch(part: dict[str, Any]) -> str | None:
    files = part.get("files")
    if not isinstance(files, list) or not files:
        return None
    names = ", ".join(f"`{Path(str(item)).name}`" for item in files[:5])
    if len(files) > 5:
        names += " 等"
    return f"产生补丁：{names}"


def summarize_messages(messages: list[dict[str, Any]]) -> tuple[list[str], str | None]:
    updates: list[str] = []
    last_message_id: str | None = None
    for item in messages:
        info = item.get("info")
        if isinstance(info, dict):
            msg_id = info.get("id")
            if isinstance(msg_id, str) and msg_id:
                last_message_id = msg_id
            role = info.get("role")
            if role != "assistant":
                continue
        parts = item.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict):
                continue
            part_type = part.get("type")
            if part_type == "text":
                text = part.get("text")
                if isinstance(text, str) and clean_text(text):
                    updates.append(f"文本进展：{clean_text(text)[:400]}")
            elif part_type == "tool":
                line = summarize_tool(part)
                if line:
                    updates.append(line)
            elif part_type == "patch":
                line = summarize_patch(part)
                if line:
                    updates.append(line)
    deduped: list[str] = []
    seen: set[str] = set()
    for line in updates:
        if line in seen:
            continue
        seen.add(line)
        deduped.append(line)
    return deduped, last_message_id


def render_markdown(payload: dict[str, Any]) -> str:
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("Unexpected pmgr response: missing data object")
    messages = data.get("messages")
    if not isinstance(messages, list):
        raise ValueError("Unexpected pmgr response: missing messages list")
    updates, last_message_id = summarize_messages(messages)
    if not updates:
        updates = ["无新增可同步进展"]
    lines = [
        "# OpenCode 过程同步",
        "",
        f"- Session: `{data.get('session_id', '')}`",
        f"- 新增消息数: {data.get('count', 0)}",
        f"- 最新消息 ID: `{last_message_id or data.get('last_message_id') or ''}`",
        "",
        "## 中文进度摘要",
        "",
    ]
    lines.extend(f"- {line}" for line in updates)
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    payload = load_payload(Path(args.messages_json).expanduser().resolve())
    markdown = render_markdown(payload)
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
