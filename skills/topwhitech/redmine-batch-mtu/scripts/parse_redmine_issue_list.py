#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.parse import parse_qs, urlparse


LIST_URL_PATTERN = re.compile(r"https://apredmine\.topwhitech\.com/projects/[^\s\]\<]+/issues\?[^\s\]\<]+")
ISSUE_URL_PATTERN = re.compile(r"https://apredmine\.topwhitech\.com/issues/(?P<issue_id>\d+)")
PROJECT_PATTERN = re.compile(r"/projects/(?P<project>[^/]+)/issues")
REQUIRED_PREFIX = "mtu "
CSV_IDS_PATTERN = re.compile(r"\d+(?:,\d+)*")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse Redmine issue list URLs from pasted text."
    )
    parser.add_argument("--input-text", help="Raw pasted input text")
    parser.add_argument("--input-file", help="Read raw input text from file")
    return parser.parse_args()


def read_input(args: argparse.Namespace) -> str:
    if args.input_text:
        return args.input_text
    if args.input_file:
        with open(args.input_file, "r", encoding="utf-8") as handle:
            return handle.read()
    raise ValueError("input-text or input-file is required")


def normalize_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def validate_trigger(raw: str) -> str:
    normalized = normalize_text(raw)
    if not normalized.lstrip().startswith(REQUIRED_PREFIX):
        raise ValueError("Missing required trigger prefix: mtu ")
    return normalized.lstrip()[len(REQUIRED_PREFIX) :].strip()


def extract_single_list_url(raw: str) -> str | None:
    matches = LIST_URL_PATTERN.findall(raw)
    unique: list[str] = []
    for item in matches:
        if item not in unique:
            unique.append(item)
    if len(unique) > 1:
        raise ValueError("Multiple Redmine issues URLs found in input")
    return unique[0] if unique else None


def extract_single_issue_url(raw: str) -> str | None:
    matches = [item.group(0) for item in ISSUE_URL_PATTERN.finditer(raw)]
    unique: list[str] = []
    for item in matches:
        if item not in unique:
            unique.append(item)
    if len(unique) > 1:
        raise ValueError("Multiple Redmine issue URLs found in input")
    return unique[0] if unique else None


def parse_issue_ids(query: dict[str, list[str]]) -> list[str]:
    values = query.get("v[issue_id][]") or query.get("issue_id") or []
    ids: list[str] = []
    seen: set[str] = set()
    for value in values:
        for part in value.split(","):
            issue_id = part.strip()
            if not issue_id or not issue_id.isdigit() or issue_id in seen:
                continue
            seen.add(issue_id)
            ids.append(issue_id)
    if not ids:
        raise ValueError("No issue ids found in Redmine issues URL")
    return ids


def build_result(
    issue_ids: list[str],
    source_type: str,
    url: str | None = None,
    project_key: str | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "source_type": source_type,
        "issue_ids": issue_ids,
        "issue_ids_csv": ",".join(issue_ids),
    }
    if url:
        result["url"] = url
    if project_key:
        result["project_key"] = project_key
    return result


def parse_url(raw: str) -> dict[str, object]:
    payload = validate_trigger(raw)
    list_url = extract_single_list_url(payload)
    issue_url = extract_single_issue_url(payload)
    if list_url and issue_url:
        raise ValueError("参数格式不支持")
    if list_url:
        url = list_url
        parsed = urlparse(url)
        match = PROJECT_PATTERN.search(parsed.path)
        if not match:
            raise ValueError(f"Could not extract Redmine project from URL: {url}")
        project_key = match.group("project").upper()
        query = parse_qs(parsed.query, keep_blank_values=True)
        issue_ids = parse_issue_ids(query)
        return build_result(issue_ids, "redmine-issues-url", url=url, project_key=project_key)
    if issue_url:
        issue_id_match = ISSUE_URL_PATTERN.search(issue_url)
        if not issue_id_match:
            raise ValueError("参数格式不支持")
        return build_result([issue_id_match.group("issue_id")], "redmine-issue-url", url=issue_url)
    candidate = payload.strip()
    if CSV_IDS_PATTERN.fullmatch(candidate):
        issue_ids = parse_issue_ids({"issue_id": [candidate]})
        source_type = "issue-id" if len(issue_ids) == 1 else "issue-id-list"
        return build_result(issue_ids, source_type)
    raise ValueError("参数格式不支持")


def main() -> int:
    args = parse_args()
    try:
        result = parse_url(read_input(args))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
