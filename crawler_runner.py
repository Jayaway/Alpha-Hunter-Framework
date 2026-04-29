# -*- coding: utf-8 -*-
"""
X 实时情报系统 - 爬虫执行器
================================================
将极速决策器的输出转化为 scraper 可执行的任务并运行。
只打开一次浏览器，复用同一个会话执行所有任务。

输入: intel_router.decide() 的输出
输出: 原始推文列表（scraper Tweet 格式）
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import Optional


def build_tasks(decision: dict) -> dict:
    """
    将决策器输出转化为可执行的抓取任务

    Returns:
        {
            "user_tasks": [{"username": "xxx", "limit": 20}, ...],
            "search_tasks": [{"query": "xxx", "limit": 30}, ...],
        }
    """
    accounts = decision.get("top_accounts", [])
    crawl_tasks = decision.get("crawl_tasks", [])

    user_tasks = []
    search_tasks = []

    for acc in accounts[:5]:
        username = acc.lstrip("@")
        user_tasks.append({"username": username, "limit": 20})

    for task in crawl_tasks[:2]:
        search_tasks.append({"query": task, "limit": 30})

    return {
        "user_tasks": user_tasks,
        "search_tasks": search_tasks,
    }


def _convert_tweets(raw_tweets: list) -> list:
    """将 scraper 原始数据转为标准字典格式"""
    tweets = []
    for t in raw_tweets:
        tweets.append({
            "name": t[0],
            "handle": t[1],
            "timestamp": t[2],
            "verified": t[3],
            "content": t[4],
            "replies": t[5],
            "retweets": t[6],
            "likes": t[7],
            "analytics": t[8],
            "tags": t[9],
            "mentions": t[10],
            "emojis": t[11],
            "profile_image": t[12],
            "tweet_link": t[13],
            "tweet_id": t[14],
        })
    return tweets


def run_all_tasks(decision: dict, cookie_file: str = "x_cookie.json",
                  browser: str = "chrome", headless: str = "no",
                  delay_between_tasks: int = 3) -> dict:
    """
    执行所有抓取任务（单次浏览器会话，复用登录态）

    核心优化：只打开一次浏览器，所有任务共用同一个 session。

    Returns:
        {
            "total_tweets": int,
            "user_results": {username: [tweets]},
            "search_results": {query: [tweets]},
            "all_tweets": [tweets],
            "errors": [str],
        }
    """
    from scraper.twitter_scraper import Twitter_Scraper

    tasks = build_tasks(decision)
    total_tasks = len(tasks["user_tasks"]) + len(tasks["search_tasks"])

    results = {
        "total_tweets": 0,
        "user_results": {},
        "search_results": {},
        "all_tweets": [],
        "errors": [],
    }

    print("=" * 60)
    print(f"  爬虫执行器 - 共 {total_tasks} 个任务，单次会话执行")
    print("=" * 60)

    # === 只创建一次 scraper，登录一次 ===
    scraper = Twitter_Scraper(
        mail="cookie_login",
        username="cookie_login",
        password="cookie_login",
        headlessState=headless,
        max_tweets=50,
        cookie_file=cookie_file,
        browser=browser,
    )

    try:
        print("\n  正在启动浏览器并登录...")
        scraper.login()
        print("  ✓ 登录成功，开始抓取\n")

        # --- 账号抓取 ---
        for i, task in enumerate(tasks["user_tasks"]):
            username = task["username"]
            limit = task["limit"]
            task_num = i + 1
            print(f"  [{task_num}/{total_tasks}] 抓取 @{username} 最近 {limit} 条...")

            try:
                # 清空上次数据
                scraper.data = []
                scraper.max_tweets = limit

                scraper.scrape_tweets(
                    max_tweets=limit,
                    scrape_username=username,
                    scrape_latest=True,
                )

                raw = scraper.get_tweets()
                tweets = _convert_tweets(raw)
                results["user_results"][username] = tweets
                results["all_tweets"].extend(tweets)
                results["total_tweets"] += len(tweets)
                print(f"    ✓ 获取 {len(tweets)} 条")
            except Exception as e:
                error_msg = f"@{username}: {e}"
                results["errors"].append(error_msg)
                print(f"    ✗ 失败: {e}")

            # 任务间短暂延迟（防频率限制，不需要等太久）
            if i < len(tasks["user_tasks"]) - 1 or tasks["search_tasks"]:
                time.sleep(delay_between_tasks)

        # --- 搜索抓取 ---
        for i, task in enumerate(tasks["search_tasks"]):
            query = task["query"]
            limit = task["limit"]
            task_num = len(tasks["user_tasks"]) + i + 1
            print(f"\n  [{task_num}/{total_tasks}] 搜索: {query[:60]}...")

            try:
                scraper.data = []
                scraper.max_tweets = limit

                scraper.scrape_tweets(
                    max_tweets=limit,
                    scrape_query=query,
                    scrape_latest=True,
                )

                raw = scraper.get_tweets()
                tweets = _convert_tweets(raw)
                results["search_results"][query] = tweets
                results["all_tweets"].extend(tweets)
                results["total_tweets"] += len(tweets)
                print(f"    ✓ 获取 {len(tweets)} 条")
            except Exception as e:
                error_msg = f"搜索'{query[:30]}': {e}"
                results["errors"].append(error_msg)
                print(f"    ✗ 失败: {e}")

            if i < len(tasks["search_tasks"]) - 1:
                time.sleep(delay_between_tasks)

    finally:
        # 所有任务完成后才关闭浏览器
        print(f"\n  正在关闭浏览器...")
        try:
            scraper.driver.quit()
        except Exception:
            pass

    print(f"\n{'=' * 60}")
    print(f"  抓取完成: {results['total_tweets']} 条推文, {len(results['errors'])} 个错误")
    print(f"{'=' * 60}")

    return results


def save_results(results: dict, output_dir: str = "./抓取的信息/"):
    """保存抓取结果到CSV"""
    import pandas as pd

    if not results["all_tweets"]:
        print("  无数据可保存")
        return

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filepath = os.path.join(output_dir, f"{timestamp}_intel_{len(results['all_tweets'])}.csv")

    df = pd.DataFrame(results["all_tweets"])
    df.to_csv(filepath, index=False, encoding="utf-8")
    print(f"  CSV已保存: {filepath}")
    return filepath


def print_tasks(decision: dict):
    """打印将要执行的任务（不实际抓取）"""
    tasks = build_tasks(decision)

    print(f"\n  账号抓取任务 ({len(tasks['user_tasks'])} 个):")
    for t in tasks["user_tasks"]:
        print(f"    @{t['username']}  →  最近 {t['limit']} 条")

    print(f"\n  搜索抓取任务 ({len(tasks['search_tasks'])} 个):")
    for t in tasks["search_tasks"]:
        print(f"    {t['query'][:70]}{'...' if len(t['query']) > 70 else ''}  →  {t['limit']} 条")

    total = sum(t["limit"] for t in tasks["user_tasks"]) + \
            sum(t["limit"] for t in tasks["search_tasks"])
    print(f"\n  预计总抓取: {total} 条")
