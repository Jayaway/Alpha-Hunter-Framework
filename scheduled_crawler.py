# -*- coding: utf-8 -*-
"""
低频定时刷新抓取库。

用途：以较低频率刷新本地历史情报库，让用户提问时优先走历史分析。
随机抖动只用于错峰和降低请求冲击，不用于规避平台风控。
"""

import argparse
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timezone


DEFAULT_QUERIES = [
    "油价会涨吗？",
    "黄金走势？",
    "比特币会涨吗？",
]
STATE_FILE = "./graph_data/scheduler_state.json"
LOCK_FILE = "./graph_data/scheduler.lock"


def main():
    parser = argparse.ArgumentParser(description="低频定时刷新历史情报库")
    parser.add_argument("--queries", nargs="*", default=DEFAULT_QUERIES, help="要定时刷新的问题列表")
    parser.add_argument("--interval-minutes", type=int, default=120, help="基础间隔，默认120分钟")
    parser.add_argument("--jitter-minutes", type=int, default=25, help="随机错峰窗口，默认0-25分钟")
    parser.add_argument("--once", action="store_true", help="只执行一次检查，适合系统 cron/自动化调用")
    parser.add_argument("--headless", action="store_true", help="抓取时使用无头浏览器")
    args = parser.parse_args()

    while True:
        run_once(args)
        if args.once:
            return
        sleep_seconds = args.interval_minutes * 60 + random.randint(0, args.jitter_minutes * 60)
        print(f"下次刷新约在 {sleep_seconds // 60} 分钟后")
        time.sleep(sleep_seconds)


def run_once(args):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

    if os.path.exists(LOCK_FILE):
        print("已有刷新任务在运行，跳过本轮。")
        return

    state = load_state()
    now = time.time()
    next_due = state.get("next_due", 0)
    if now < next_due:
        remain = int((next_due - now) // 60)
        print(f"尚未到刷新时间，约 {remain} 分钟后可执行。")
        return

    jitter_seconds = random.randint(0, max(args.jitter_minutes, 0) * 60)
    if jitter_seconds:
        print(f"随机错峰等待 {jitter_seconds // 60} 分钟。")
        time.sleep(jitter_seconds)

    with open(LOCK_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))

    try:
        for query in args.queries:
            run_query(query, args.headless)
        state = {
            "last_run": datetime.now(timezone.utc).isoformat(),
            "next_due": time.time() + args.interval_minutes * 60 + random.randint(0, args.jitter_minutes * 60),
        }
        save_state(state)
    finally:
        try:
            os.remove(LOCK_FILE)
        except FileNotFoundError:
            pass


def run_query(query: str, headless: bool):
    cmd = [sys.executable, "run.py", query, "--crawl"]
    if headless:
        cmd.append("--headless")
    print(f"刷新: {query}")
    subprocess.run(cmd, check=False)


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
