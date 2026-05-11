# -*- coding: utf-8 -*-
"""
Local DeepAlpha intelligence store reader.

Reads JSONL files under data/intel/ and returns normalized records for
analysis modules or future run.py integration.

Example:
  python3 local_intel_store.py --asset oil --hours 24
  python3 local_intel_store.py --asset oil --hours 6 --keyword Hormuz --account @Reuters
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_STORE_DIR = Path("data/intel")
TIME_FIELDS = ("timestamp", "created_at", "collected_at", "saved_at", "time")
CONTENT_FIELDS = ("content", "text", "full_text", "body")
ACCOUNT_FIELDS = ("handle", "account", "username", "user", "source")
ID_FIELDS = ("tweet_id", "id", "rest_id")
URL_FIELDS = ("tweet_link", "url", "link")


@dataclass
class IntelRecord:
    record_id: str | None
    asset: str | None
    timestamp: datetime | None
    account: str | None
    content: str
    url: str | None = None
    source_file: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.record_id,
            "asset": self.asset,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "account": self.account,
            "content": self.content,
            "url": self.url,
            "source_file": self.source_file,
            "raw": self.raw,
        }


def read_intel(
    store_dir: str | Path = DEFAULT_STORE_DIR,
    asset: str | None = None,
    hours: int | float | None = None,
    days: int | float | None = None,
    since: datetime | str | None = None,
    until: datetime | str | None = None,
    keywords: Iterable[str] | None = None,
    accounts: Iterable[str] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """
    Read normalized local intelligence records.

    Returns a list of dictionaries so callers can consume the result without
    depending on the dataclass.
    """
    records = read_records(
        store_dir=store_dir,
        asset=asset,
        hours=hours,
        days=days,
        since=since,
        until=until,
        keywords=keywords,
        accounts=accounts,
        limit=limit,
    )
    return [record.to_dict() for record in records]


def read_records(
    store_dir: str | Path = DEFAULT_STORE_DIR,
    asset: str | None = None,
    hours: int | float | None = None,
    days: int | float | None = None,
    since: datetime | str | None = None,
    until: datetime | str | None = None,
    keywords: Iterable[str] | None = None,
    accounts: Iterable[str] | None = None,
    limit: int | None = None,
) -> list[IntelRecord]:
    store_path = Path(store_dir)
    if not store_path.exists():
        return []

    since_dt, until_dt = build_time_window(hours=hours, days=days, since=since, until=until)
    keyword_list = [k.lower() for k in (keywords or []) if str(k).strip()]
    account_set = {_normalize_account(a) for a in (accounts or []) if str(a).strip()}

    records: list[IntelRecord] = []
    for path in iter_jsonl_files(store_path):
        for raw in iter_jsonl(path):
            record = normalize_record(raw, source_file=path)
            if not record:
                continue
            if asset and (record.asset or "").lower() != asset.lower():
                continue
            if not _matches_time(record, since_dt, until_dt):
                continue
            if keyword_list and not _matches_keywords(record, keyword_list):
                continue
            if account_set and _normalize_account(record.account) not in account_set:
                continue
            records.append(record)

    records.sort(key=lambda item: item.timestamp or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    if limit is not None:
        records = records[:limit]
    return records


def iter_jsonl_files(store_path: Path) -> list[Path]:
    return sorted(store_path.glob("**/*.jsonl"))


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            text = line.strip()
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                yield value


def normalize_record(raw: dict[str, Any], source_file: Path | None = None) -> IntelRecord | None:
    content = _first_value(raw, CONTENT_FIELDS)
    if content is None:
        return None

    account = _normalize_account(_first_value(raw, ACCOUNT_FIELDS))
    timestamp = parse_datetime(_first_value(raw, TIME_FIELDS))
    asset = raw.get("asset")

    return IntelRecord(
        record_id=_to_str(_first_value(raw, ID_FIELDS)),
        asset=_to_str(asset),
        timestamp=timestamp,
        account=account,
        content=str(content),
        url=_to_str(_first_value(raw, URL_FIELDS)),
        source_file=str(source_file) if source_file else None,
        raw=raw,
    )


def build_time_window(
    hours: int | float | None = None,
    days: int | float | None = None,
    since: datetime | str | None = None,
    until: datetime | str | None = None,
) -> tuple[datetime | None, datetime | None]:
    until_dt = parse_datetime(until) if isinstance(until, str) else until
    since_dt = parse_datetime(since) if isinstance(since, str) else since

    if until_dt is None:
        until_dt = datetime.now(timezone.utc)
    else:
        until_dt = _ensure_aware(until_dt)

    if since_dt is not None:
        since_dt = _ensure_aware(since_dt)
    elif hours is not None:
        since_dt = until_dt - timedelta(hours=float(hours))
    elif days is not None:
        since_dt = until_dt - timedelta(days=float(days))

    return since_dt, until_dt


def parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _ensure_aware(value)

    text = str(value).strip()
    if not text:
        return None

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    for candidate in (text, text.replace(" ", "T")):
        try:
            return _ensure_aware(datetime.fromisoformat(candidate))
        except ValueError:
            pass

    common_formats = (
        "%a %b %d %H:%M:%S %z %Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d_%H-%M-%S",
    )
    for fmt in common_formats:
        try:
            return _ensure_aware(datetime.strptime(text, fmt))
        except ValueError:
            pass
    return None


def _matches_time(record: IntelRecord, since: datetime | None, until: datetime | None) -> bool:
    if since is None and until is None:
        return True
    if record.timestamp is None:
        return False
    ts = _ensure_aware(record.timestamp)
    if since is not None and ts < since:
        return False
    if until is not None and ts > until:
        return False
    return True


def _matches_keywords(record: IntelRecord, keywords: list[str]) -> bool:
    content = record.content.lower()
    return any(keyword in content for keyword in keywords)


def _normalize_account(value: Any) -> str | None:
    text = _to_str(value)
    if not text:
        return None
    text = text.strip()
    if not text:
        return None
    if not text.startswith("@"):
        text = f"@{text}"
    return text


def _first_value(raw: dict[str, Any], fields: Iterable[str]) -> Any:
    for field_name in fields:
        value = raw.get(field_name)
        if value is not None and str(value) != "nan":
            return value
    return None


def _to_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read DeepAlpha local intelligence JSONL store")
    parser.add_argument("--store-dir", default=str(DEFAULT_STORE_DIR), help="JSONL store directory")
    parser.add_argument("--asset", default=None, help="Asset filter, e.g. oil")
    parser.add_argument("--hours", type=float, default=None, help="Read records from the last N hours")
    parser.add_argument("--days", type=float, default=None, help="Read records from the last N days")
    parser.add_argument("--since", default=None, help="Start time, ISO format")
    parser.add_argument("--until", default=None, help="End time, ISO format")
    parser.add_argument("--keyword", action="append", default=[], help="Keyword filter; can be repeated")
    parser.add_argument("--account", action="append", default=[], help="Account filter; can be repeated")
    parser.add_argument("--limit", type=int, default=20, help="Maximum records to print")
    parser.add_argument("--json", action="store_true", help="Print full normalized records as JSON")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    records = read_records(
        store_dir=args.store_dir,
        asset=args.asset,
        hours=args.hours,
        days=args.days,
        since=args.since,
        until=args.until,
        keywords=args.keyword,
        accounts=args.account,
        limit=args.limit,
    )

    print(f"records={len(records)} store_dir={args.store_dir}")
    if args.json:
        print(json.dumps([record.to_dict() for record in records], ensure_ascii=False, indent=2))
        return

    for record in records:
        timestamp = record.timestamp.isoformat() if record.timestamp else "unknown-time"
        account = record.account or "unknown-account"
        asset = record.asset or "unknown-asset"
        content = record.content.replace("\n", " ")[:160]
        print(f"- [{timestamp}] [{asset}] {account}: {content}")


if __name__ == "__main__":
    main()
