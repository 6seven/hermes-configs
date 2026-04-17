#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize a fetched Redmine issue bundle."
    )
    parser.add_argument("--bundle", required=True, help="Path to issue_bundle.json")
    parser.add_argument("--output", help="Optional output markdown file path")
    return parser.parse_args()


def load_bundle(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def project_name(bundle: dict[str, Any]) -> str:
    project = bundle.get("issue", {}).get("project") or {}
    if isinstance(project, dict):
        return str(project.get("name") or project.get("id") or "")
    return ""


def summarize_attachments(
    attachments: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    lines: list[str] = []
    unresolved: list[str] = []
    for item in attachments:
        filename = str(item.get("filename") or "unknown")
        description = item.get("description") or ""
        preview = item.get("text_preview") or ""
        if preview:
            compact = " ".join(str(preview).split())[:300]
            lines.append(f"- `{filename}`: {compact}")
            continue
        if description:
            lines.append(f"- `{filename}`: {description}")
            continue
        unresolved.append(filename)
        lines.append(f"- `{filename}`: 无法自动提取正文，仅保留文件元数据")
    return lines, unresolved


def extract_acceptance_points(description: str) -> list[str]:
    points: list[str] = []
    for raw in description.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("-", "*", "1.", "2.", "3.", "4.", "5.")):
            points.append(line)
    return points[:10]


def render_markdown(bundle: dict[str, Any]) -> str:
    issue = bundle["issue"]
    description = str(issue.get("description") or "").strip()
    attachments = bundle.get("attachments", [])
    attachment_lines, unresolved = summarize_attachments(attachments)
    acceptance = extract_acceptance_points(description)
    acceptance_lines = acceptance or ["- 需根据工单描述与附件补全验收点"]
    unresolved_line = (
        ", ".join(f"`{name}`" for name in unresolved) if unresolved else "无"
    )
    description_block = description if description else "工单描述为空"
    return f"""# Redmine Issue Summary

## Meta

- Issue: #{bundle["issue_id"]}
- URL: {bundle["issue_url"]}
- Project: {project_name(bundle)}
- Subject: {issue.get("subject") or ""}
- Tracker: {(issue.get("tracker") or {}).get("name", "")}
- Status: {(issue.get("status") or {}).get("name", "")}
- Priority: {(issue.get("priority") or {}).get("name", "")}

## Original Description

{description_block}

## Working Summary

- 先根据工单描述定位问题背景、受影响范围和预期行为。
- 若附件包含日志、接口数据或复现线索，优先把这些信息转为可执行的排查和修复目标。
- 若描述不足，以附件和已有代码上下文补全约束，但不要虚构需求。

## Acceptance Criteria

{chr(10).join(acceptance_lines)}

## Attachment Notes

{chr(10).join(attachment_lines) if attachment_lines else "- 无附件"}

## Unresolved Attachments

- {unresolved_line}

## OpenCode Handoff

- 仅在当前 task worktree 内操作。
- 先检查现有实现与约束，再做修改。
- 完成后报告修改文件、已执行验证和剩余风险。
- 不要自动 merge 或 push。
"""


def main() -> int:
    args = parse_args()
    bundle_path = Path(args.bundle).expanduser().resolve()
    bundle = load_bundle(bundle_path)
    markdown = render_markdown(bundle)
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
