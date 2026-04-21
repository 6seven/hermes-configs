#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.parse import parse_qs, urlparse


URL_PATTERN = re.compile(r"https://apredmine\.topwhitech\.com/projects/[^\s\]\<]+/issues\?[^\s\]\<]+")
PROJECT_PATTERN = re.compile(r"/projects/(?P<project>[^/]+)/issues")
REQUIRED_PREFIX = "mtu:"
BUILD_REMINDER = """<system-reminder>
Your operational mode has changed from plan to build.
You are no longer in read-only mode.
You are permitted to make file changes, run shell commands, and utilize your arsenal of tools as needed.
</system-reminder>"""


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
        raise ValueError("Missing required trigger prefix: mtu:")
    if BUILD_REMINDER not in normalized:
        raise ValueError("Missing required build-mode system reminder")
    return normalized


def extract_single_url(raw: str) -> str:
    matches = URL_PATTERN.findall(raw)
    unique: list[str] = []
    for item in matches:
        if item not in unique:
            unique.append(item)
    if not unique:
        raise ValueError("No Redmine issues URL found in input")
    if len(unique) > 1:
        raise ValueError("Multiple Redmine issues URLs found in input")
    return unique[0]


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


def parse_url(raw: str) -> dict[str, object]:
    url = extract_single_url(validate_trigger(raw))
    parsed = urlparse(url)
    match = PROJECT_PATTERN.search(parsed.path)
    if not match:
        raise ValueError(f"Could not extract Redmine project from URL: {url}")
    project_key = match.group("project").upper()
    query = parse_qs(parsed.query, keep_blank_values=True)
    issue_ids = parse_issue_ids(query)
    return {
        "url": url,
        "project_key": project_key,
        "issue_ids": issue_ids,
        "issue_ids_csv": ",".join(issue_ids),
    }


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
