# -*- coding: utf-8 -*-
"""
X 实时情报系统 - 一键运行入口
================================================
用户一句话 → 抓取 → 清洗 → 信号判断 → 输出报告

用法:
  python3 run.py "油价会涨吗？"
  python3 run.py "黄金还能涨吗？" --dry-run    # 只看决策，不抓取
  python3 run.py "美联储下周降息？" --no-clean   # 跳过清洗
"""

import argparse
import json
import sys
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(
        description="X 实时情报系统 - 价格问题驱动的极速情报筛选器",
        usage='python3 run.py "你的市场问题" [选项]',
    )
    parser.add_argument("query", type=str, help="市场问题，如：油价会涨吗？")
    parser.add_argument("--dry-run", action="store_true", help="只显示决策，不执行抓取")
    parser.add_argument("--no-clean", action="store_true", help="跳过数据清洗")
    parser.add_argument("--no-judge", action="store_true", help="跳过信号判断")
    parser.add_argument("--cookie-file", type=str, default="x_cookie.json", help="Cookie文件路径")
    parser.add_argument("-b", "--browser", type=str, default="chrome", choices=["chrome", "firefox", "safari"])
    parser.add_argument("--headless", action="store_true", help="无头模式")
    parser.add_argument("--delay", type=int, default=3, help="任务间延迟秒数（默认3秒）")
    parser.add_argument("--output", type=str, default=None, help="输出JSON文件路径")

    args = parser.parse_args()

    query = args.query
    print(f"\n{'=' * 60}")
    print(f"  X 实时情报系统")
    print(f"  查询: {query}")
    print(f"{'=' * 60}\n")

    # ============================================================
    # Step 1: 极速决策
    # ============================================================
    from intel_router import decide, print_decision

    decision = decide(query)
    print_decision(decision)
    print()

    if args.dry_run:
        print("  [DRY RUN] 仅显示决策，不执行抓取。")
        print()

        # 显示将要执行的任务
        from crawler_runner import print_tasks
        print("  将要执行的任务:")
        print("-" * 40)
        print_tasks(decision)
        return

    # ============================================================
    # Step 2: 执行抓取
    # ============================================================
    from crawler_runner import run_all_tasks, save_results

    crawl_results = run_all_tasks(
        decision,
        cookie_file=args.cookie_file,
        browser=args.browser,
        headless="yes" if args.headless else "no",
        delay_between_tasks=args.delay,
    )

    if not crawl_results["all_tweets"]:
        print("\n  未抓取到任何推文，流程结束。")
        return

    # 保存原始数据
    csv_path = save_results(crawl_results)

    all_tweets = crawl_results["all_tweets"]
    print(f"\n  原始推文: {len(all_tweets)} 条")

    # ============================================================
    # Step 3: 数据清洗（可选）
    # ============================================================
    cleaned_tweets = all_tweets

    if not args.no_clean:
        print(f"\n{'─' * 60}")
        print("  Step 3: 数据清洗")
        print(f"{'─' * 60}")

        from data_cleaner import Tweet as CleanTweet, clean_pipeline

        # 转换格式
        clean_input = []
        for t in all_tweets:
            ct = CleanTweet(
                tweet_id=t.get("tweet_id"),
                username=t.get("handle", "").lstrip("@"),
                content=t.get("content", ""),
                timestamp=t.get("timestamp"),
                likes=_parse_count(t.get("likes")),
                retweets=_parse_count(t.get("retweets")),
                replies=_parse_count(t.get("replies")),
                impressions=_parse_count(t.get("analytics")),
                is_verified=t.get("verified", False),
                is_retweet=False,
                has_media=False,
                media_urls=[], links=[], hashtags=t.get("tags", []),
                mentions=t.get("mentions", []),
            )
            clean_input.append(ct)

        cleaned = clean_pipeline(clean_input, verbose=True)

        # 只保留actionable + noteworthy
        filtered = [t for t in cleaned if t._final_verdict in ("actionable", "noteworthy")]
        cleaned_tweets = [
            {
                "handle": f"@{t.username}",
                "content": t.content,
                "likes": t.likes,
                "retweets": t.retweets,
                "verified": t.is_verified,
                "_final_score": t._final_score,
                "_final_verdict": t._final_verdict,
                "_source_score": t._source_score,
                "_hearsay_flag": t._hearsay_flag,
                "_cross_verify_score": t._cross_verify_score,
            }
            for t in filtered
        ]
        print(f"\n  清洗后有效情报: {len(cleaned_tweets)} 条")
    else:
        print("  [跳过清洗]")

    # ============================================================
    # Step 4: 信号判断（可选）
    # ============================================================
    judgment = None

    if not args.no_judge and cleaned_tweets:
        print(f"\n{'─' * 60}")
        print("  Step 4: 信号判断")
        print(f"{'─' * 60}\n")

        from signal_judge import judge_all_signals, print_signal_report

        judgment = judge_all_signals(cleaned_tweets, asset=decision["asset"])
        print_signal_report(judgment, asset=decision["asset"])

    # ============================================================
    # Step 5: 输出报告
    # ============================================================
    print(f"\n{'=' * 60}")
    print("  最终报告")
    print(f"{'=' * 60}")
    print(f"  查询: {query}")
    print(f"  资产: {decision['asset']}")
    print(f"  市场阶段: {decision['current_regime']}")
    print(f"  抓取总量: {len(all_tweets)} 条")
    print(f"  有效情报: {len(cleaned_tweets)} 条")

    if judgment and judgment["market_direction"]:
        d = judgment["market_direction"]
        arrow = "🟢" if "bullish" in d else ("🔴" if "bearish" in d else "⚪")
        print(f"  {arrow} 方向判断: {judgment['market_direction_label']}")
        print(f"  置信度: {judgment['aggregate_confidence']}")
        print(f"  平均影响: {judgment['avg_impact']}/5")

        if judgment["top_signals"]:
            print(f"\n  核心信号:")
            for s in judgment["top_signals"][:3]:
                print(f"    • [{s['direction_label']}] @{s['tweet_handle']}: {s['tweet_content'][:50]}...")
    else:
        print("  方向判断: 无明确方向（数据不足或信号冲突）")

    print(f"\n{'=' * 60}\n")

    # 保存JSON报告
    if args.output:
        report = {
            "query": query,
            "decision": decision,
            "crawl_stats": {
                "total": len(all_tweets),
                "cleaned": len(cleaned_tweets),
                "errors": crawl_results.get("errors", []),
            },
            "judgment": {
                "market_direction": judgment["market_direction"] if judgment else None,
                "market_direction_label": judgment["market_direction_label"] if judgment else None,
                "aggregate_confidence": judgment["aggregate_confidence"] if judgment else 0,
                "avg_impact": judgment["avg_impact"] if judgment else 0,
                "top_signals": [
                    {
                        "handle": s["tweet_handle"],
                        "content": s["tweet_content"],
                        "direction": s["direction_label"],
                        "impact": s["impact_level"],
                        "confidence": s["confidence"],
                    }
                    for s in (judgment["top_signals"] if judgment else [])[:5]
                ],
            } if judgment else None,
            "timestamp": datetime.now().isoformat(),
        }

        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"  JSON报告已保存: {args.output}")


def _parse_count(val) -> int:
    """解析互动数（支持 1.2K, 5.3M 格式）"""
    if not val or val == "0":
        return 0
    try:
        val = str(val).replace(",", "").strip()
        if val.endswith("K"):
            return int(float(val[:-1]) * 1000)
        elif val.endswith("M"):
            return int(float(val[:-1]) * 1000000)
        return int(val)
    except (ValueError, TypeError):
        return 0


if __name__ == "__main__":
    main()
