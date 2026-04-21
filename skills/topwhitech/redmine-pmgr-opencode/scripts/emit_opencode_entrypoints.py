#!/usr/bin/env python3

from __future__ import annotations

import argparse
import base64
from urllib.parse import urlencode, urlparse, urlunparse, quote


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Open Web and local session entrypoints for an OpenCode session."
    )
    parser.add_argument(
        "--base-url", required=True, help="OpenCode shared server base URL"
    )
    parser.add_argument("--directory", required=True, help="Workspace directory")
    parser.add_argument("--session-id", required=True, help="OpenCode session id")
    return parser.parse_args()


def base64url_encode(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def build_open_web(base_url: str, directory: str, session_id: str) -> str:
    parsed = urlparse(base_url)
    encoded_directory = base64url_encode(directory)
    path = f"/{encoded_directory}/session/{quote(session_id, safe='')}"
    query = urlencode({"directory": directory})
    return urlunparse((parsed.scheme, parsed.netloc, path, "", query, ""))


def main() -> int:
    args = parse_args()
    open_web = build_open_web(args.base_url, args.directory, args.session_id)
    print("Open Web:")
    print(open_web)
    print()
    print("Session:")
    print(f"pmgr session {args.session_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
