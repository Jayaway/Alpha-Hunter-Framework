# -*- coding: utf-8 -*-
"""
Account crawl runtime status.

This module does not proactively validate accounts and does not access the
network. It only records status based on results returned by the crawl process.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


STATUS_FILE = Path("graph_data/account_runtime_status.json")


def load_account_status() -> dict[str, Any]:
    if not STATUS_FILE.exists():
        return {}
    try:
        with STATUS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_account_status(status: dict[str, Any]) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with STATUS_FILE.open("w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def mark_account_success(handle: str, tweet_count: int) -> dict[str, Any]:
    status = load_account_status()
    normalized = normalize_handle(handle)
    item = {
        "last_status": "active",
        "fail_count": 0,
        "last_error": "",
        "last_checked_at": now_iso(),
        "last_tweet_count": int(tweet_count or 0),
    }
    status[normalized] = item
    save_account_status(status)
    return item


def mark_account_failure(handle: str, error_message: str) -> dict[str, Any]:
    status = load_account_status()
    normalized = normalize_handle(handle)
    previous = status.get(normalized, {})
    fail_count = int(previous.get("fail_count", 0) or 0) + 1
    item = {
        "last_status": classify_failure(error_message),
        "fail_count": fail_count,
        "last_error": str(error_message or ""),
        "last_checked_at": now_iso(),
        "last_tweet_count": 0,
    }
    status[normalized] = item
    save_account_status(status)
    return item


def should_skip_account(handle: str) -> bool:
    status = load_account_status()
    item = status.get(normalize_handle(handle), {})
    try:
        return int(item.get("fail_count", 0) or 0) >= 3
    except (TypeError, ValueError):
        return False


def should_degrade_account(handle: str) -> bool:
    """Compatibility helper for the existing fail_count >= 2 downgrade rule."""
    status = load_account_status()
    item = status.get(normalize_handle(handle), {})
    try:
        fail_count = int(item.get("fail_count", 0) or 0)
    except (TypeError, ValueError):
        return False
    return fail_count >= 2 and fail_count < 3


def classify_failure(error_message: str) -> str:
    text = str(error_message or "").lower()
    if "doesn" in text and "exist" in text:
        return "not_found_or_empty"
    if "no more tweets" in text:
        return "not_found_or_empty"
    if "suspended" in text:
        return "suspended"
    if "protected" in text:
        return "protected"
    return "crawl_failed"


def normalize_handle(handle: str) -> str:
    text = str(handle or "").strip()
    if not text:
        return "@unknown"
    if not text.startswith("@"):
        text = f"@{text}"
    return text


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
