#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a text message to Telegram.")
    parser.add_argument("--message", help="Inline message text")
    parser.add_argument("--message-file", help="Read message from file")
    parser.add_argument(
        "--bot-token",
        default=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        help="Telegram bot token",
    )
    parser.add_argument(
        "--chat-id",
        default=os.environ.get("TELEGRAM_CHAT_ID")
        or os.environ.get("TELEGRAM_HOME_CHANNEL", ""),
        help="Telegram chat id",
    )
    return parser.parse_args()


def read_message(args: argparse.Namespace) -> str:
    if args.message:
        return args.message
    if args.message_file:
        with open(args.message_file, "r", encoding="utf-8") as handle:
            return handle.read()
    raise ValueError("message or message-file is required")


def main() -> int:
    args = parse_args()
    if not args.bot_token:
        print("Missing TELEGRAM_BOT_TOKEN", file=sys.stderr)
        return 2
    if not args.chat_id:
        print("Missing TELEGRAM_CHAT_ID or TELEGRAM_HOME_CHANNEL", file=sys.stderr)
        return 3
    text = read_message(args)
    body = urlencode(
        {
            "chat_id": args.chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    request = Request(
        f"https://api.telegram.org/bot{args.bot_token}/sendMessage",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except HTTPError as exc:
        print(f"Telegram request failed: HTTP {exc.code}", file=sys.stderr)
        return 4
    except URLError as exc:
        print(f"Telegram request failed: {exc}", file=sys.stderr)
        return 5
    if not payload.get("ok"):
        print(json.dumps(payload, ensure_ascii=True), file=sys.stderr)
        return 6
    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
