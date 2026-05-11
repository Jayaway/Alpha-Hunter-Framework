# -*- coding: utf-8 -*-
"""
DeepAlpha 石油定时情报监听模块。

职责：
  - 使用 intel_router_v2 和 x_intel_rules 生成石油监听任务
  - 使用 crawler_runner 执行抓取
  - 同时保存到原有 抓取的信息/ 和新版 data/intel/YYYY-MM-DD/
  - 记录 data/intel/monitor_state.json

运行：
  python deepalpha_runtime/monitor.py
  python deepalpha_runtime/monitor.py --once --headless
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
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = PROJECT_ROOT / "data" / "intel" / "monitor_state.json"
DEFAULT_INTERVAL_MINUTES = (25, 40)
DEFAULT_OIL_QUERY = "油价会涨吗？ 原油 OPEC 霍尔木兹 供应风险"


def main() -> None:
    os.chdir(PROJECT_ROOT)
    _ensure_project_on_path()

    parser = build_parser()
    args = parser.parse_args()

    _log("DeepAlpha oil monitor starting")
    _log(f"project_root={PROJECT_ROOT}")
    _log(f"interval_range={args.min_minutes}-{args.max_minutes} minutes")

    if args.min_minutes > args.max_minutes:
        raise ValueError("--min-minutes must be <= --max-minutes")

    while True:
        try:
            next_wait = run_once(args)
        except KeyboardInterrupt:
            _log("Interrupted by user")
            raise
        except Exception as exc:
            _log(f"monitor round failed: {exc}")
            next_wait = _random_wait_seconds(args.min_minutes, args.max_minutes)

        if args.once:
            _log("once mode complete")
            return

        _log(f"sleeping {next_wait // 60} minutes before next round")
        time.sleep(next_wait)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DeepAlpha oil intelligence monitor")
    parser.add_argument("--once", action="store_true", help="只执行一轮，便于手动验证或外部调度")
    parser.add_argument("--cookie-file", default="cookies/browser/x_cookie.json", help="Cookie 文件路径")
    parser.add_argument("-b", "--browser", default="chrome", choices=["chrome", "firefox", "safari"])
    parser.add_argument("--headless", action="store_true", help="使用无头浏览器")
    parser.add_argument("--delay", type=int, default=3, help="crawler_runner 内部任务间隔秒数")
    parser.add_argument("--min-minutes", type=int, default=DEFAULT_INTERVAL_MINUTES[0])
    parser.add_argument("--max-minutes", type=int, default=DEFAULT_INTERVAL_MINUTES[1])
    parser.add_argument("--query", default=DEFAULT_OIL_QUERY, help="用于生成石油监听任务的基础问题")
    return parser


def run_once(args: argparse.Namespace) -> int:
    _ensure_project_on_path()

    from deepalpha.crawler_runner import print_tasks, run_all_tasks, save_results

    started_at = datetime.now()
    _log("=" * 72)
    _log(f"monitor round started at {started_at.isoformat(timespec='seconds')}")

    decision = build_oil_decision(args.query)
    _log(f"decision asset={decision.get('asset')} regime={decision.get('current_regime')}")
    _log(f"top_accounts={decision.get('top_accounts')}")
    _log(f"crawl_tasks={decision.get('crawl_tasks')}")

    print_tasks(decision)

    crawl_results = run_all_tasks(
        decision,
        cookie_file=args.cookie_file,
        browser=args.browser,
        headless="yes" if args.headless else "no",
        delay_between_tasks=args.delay,
    )

    tweet_count = len(crawl_results.get("all_tweets", []))
    errors = crawl_results.get("errors", [])
    _log(f"crawl complete tweet_count={tweet_count} errors={len(errors)}")
    for error in errors:
        _log(f"crawl error: {error}")

    legacy_path = None
    dated_path = None
    if tweet_count:
        legacy_path = save_results(crawl_results)
        dated_output_dir = _dated_output_dir(started_at)
        dated_path = save_results(crawl_results, output_dir=str(dated_output_dir))
        _log(f"saved legacy_csv={legacy_path}")
        _log(f"saved dated_csv={dated_path}")
    else:
        _log("no tweets fetched; no CSV written this round")

    wait_seconds = _random_wait_seconds(args.min_minutes, args.max_minutes)
    next_run_at = datetime.now() + timedelta(seconds=wait_seconds)
    update_state(
        last_run_time=datetime.now(),
        next_run_time=next_run_at,
        last_saved_path=dated_path,
        last_legacy_saved_path=legacy_path,
        last_tweet_count=tweet_count,
    )
    _log(f"state updated: {STATE_FILE}")
    _log(f"next_run_time={next_run_at.isoformat(timespec='seconds')}")
    _log("=" * 72)

    return wait_seconds


def build_oil_decision(query: str) -> dict:
    """
    生成石油监听任务。

    intel_router_v2 负责资产/阶段和基础账号选择；
    x_intel_rules 负责补充石油账号池和关键词搜索任务。
    """
    from deepalpha.intel_router_v2 import decide
    from deepalpha.x_intel_rules import get_accounts_by_group, get_accounts_by_level, get_keyword_rules_by_domain

    decision_obj = decide(query)
    decision = decision_obj.to_dict()

    oil_accounts = get_accounts_by_group("oil")
    s_accounts = get_accounts_by_level("S")
    merged_accounts = _dedupe_accounts(
        list(decision.get("top_accounts", []))
        + list(_take(oil_accounts, 8))
        + list(_take(s_accounts, 8))
    )

    oil_rules = get_keyword_rules_by_domain("oil")
    search_tasks = build_oil_search_tasks(oil_rules)

    decision.update(
        {
            "asset": "oil",
            "top_accounts": merged_accounts[:5],
            "top_event_phrases": [
                f"{rule[0]} {rule[1]}" for rule in oil_rules[:5]
            ],
            "crawl_tasks": search_tasks,
            "why_this_route": (
                f"{decision.get('why_this_route', '')}; "
                "oil monitor merged intel_router_v2 decision with x_intel_rules oil accounts and keyword rules"
            ).strip("; "),
        }
    )
    return decision


def build_oil_search_tasks(oil_rules: Iterable[tuple]) -> list[str]:
    s_rules = [rule for rule in oil_rules if len(rule) >= 4 and rule[3] == "S"]

    supply_terms = _phrases_from_rules(
        s_rules,
        preferred_heads=("OPEC", "OPEC+", "Saudi", "EIA", "API", "crude"),
        limit=4,
    )
    geopolitics_terms = _phrases_from_rules(
        s_rules,
        preferred_heads=("Iran", "Hormuz", "Strait", "Red Sea", "tanker"),
        limit=4,
    )

    if not supply_terms:
        supply_terms = ['"OPEC cut"', '"EIA inventory"', '"crude supply"']
    if not geopolitics_terms:
        geopolitics_terms = ['"Iran Hormuz"', '"Red Sea attack"', '"tanker attack"']

    return [
        f"({' OR '.join(supply_terms)}) (oil OR crude OR Brent OR WTI)",
        f"({' OR '.join(geopolitics_terms)}) (oil OR crude OR tanker)",
    ]


def _phrases_from_rules(rules: list[tuple], preferred_heads: tuple[str, ...], limit: int) -> list[str]:
    phrases = []
    for head in preferred_heads:
        for rule in rules:
            if len(rule) < 2:
                continue
            if str(rule[0]).lower() != head.lower():
                continue
            phrase = f"{rule[0]} {rule[1]}".strip()
            phrases.append(_quote_query_phrase(phrase))
            if len(phrases) >= limit:
                return phrases
    return phrases


def update_state(
    last_run_time: datetime,
    next_run_time: datetime,
    last_saved_path: str | None,
    last_legacy_saved_path: str | None,
    last_tweet_count: int,
) -> None:
    current = load_state()
    total_runs = int(current.get("total_runs", 0)) + 1

    state = {
        "last_run_time": last_run_time.isoformat(timespec="seconds"),
        "next_run_time": next_run_time.isoformat(timespec="seconds"),
        "total_runs": total_runs,
        "last_saved_path": last_saved_path,
        "last_tweet_count": last_tweet_count,
        "last_legacy_saved_path": last_legacy_saved_path,
    }

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        with STATE_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _dated_output_dir(dt: datetime) -> Path:
    return PROJECT_ROOT / "data" / "intel" / dt.strftime("%Y-%m-%d")


def _random_wait_seconds(min_minutes: int, max_minutes: int) -> int:
    return random.randint(min_minutes * 60, max_minutes * 60)


def _dedupe_accounts(accounts: Iterable[str]) -> list[str]:
    result = []
    seen = set()
    for account in accounts:
        if not account:
            continue
        normalized = str(account).strip()
        if not normalized:
            continue
        if not normalized.startswith("@"):
            normalized = f"@{normalized}"
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def _take(items: Iterable[str], limit: int) -> list[str]:
    result = []
    for item in items:
        result.append(item)
        if len(result) >= limit:
            break
    return result


def _quote_query_phrase(phrase: str) -> str:
    escaped = phrase.replace('"', "")
    return f'"{escaped}"'


def _ensure_project_on_path() -> None:
    project_root = str(PROJECT_ROOT)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


def _log(message: str) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")
    print(f"[{timestamp}] [oil-monitor] {message}", flush=True)


if __name__ == "__main__":
    main()
