# -*- coding: utf-8 -*-
"""
DeepAlpha oil intelligence monitor.

This module is a low-frequency local scheduler for the oil scenario. It does
not modify or bypass the scraper layer; every crawl is delegated to
crawler_runner.py.

Example:
  python3 deepalpha_runtime/oil_monitor.py --asset oil
  python3 deepalpha_runtime/oil_monitor.py --asset oil --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = PROJECT_ROOT / "graph_data" / "monitor_state.json"
DEFAULT_SCENARIO_QUERIES = {
    "supply_risk": "oil supply disruption OPEC cut Brent WTI",
    "geopolitics": "Iran Israel Middle East sanction oil",
    "opec_policy": "OPEC Saudi production cut increase oil",
    "shipping_risk": "Hormuz Red Sea tanker shipping oil",
}


def main() -> None:
    os.chdir(PROJECT_ROOT)
    _ensure_project_on_path()

    parser = build_parser()
    args = parser.parse_args()

    if args.asset != "oil":
        raise ValueError("oil_monitor currently supports --asset oil only")
    if args.min_interval > args.max_interval:
        raise ValueError("--min-interval must be <= --max-interval")
    if args.accounts_per_round <= 0:
        raise ValueError("--accounts-per-round must be positive")
    if args.tweets_per_account <= 0:
        raise ValueError("--tweets-per-account must be positive")

    _log("DeepAlpha oil monitor starting")
    _log(f"project_root={PROJECT_ROOT}")
    _log(
        "config "
        f"accounts_per_round={args.accounts_per_round}, "
        f"tweets_per_account={args.tweets_per_account}, "
        f"interval={args.min_interval}-{args.max_interval} minutes, "
        f"max_rounds={args.max_rounds}, dry_run={args.dry_run}"
    )

    completed = 0
    while True:
        wait_seconds = run_round(args)
        completed += 1

        if args.dry_run:
            _log("dry-run complete; no crawl executed")
            return
        if args.max_rounds and completed >= args.max_rounds:
            _log(f"max_rounds reached: {args.max_rounds}")
            return

        _log(f"sleeping {wait_seconds // 60} minutes before next round")
        time.sleep(wait_seconds)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DeepAlpha oil monitor")
    parser.add_argument("--asset", default="oil", choices=["oil"], help="currently only oil is supported")
    parser.add_argument("--accounts-per-round", type=int, default=10)
    parser.add_argument("--tweets-per-account", type=int, default=8)
    parser.add_argument("--min-interval", type=int, default=25, help="minimum interval in minutes")
    parser.add_argument("--max-interval", type=int, default=40, help="maximum interval in minutes")
    parser.add_argument("--max-rounds", type=int, default=0, help="0 means run continuously")
    parser.add_argument("--dry-run", action="store_true", help="print selected accounts only")
    parser.add_argument("--cookie-file", default="x_cookie.json")
    parser.add_argument("-b", "--browser", default="chrome", choices=["chrome", "firefox", "safari"])
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--delay", type=int, default=3, help="crawler_runner task delay in seconds")
    return parser


def run_round(args: argparse.Namespace) -> int:
    started_at = datetime.now()
    next_wait = random.randint(args.min_interval * 60, args.max_interval * 60)
    next_run_at = datetime.now() + timedelta(seconds=next_wait)

    _log("=" * 72)
    _log(f"round_start={started_at.isoformat(timespec='seconds')}")

    selection = select_accounts(args.accounts_per_round, update_status=not args.dry_run)
    selected_accounts = selection["selected_accounts"]
    skipped_accounts = selection["skipped_accounts"]
    selected_reason = selection["selected_reason"]

    _log(f"selected_accounts={selected_accounts}")
    if skipped_accounts:
        _log(f"skipped_accounts={skipped_accounts}")
    else:
        _log("skipped_accounts=[]")

    if args.dry_run:
        print(json.dumps(selection, ensure_ascii=False, indent=2))
        _log(f"next_run_time_preview={next_run_at.isoformat(timespec='seconds')}")
        _log("=" * 72)
        return next_wait

    from crawler_runner import run_all_tasks, save_results

    decision = build_monitor_decision(
        selected_accounts=selected_accounts,
        tweets_per_account=args.tweets_per_account,
        accounts_per_round=args.accounts_per_round,
    )

    crawl_results = run_all_tasks(
        decision,
        cookie_file=args.cookie_file,
        browser=args.browser,
        headless="yes" if args.headless else "no",
        delay_between_tasks=args.delay,
    )

    tweet_count = int(crawl_results.get("total_tweets", 0) or 0)
    _log(f"crawl_tweet_count={tweet_count}")
    for error in crawl_results.get("errors", []):
        _log(f"crawl_error={error}")

    saved_path = None
    legacy_csv_path = None
    if tweet_count:
        records = normalize_records(
            crawl_results=crawl_results,
            selected_reason=selected_reason,
            crawl_time=started_at,
        )
        saved_path = save_jsonl(records, started_at)
        legacy_csv_path = save_results(crawl_results)
        _log(f"saved_jsonl={saved_path}")
        _log(f"saved_legacy_csv={legacy_csv_path}")
    else:
        _log("no tweets fetched; JSONL and CSV were not written")

    update_monitor_state(
        last_run_time=started_at,
        next_run_time=next_run_at,
        selected_accounts=selected_accounts,
        skipped_accounts=skipped_accounts,
        last_saved_path=saved_path,
        last_legacy_csv_path=legacy_csv_path,
        last_tweet_count=tweet_count,
        errors=crawl_results.get("errors", []),
    )

    _log(f"state_updated={STATE_FILE}")
    _log(f"next_run_time={next_run_at.isoformat(timespec='seconds')}")
    _log("=" * 72)
    return next_wait


def select_accounts(accounts_per_round: int, update_status: bool = True) -> dict[str, Any]:
    import account_status
    from account_status import load_account_status, save_account_status
    from intel_router_v2 import decide
    from x_intel_rules import get_accounts_by_group, get_accounts_by_level

    status = load_account_status()

    router_accounts: list[str] = []
    scenario_router_accounts: dict[str, list[str]] = {}
    original_status_file = account_status.STATUS_FILE
    if not update_status:
        account_status.STATUS_FILE = Path("/private/tmp/deepalpha_oil_monitor_dry_run_account_status.json")
    try:
        for scenario, query in DEFAULT_SCENARIO_QUERIES.items():
            decision = decide(query).to_dict()
            accounts = _dedupe_accounts(
                decision.get("selected_accounts", []) or decision.get("top_accounts", [])
            )
            scenario_router_accounts[scenario] = accounts
            router_accounts.extend(accounts)
    finally:
        account_status.STATUS_FILE = original_status_file

    core_pool = _dedupe_accounts(
        get_accounts_by_level("S")
        + scenario_router_accounts.get("supply_risk", [])
        + scenario_router_accounts.get("shipping_risk", [])
    )
    scenario_pool = _dedupe_accounts(
        router_accounts
        + get_accounts_by_group("oil")
        + get_accounts_by_group("geopolitics")
        + get_accounts_by_group("leaders")
        + get_accounts_by_group("journalist")
    )
    exploration_pool = _dedupe_accounts(
        get_accounts_by_level("B")
        + get_accounts_by_level("C")
        + get_accounts_by_group("oil")
    )

    all_candidates = _dedupe_accounts(core_pool + scenario_pool + exploration_pool)
    skipped_accounts: list[dict[str, Any]] = []
    available_core = _filter_available(core_pool, status, skipped_accounts)
    available_scenario = _filter_available(scenario_pool, status, skipped_accounts)
    available_exploration = _filter_available(exploration_pool, status, skipped_accounts)
    review_pool = _review_pool(all_candidates, status)

    selected: list[str] = []
    selected_reason: dict[str, str] = {}

    def add_accounts(accounts: list[str], reason: str) -> None:
        for account in accounts:
            if len(selected) >= accounts_per_round:
                return
            handle = _normalize_handle(account)
            if not handle or handle in selected:
                continue
            selected.append(handle)
            selected_reason[handle] = reason

    core_target = min(random.randint(1, 2), accounts_per_round)
    add_accounts(_sample(available_core, core_target), "core_accounts: high-trust source")

    remaining = accounts_per_round - len(selected)
    scenario_target = min(random.randint(4, 6), max(remaining, 0))
    add_accounts(
        _sample(available_scenario, scenario_target),
        "scenario_accounts: supply/geopolitics/opec/shipping",
    )

    remaining = accounts_per_round - len(selected)
    exploration_target = min(random.randint(2, 4), max(remaining, 0))
    add_accounts(_sample(available_exploration, exploration_target), "exploration_accounts: B/C random source")

    remaining = accounts_per_round - len(selected)
    review_target = min(random.randint(0, 2), max(remaining, 0))
    for account in _sample(review_pool, review_target):
        handle = _normalize_handle(account)
        fail_count = int(status.get(handle, {}).get("fail_count", 0) or 0)
        add_accounts([handle], f"review_accounts: previous fail_count={fail_count}")

    if len(selected) < accounts_per_round:
        fill_pool = _dedupe_accounts(available_scenario + available_core + available_exploration)
        add_accounts(_sample(fill_pool, accounts_per_round - len(selected)), "fill_accounts: available candidate")

    if skipped_accounts and update_status:
        save_account_status(status)

    return {
        "candidate_accounts": all_candidates,
        "selected_accounts": selected[:accounts_per_round],
        "selected_reason": selected_reason,
        "skipped_accounts": _dedupe_skipped(skipped_accounts),
        "scenario_router_accounts": scenario_router_accounts,
        "selection_policy": {
            "core_accounts": "1-2 high-trust accounts",
            "scenario_accounts": "4-6 supply/geopolitics/opec/shipping accounts",
            "exploration_accounts": "2-4 B/C random accounts",
            "review_accounts": "0-2 previously failed but not disabled accounts",
        },
    }


def build_monitor_decision(
    selected_accounts: list[str],
    tweets_per_account: int,
    accounts_per_round: int,
) -> dict[str, Any]:
    return {
        "asset": "oil",
        "user_intent": "持续情报监测",
        "current_regime": "oil_monitor",
        "urgency": "normal",
        "top_accounts": selected_accounts,
        "selected_accounts": selected_accounts,
        "candidate_accounts": selected_accounts,
        "excluded_accounts": [],
        "account_selection_reason": "oil_monitor dynamic account rotation",
        "top_event_phrases": [],
        "crawl_tasks": [],
        "why_this_route": "石油场景低频持续监听，按核心/场景/探索/复检动态轮换账号",
        "accounts_per_round": accounts_per_round,
        "tweets_per_account": tweets_per_account,
    }


def normalize_records(
    crawl_results: dict[str, Any],
    selected_reason: dict[str, str],
    crawl_time: datetime,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen = set()
    crawl_time_text = crawl_time.isoformat(timespec="seconds")

    for username, tweets in crawl_results.get("user_results", {}).items():
        handle = _normalize_handle(username)
        for tweet in tweets:
            record = build_record(
                tweet=tweet,
                source_task=f"user:{handle}",
                selected_reason=selected_reason.get(handle, "account_task"),
                crawl_time=crawl_time_text,
            )
            key = record.get("tweet_id") or record.get("tweet_url") or record.get("content")
            if key in seen:
                continue
            seen.add(key)
            records.append(record)

    for query, tweets in crawl_results.get("search_results", {}).items():
        for tweet in tweets:
            handle = _normalize_handle(tweet.get("handle", ""))
            record = build_record(
                tweet=tweet,
                source_task=f"search:{query}",
                selected_reason=selected_reason.get(handle, "keyword_search"),
                crawl_time=crawl_time_text,
            )
            key = record.get("tweet_id") or record.get("tweet_url") or record.get("content")
            if key in seen:
                continue
            seen.add(key)
            records.append(record)

    return records


def build_record(
    tweet: dict[str, Any],
    source_task: str,
    selected_reason: str,
    crawl_time: str,
) -> dict[str, Any]:
    handle = _normalize_handle(tweet.get("handle", ""))
    tweet_url = tweet.get("tweet_link") or tweet.get("tweet_url") or ""
    return {
        "tweet_id": str(tweet.get("tweet_id") or _tweet_id_from_url(tweet_url)),
        "author": tweet.get("name") or "",
        "handle": handle,
        "content": tweet.get("content") or "",
        "timestamp": tweet.get("timestamp") or "",
        "crawl_time": crawl_time,
        "source_task": source_task,
        "selected_reason": selected_reason,
        "tweet_url": tweet_url,
    }


def save_jsonl(records: list[dict[str, Any]], started_at: datetime) -> str:
    output_dir = PROJECT_ROOT / "data" / "intel" / "oil" / started_at.strftime("%Y-%m-%d")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"round_{started_at.strftime('%Y%m%d_%H%M%S')}.jsonl"
    with output_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return str(output_path)


def update_monitor_state(
    last_run_time: datetime,
    next_run_time: datetime,
    selected_accounts: list[str],
    skipped_accounts: list[dict[str, Any]],
    last_saved_path: str | None,
    last_legacy_csv_path: str | None,
    last_tweet_count: int,
    errors: list[str],
) -> None:
    current = load_monitor_state()
    state = {
        "last_run_time": last_run_time.isoformat(timespec="seconds"),
        "next_run_time": next_run_time.isoformat(timespec="seconds"),
        "total_runs": int(current.get("total_runs", 0) or 0) + 1,
        "last_saved_path": last_saved_path,
        "last_legacy_csv_path": last_legacy_csv_path,
        "last_tweet_count": last_tweet_count,
        "last_selected_accounts": selected_accounts,
        "last_skipped_accounts": skipped_accounts,
        "last_errors": errors,
    }
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_monitor_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        with STATE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _filter_available(
    accounts: Iterable[str],
    status: dict[str, Any],
    skipped_accounts: list[dict[str, Any]],
) -> list[str]:
    available = []
    for account in accounts:
        handle = _normalize_handle(account)
        runtime = status.get(handle, {})
        fail_count = _safe_int(runtime.get("fail_count", 0))
        if fail_count >= 3:
            runtime["last_status"] = "cooldown"
            status[handle] = runtime
            skipped_accounts.append(
                {
                    "handle": handle,
                    "reason": "fail_count>=3",
                    "last_status": runtime.get("last_status"),
                    "fail_count": fail_count,
                    "last_error": runtime.get("last_error", ""),
                }
            )
            continue
        available.append(handle)
    return _dedupe_accounts(available)


def _review_pool(candidates: Iterable[str], status: dict[str, Any]) -> list[str]:
    candidate_set = {account.lower() for account in _dedupe_accounts(candidates)}
    review = []
    for handle, runtime in status.items():
        normalized = _normalize_handle(handle)
        fail_count = _safe_int(runtime.get("fail_count", 0))
        if fail_count <= 0 or fail_count >= 3:
            continue
        if normalized.lower() in candidate_set:
            review.append(normalized)
    return _dedupe_accounts(review)


def _sample(accounts: list[str], count: int) -> list[str]:
    accounts = _dedupe_accounts(accounts)
    if count <= 0 or not accounts:
        return []
    return random.sample(accounts, min(count, len(accounts)))


def _dedupe_accounts(accounts: Iterable[str]) -> list[str]:
    result = []
    seen = set()
    for account in accounts:
        handle = _normalize_handle(account)
        if not handle:
            continue
        key = handle.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(handle)
    return result


def _dedupe_skipped(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for item in items:
        handle = _normalize_handle(item.get("handle", ""))
        key = handle.lower()
        if not handle or key in seen:
            continue
        copied = dict(item)
        copied["handle"] = handle
        seen.add(key)
        result.append(copied)
    return result


def _normalize_handle(handle: str) -> str:
    text = str(handle or "").strip()
    if not text:
        return ""
    if not text.startswith("@"):
        text = f"@{text}"
    return text


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _tweet_id_from_url(url: str) -> str:
    text = str(url or "").rstrip("/")
    if not text:
        return ""
    return text.split("/")[-1]


def _ensure_project_on_path() -> None:
    project_root = str(PROJECT_ROOT)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


def _log(message: str) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")
    print(f"[{timestamp}] [oil-monitor] {message}", flush=True)


if __name__ == "__main__":
    main()
