# -*- coding: utf-8 -*-
"""
Runtime account status tracking for DeepAlpha crawls.

This module records account-level failures without changing x_intel_rules.py.
Accounts are never deleted here; they are only marked for downgrade or
temporary exclusion from automatic crawling.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


STATUS_FILE = Path("graph_data/account_runtime_status.json")
FAILURE_STATUSES = {
    "not_found",
    "suspended",
    "protected",
    "renamed_suspected",
    "no_recent_posts",
    "not_found_or_empty",
    "crawl_failed",
}


def load_status(path: str | Path = STATUS_FILE) -> dict[str, Any]:
    status_path = Path(path)
    if not status_path.exists():
        return {}
    try:
        with status_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_status(data: dict[str, Any], path: str | Path = STATUS_FILE) -> None:
    status_path = Path(path)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    with status_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_account_status(handle: str) -> dict[str, Any]:
    data = load_status()
    return data.get(normalize_handle(handle), {})


def get_fail_count(handle: str) -> int:
    status = get_account_status(handle)
    try:
        return int(status.get("fail_count", 0))
    except (TypeError, ValueError):
        return 0


def should_degrade(handle: str) -> bool:
    return get_fail_count(handle) >= 2


def should_skip(handle: str) -> bool:
    status = get_account_status(handle)
    return int(status.get("fail_count", 0) or 0) >= 3 and status.get("last_status") in FAILURE_STATUSES


def record_account_failure(
    handle: str,
    status: str,
    error_message: str,
    path: str | Path = STATUS_FILE,
) -> dict[str, Any]:
    data = load_status(path)
    normalized = normalize_handle(handle)
    previous = data.get(normalized, {})
    fail_count = int(previous.get("fail_count", 0) or 0) + 1

    item = {
        "last_status": status,
        "fail_count": fail_count,
        "last_error": error_message,
        "last_checked_at": datetime.now().isoformat(timespec="seconds"),
    }
    data[normalized] = item
    save_status(data, path)
    return item


def record_account_success(handle: str, path: str | Path = STATUS_FILE) -> dict[str, Any]:
    data = load_status(path)
    normalized = normalize_handle(handle)
    previous = data.get(normalized, {})
    item = {
        "last_status": "active",
        "fail_count": 0,
        "last_error": "",
        "last_checked_at": datetime.now().isoformat(timespec="seconds"),
    }
    if previous.get("last_note"):
        item["last_note"] = previous["last_note"]
    data[normalized] = item
    save_status(data, path)
    return item


def classify_account_page(page_text: str, fallback_empty: bool = True) -> tuple[str, str]:
    text = (page_text or "").lower()
    if "this account doesn" in text and "exist" in text:
        return "not_found_or_empty", "This account doesn’t exist / No more tweets to scrape"
    if "account suspended" in text or "account has been suspended" in text:
        return "suspended", "Account suspended / No more tweets to scrape"
    if "these tweets are protected" in text or "protected tweets" in text:
        return "protected", "Protected account / No more tweets to scrape"
    if "try searching for another" in text or "doesn’t exist" in text or "doesn't exist" in text:
        return "not_found_or_empty", "This account doesn’t exist / No more tweets to scrape"
    if fallback_empty:
        return "not_found_or_empty", "No more tweets to scrape"
    return "unknown", "Unable to classify account page"


def normalize_handle(handle: str) -> str:
    text = str(handle or "").strip()
    if not text:
        return "@unknown"
    if not text.startswith("@"):
        text = f"@{text}"
    return text
