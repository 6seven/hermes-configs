#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


ISSUE_PATTERN = re.compile(r"/issues/(?P<issue_id>\d+)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Redmine issue details and attachments."
    )
    parser.add_argument("--issue-url", required=True, help="Full Redmine issue URL.")
    parser.add_argument(
        "--output-dir", required=True, help="Directory for bundle output."
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("REDMINE_BASE_URL", "https://apredmine.topwhitech.com"),
        help="Redmine base URL.",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("REDMINE_API_KEY"),
        help="Redmine API key. Falls back to REDMINE_API_KEY.",
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Fetch issue JSON without downloading attachments.",
    )
    return parser.parse_args()


def extract_issue_id(issue_url: str) -> str:
    match = ISSUE_PATTERN.search(urlparse(issue_url).path)
    if not match:
        raise ValueError(f"Could not extract Redmine issue id from URL: {issue_url}")
    return match.group("issue_id")


def build_headers(api_key: str | None) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["X-Redmine-API-Key"] = api_key
    return headers


def fetch_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    request = Request(url, headers=headers)
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def download_file(url: str, destination: Path, headers: dict[str, str]) -> None:
    request = Request(url, headers=headers)
    with urlopen(request, timeout=60) as response:
        destination.write_bytes(response.read())


def detect_text_file(path: Path, content_type: str | None) -> bool:
    guessed = content_type or mimetypes.guess_type(path.name)[0] or ""
    return guessed.startswith("text/") or path.suffix.lower() in {
        ".txt",
        ".md",
        ".json",
        ".log",
        ".yaml",
        ".yml",
        ".csv",
        ".xml",
        ".html",
        ".js",
        ".ts",
        ".tsx",
        ".py",
        ".java",
        ".kt",
        ".swift",
    }


def read_text_preview(path: Path, limit: int = 4000) -> str | None:
    try:
        data = path.read_text(encoding="utf-8")
        return data[:limit]
    except UnicodeDecodeError:
        try:
            data = path.read_text(encoding="utf-8", errors="replace")
            return data[:limit]
        except OSError:
            return None
    except OSError:
        return None


def normalize_attachment(
    item: dict[str, Any],
    attachments_dir: Path,
    headers: dict[str, str],
    metadata_only: bool,
) -> dict[str, Any]:
    attachment_id = str(item.get("id", ""))
    filename = item.get("filename") or f"attachment-{attachment_id}"
    disk_path = attachments_dir / filename
    result: dict[str, Any] = {
        "id": attachment_id,
        "filename": filename,
        "filesize": item.get("filesize"),
        "content_type": item.get("content_type"),
        "description": item.get("description"),
        "content_url": item.get("content_url"),
        "disk_path": str(disk_path),
        "downloaded": False,
    }
    if metadata_only:
        return result
    content_url = item.get("content_url")
    if not content_url:
        result["download_error"] = "missing content_url"
        return result
    try:
        download_file(str(content_url), disk_path, headers)
        result["downloaded"] = True
        result["exists"] = disk_path.exists()
        if detect_text_file(disk_path, item.get("content_type")):
            preview = read_text_preview(disk_path)
            if preview:
                result["text_preview"] = preview
    except (HTTPError, URLError, OSError) as exc:
        result["download_error"] = str(exc)
    return result


def build_bundle(
    issue_url: str,
    base_url: str,
    api_key: str | None,
    output_dir: Path,
    metadata_only: bool,
) -> dict[str, Any]:
    issue_id = extract_issue_id(issue_url)
    output_dir.mkdir(parents=True, exist_ok=True)
    attachments_dir = output_dir / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)

    issue_endpoint = f"{base_url.rstrip('/')}/issues/{issue_id}.json?{urlencode({'include': 'attachments,journals'})}"
    headers = build_headers(api_key)
    payload = fetch_json(issue_endpoint, headers)
    issue = payload["issue"]

    attachments = [
        normalize_attachment(item, attachments_dir, headers, metadata_only)
        for item in issue.get("attachments", [])
    ]

    bundle = {
        "issue_url": issue_url,
        "issue_id": issue_id,
        "base_url": base_url,
        "issue": {
            "id": issue.get("id"),
            "subject": issue.get("subject"),
            "description": issue.get("description"),
            "project": issue.get("project"),
            "tracker": issue.get("tracker"),
            "status": issue.get("status"),
            "priority": issue.get("priority"),
            "author": issue.get("author"),
            "assigned_to": issue.get("assigned_to"),
            "fixed_version": issue.get("fixed_version"),
            "custom_fields": issue.get("custom_fields", []),
            "journals": issue.get("journals", []),
        },
        "attachments": attachments,
    }
    return bundle


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()
    try:
        bundle = build_bundle(
            issue_url=args.issue_url,
            base_url=args.base_url,
            api_key=args.api_key,
            output_dir=output_dir,
            metadata_only=args.metadata_only,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyError as exc:
        print(f"Unexpected Redmine response, missing key: {exc}", file=sys.stderr)
        return 3
    except HTTPError as exc:
        print(f"Redmine request failed: HTTP {exc.code}", file=sys.stderr)
        return 4
    except URLError as exc:
        print(f"Redmine request failed: {exc}", file=sys.stderr)
        return 5

    bundle_path = output_dir / "issue_bundle.json"
    bundle_path.write_text(
        json.dumps(bundle, ensure_ascii=True, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {"bundle_path": str(bundle_path), "issue_id": bundle["issue_id"]},
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
