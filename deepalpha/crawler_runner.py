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
import logging
import time
import traceback
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
    max_accounts = int(decision.get("accounts_per_round", 5) or 5)
    tweets_per_account = int(decision.get("tweets_per_account", 20) or 20)

    user_tasks = []
    search_tasks = []

    from deepalpha.account_status import should_degrade_account, should_skip_account

    for acc in accounts[:max_accounts]:
        username = acc.lstrip("@")
        handle = f"@{username}"
        if should_skip_account(handle):
            print(f"  [账号状态] {handle} fail_count>=3，暂不参与自动抓取，需人工确认后恢复。")
            continue
        if should_degrade_account(handle):
            print(f"  [账号状态] {handle} fail_count>=2，本轮降级抓取。")
            user_tasks.append({"username": username, "limit": min(tweets_per_account, 10), "runtime_status": "degraded"})
            continue
        user_tasks.append({"username": username, "limit": tweets_per_account, "runtime_status": "normal"})

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


def _account_empty_error(page_text: str) -> str:
    text = (page_text or "").lower()
    if "this account doesn" in text and "exist" in text:
        return "This account doesn’t exist / No more tweets to scrape"
    if "doesn’t exist" in text or "doesn't exist" in text:
        return "This account doesn’t exist / No more tweets to scrape"
    if "account suspended" in text or "account has been suspended" in text:
        return "Account suspended / No more tweets to scrape"
    if "protected tweets" in text or "these tweets are protected" in text:
        return "Protected account / No more tweets to scrape"
    return "No more tweets to scrape"


def run_all_tasks(decision: dict, cookie_file: str = "cookies/browser/x_cookie.json",
                  browser: str = "chrome", headless: str = "no",
                  delay_between_tasks: int = 3, debug: bool = False) -> dict:
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
    tasks = build_tasks(decision)
    total_tasks = len(tasks["user_tasks"]) + len(tasks["search_tasks"])

    results = {
        "total_tweets": 0,
        "user_results": {},
        "search_results": {},
        "all_tweets": [],
        "errors": [],
        "account_runtime_status": {},
    }

    print("=" * 60)
    print(f"  爬虫执行器 - 共 {total_tasks} 个任务，单次会话执行")
    print("=" * 60)

    # === 只创建一次 scraper，登录一次 ===
    scraper = None
    
    try:
        from scraper.twitter_scraper import Twitter_Scraper
        from deepalpha.account_status import mark_account_failure, mark_account_success

        scraper = Twitter_Scraper(
            mail="cookie_login",
            username="cookie_login",
            password="cookie_login",
            headlessState=headless,
            max_tweets=50,
            cookie_file=cookie_file,
            browser=browser,
        )

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

                if tweets:
                    status_item = mark_account_success(f"@{username}", len(tweets))
                    results["account_runtime_status"][f"@{username}"] = status_item
                else:
                    try:
                        page_text = scraper.driver.page_source
                    except Exception:
                        page_text = ""
                    status_error = _account_empty_error(page_text)
                    status_item = mark_account_failure(f"@{username}", status_error)
                    results["account_runtime_status"][f"@{username}"] = status_item
                    results["errors"].append(f"@{username}: {status_error}")
                    print(f"    ! 账号状态记录: {status_item['last_status']} (fail_count={status_item['fail_count']})")
            except Exception as e:
                error_msg = f"@{username}: {e}"
                logging.exception("profile crawl failed: @%s", username)
                status_item = mark_account_failure(f"@{username}", str(e))
                results["account_runtime_status"][f"@{username}"] = status_item
                results["errors"].append(error_msg)
                print(f"    ✗ 失败: {e} (fail_count={status_item['fail_count']})")
                if debug:
                    traceback.print_exc()

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
                logging.exception("search crawl failed: %s", query[:80])
                results["errors"].append(error_msg)
                print(f"    ✗ 失败: {e}")
                if debug:
                    traceback.print_exc()

            if i < len(tasks["search_tasks"]) - 1:
                time.sleep(delay_between_tasks)

    except Exception as e:
        # 登录或其他严重错误
        error_msg = f"爬虫执行失败: {str(e)[:100]}"
        logging.exception("crawler run failed")
        results["errors"].append(error_msg)
        print(f"\n  ✗ 爬虫执行失败: {e}")
        if debug:
            traceback.print_exc()
        return results
        
    finally:
        # 所有任务完成后才关闭浏览器
        print(f"\n  正在关闭浏览器...")
        if scraper:
            try:
                scraper.driver.quit()
            except Exception as e:
                print(f"    关闭浏览器时出错: {e}")

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
        suffix = " [降级]" if t.get("runtime_status") == "degraded" else ""
        print(f"    @{t['username']}  →  最近 {t['limit']} 条{suffix}")

    print(f"\n  搜索抓取任务 ({len(tasks['search_tasks'])} 个):")
    for t in tasks["search_tasks"]:
        print(f"    {t['query'][:70]}{'...' if len(t['query']) > 70 else ''}  →  {t['limit']} 条")

    total = sum(t["limit"] for t in tasks["user_tasks"]) + \
            sum(t["limit"] for t in tasks["search_tasks"])
    print(f"\n  预计总抓取: {total} 条")
