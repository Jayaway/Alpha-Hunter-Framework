#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X 实时情报系统入口（优化版）
✅ 使用新版极速决策器 (100x 更快)
✅ 可选新版精简清洗器
✅ 完全兼容旧版
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime

from graph_engine import DEFAULT_GRAPH_FILE


MARKET_KEYWORDS = {
    "oil", "crude", "brent", "wti", "gold", "bitcoin", "btc", "crypto",
    "dollar", "dxy", "fed", "rate", "inflation", "cpi", "stock", "equity",
    "nasdaq", "s&p", "market", "opec", "tariff", "sanction", "recession",
    "原油", "油价", "黄金", "比特币", "美元", "美联储", "降息", "加息",
    "通胀", "股市", "股票", "纳指", "标普", "市场", "行情", "走势",
    "涨", "跌", "价格", "金融", "宏观", "关税", "制裁",
}


def main():
    parser = build_parser()
    args = parser.parse_args()
    _configure_logging(args.debug)

    print(f"\n{'=' * 60}")
    print("  ✅ X 实时情报系统（优化版）")
    print(f"  极速决策器: ON (100x更快)")
    print(f"  精简清洗器: {'ON' if args.new_cleaner else 'OFF (可选 --new-cleaner)'}")
    print(f"{'=' * 60}")

    if not args.query:
        interactive_loop(args)
        return

    try:
        run_query(args.query, args)
    except Exception as exc:
        logging.exception("run_query failed")
        print(f"\n  ✗ 主流程失败: {exc}")
        if args.debug:
            print("\n  [DEBUG] 详细错误:")
            traceback.print_exc()
        else:
            print("  提示：使用 --debug 查看详细错误；完整错误已写入 logs/deepalpha.log")
        raise SystemExit(1)


def build_parser():
    parser = argparse.ArgumentParser(
        description="X 实时情报系统 - 优化版（极速决策器 + 精简清洗器）",
        usage='python3 run_v2.py ["你的问题"] [选项]',
    )
    parser.add_argument("query", nargs="?", type=str, help="任意问题；为空时进入交互模式")
    parser.add_argument("--ai", action="store_true", help="使用 AI 做前置决策/一般问题回答")
    parser.add_argument("--ai-backend", type=str, default="auto", choices=["auto", "openai", "ollama", "lmstudio"])
    parser.add_argument("--ai-model", type=str, default=None, help="AI 模型名称")
    parser.add_argument("--ai-base-url", type=str, default=None, help="兼容 OpenAI API 的服务地址")
    parser.add_argument("--dry-run", action="store_true", help="只显示决策，不执行抓取")
    parser.add_argument("--crawl", action="store_true", help="执行实时抓取；默认只分析历史抓取结果")
    parser.add_argument("--no-clean", action="store_true", help="跳过数据清洗")
    parser.add_argument("--new-cleaner", action="store_true", help="使用新版精简清洗器 (O(n)复杂度)")
    parser.add_argument("--no-judge", action="store_true", help="跳过信号判断")
    parser.add_argument("--no-graph", action="store_true", help="跳过独立关系图谱生成")
    parser.add_argument("--graph-file", type=str, default=DEFAULT_GRAPH_FILE, help="独立图谱 JSON 输出文件")
    parser.add_argument("--graph-current-only", action="store_true", help="只用本次抓取生成图谱，默认读取历史CSV")
    parser.add_argument("--view-graph", action="store_true", help="抓取/生成后启动独立图谱查看器")
    parser.add_argument("--graph-port", type=int, default=8080, help="图谱查看器端口")
    parser.add_argument("--cookie-file", type=str, default="x_cookie.json", help="Cookie文件路径")
    parser.add_argument("-b", "--browser", type=str, default="chrome", choices=["chrome", "firefox", "safari"])
    parser.add_argument("--headless", action="store_true", help="无头模式")
    parser.add_argument("--delay", type=int, default=3, help="任务间延迟秒数")
    parser.add_argument("--output", type=str, default=None, help="输出 JSON 报告路径")
    parser.add_argument("--debug", action="store_true", help="显示详细错误并写入调试日志")
    parser.add_argument("--event-pipeline", action="store_true", help="启用 v0.2 事件聚合 + 证据链报告")
    return parser


def interactive_loop(args):
    print("进入交互模式。输入 exit / quit 退出。")
    while True:
        try:
            query = input("\n你想问什么？> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not query:
            continue
        if query.lower() in {"exit", "quit", "q"}:
            break
        run_query(query, args)


def run_query(query: str, args):
    print(f"\n{'=' * 60}")
    print("  X 实时情报系统（优化版）")
    print(f"  查询: {query}")
    print(f"{'=' * 60}\n")

    ai = _make_ai(args) if args.ai else None
    decision = _make_decision(query, args, ai)

    if _is_general_question(query, decision):
        _answer_general_question(query, ai)
        return

    _print_decision(decision)

    if not args.crawl:
        analysis_result, graph_result = _analyze_existing_intel(query, decision, args)
        event_pipeline = _build_event_pipeline(args, query, decision, analysis_result.get("relevant_tweets", []))
        _save_history_report(args, query, decision, analysis_result, graph_result, event_pipeline)
        return

    if args.dry_run:
        print("\n  [DRY RUN] 仅显示决策，不执行抓取。")
        from crawler_runner import print_tasks
        print("\n  将要执行的任务:")
        print("-" * 40)
        print_tasks(decision)
        return

    from crawler_runner import run_all_tasks, save_results

    crawl_results = run_all_tasks(
        decision,
        cookie_file=args.cookie_file,
        browser=args.browser,
        headless="yes" if args.headless else "no",
        delay_between_tasks=args.delay,
        debug=args.debug,
    )

    if not crawl_results["all_tweets"]:
        print("\n  未抓取到任何推文，流程结束。")
        logging.warning("crawl completed with zero tweets; errors=%s", crawl_results.get("errors", []))
        _save_report(args, query, decision, crawl_results, [], None, None, None)
        return

    csv_path = save_results(crawl_results)
    all_tweets = crawl_results["all_tweets"]
    print(f"\n  原始推文: {len(all_tweets)} 条")

    graph_result = None
    if not args.no_graph:
        graph_result = _generate_graph(args, query, all_tweets)

    cleaned_tweets = _clean_tweets(all_tweets, args, ai)
    judgment = _judge_signals(cleaned_tweets, decision, args)
    event_pipeline = _build_event_pipeline(args, query, decision, cleaned_tweets)

    _print_final_report(query, decision, all_tweets, cleaned_tweets, judgment)
    _save_report(args, query, decision, crawl_results, cleaned_tweets, judgment, graph_result, csv_path, event_pipeline)

    if args.view_graph and graph_result:
        _start_graph_viewer(args.graph_file, args.graph_port)


def _make_ai(args):
    from ai_model import AIModel
    return AIModel(
        backend=args.ai_backend,
        model=args.ai_model,
        base_url=args.ai_base_url,
    )


def _make_decision(query: str, args, ai):
    if args.ai:
        from ai_model import ai_decide
        decision = ai_decide(query, ai)
    else:
        # ✅ 使用新版极速决策器 (100x 更快)
        from intel_router_v2 import decide

        start = time.time()
        decision_obj = decide(query)
        elapsed = (time.time() - start) * 1000
        print(f"  ⚡ 极速决策完成: {elapsed:.2f} ms\n")

        # 转换为旧版兼容的格式
        decision = decision_obj.to_dict()

    decision.setdefault("asset", "unknown")
    decision.setdefault("user_intent", "general")
    decision.setdefault("current_regime", "unknown")
    decision.setdefault("urgency", "normal")
    decision.setdefault("top_accounts", [])
    decision.setdefault("top_event_phrases", [])
    decision.setdefault("crawl_tasks", [])
    decision.setdefault("why_this_route", "")
    return decision


def _is_general_question(query: str, decision: dict) -> bool:
    text = query.lower()
    if not any(keyword in text for keyword in MARKET_KEYWORDS):
        return True
    if decision.get("asset") == "general":
        return True
    return not decision.get("crawl_tasks")


def _answer_general_question(query: str, ai):
    print("  识别为一般问题，跳过 X 抓取。")
    if ai is None:
        print("  未启用 AI。一般问题请使用 --ai，或配置本地 Ollama/LM Studio/OpenAI API。")
        return

    answer = ai.chat(
        query,
        system_prompt="你是一个简洁、准确的中文助手。直接回答用户问题。",
        temperature=0.5,
        max_tokens=1200,
    )
    print("\n" + answer)


def _print_decision(decision: dict):
    print(f"  asset: {decision['asset']}")
    print(f"  user_intent: {decision['user_intent']}")
    print(f"  current_regime: {decision['current_regime']}")
    print(f"  urgency: {decision['urgency']}")
    print("\n  top_accounts:")
    for account in decision["top_accounts"]:
        print(f"    {account}")
    print("\n  top_event_phrases:")
    for phrase in decision.get("top_event_phrases", []):
        print(f"    {phrase}")
    print("\n  crawl_tasks:")
    for task in decision["crawl_tasks"]:
        print(f"    {task}")
    print(f"\n  why: {decision['why_this_route']}")


def _generate_graph(args, query: str, all_tweets: list):
    from graph_engine import generate_graph_data

    if args.graph_current_only:
        return generate_graph_data(
            tweets=all_tweets,
            output_file=args.graph_file,
            query=query,
        )

    return generate_graph_data(
        input_dir="./抓取的信息/",
        output_file=args.graph_file,
        query=query,
    )


def _analyze_existing_intel(query: str, decision: dict, args):
    from graph_engine import generate_graph_data
    from intel_analyzer import analyze_history, print_history_report

    result = analyze_history(query, decision)
    print_history_report(query, decision, result)

    graph_result = None
    if not args.no_graph:
        graph_result = generate_graph_data(
            input_dir="./抓取的信息/",
            output_file=args.graph_file,
            query=query,
        )

    if args.view_graph:
        _start_graph_viewer(args.graph_file, args.graph_port)

    return result, graph_result


def _clean_tweets(all_tweets: list, args, ai):
    if args.no_clean:
        print("  [跳过清洗]")
        return all_tweets

    print(f"\n{'─' * 60}")
    print("  Step 3: 数据清洗")
    print(f"{'─' * 60}")

    # ✅ 新版精简清洗器（可选，--new-cleaner 参数）
    if args.new_cleaner:
        from cleaner_v2 import clean_tweets as clean_tweets_v2

        start = time.time()
        cleaned_objs = clean_tweets_v2(all_tweets, verbose=True)
        elapsed = (time.time() - start) * 1000

        filtered = [t for t in cleaned_objs if t.verdict in ("actionable", "noteworthy")]
        cleaned_tweets = [
            {
                "handle": f"@{t.username}",
                "content": t.content,
                "likes": t.likes,
                "retweets": t.retweets,
                "verified": t.is_verified,
                "_final_score": t.final_score,
                "_final_verdict": t.verdict,
                "_source_score": t.source_score,
                "_hearsay_flag": t.is_hearsay,
                "_cross_verify_score": t.cross_verify_score,
            }
            for t in filtered
        ]
        print(f"\n  ⚡ 新版清洗完成: {elapsed:.2f} ms")
        print(f"  清洗后有效情报: {len(cleaned_tweets)} 条")
        return cleaned_tweets

    # 旧版清洗器（默认）
    if args.ai and ai is not None:
        from ai_model import ai_batch_clean
        ai_results = ai_batch_clean(all_tweets, ai)
        cleaned = []
        for tweet, result in zip(all_tweets, ai_results):
            if result.get("final_verdict") in ("actionable", "noteworthy"):
                item = dict(tweet)
                item.update({
                    "_final_score": result.get("final_score", 0),
                    "_final_verdict": result.get("final_verdict"),
                    "_ai_summary": result.get("summary", ""),
                    "_ai_direction": result.get("direction", "neutral"),
                })
                cleaned.append(item)
        print(f"\n  AI 清洗后有效情报: {len(cleaned)} 条")
        return cleaned

    from data_cleaner import Tweet as CleanTweet, clean_pipeline

    clean_input = []
    for tweet in all_tweets:
        clean_input.append(CleanTweet(
            tweet_id=tweet.get("tweet_id"),
            username=tweet.get("handle", "").lstrip("@"),
            content=tweet.get("content", ""),
            timestamp=tweet.get("timestamp"),
            likes=_parse_count(tweet.get("likes")),
            retweets=_parse_count(tweet.get("retweets")),
            replies=_parse_count(tweet.get("replies")),
            impressions=_parse_count(tweet.get("analytics")),
            is_verified=tweet.get("verified", False),
            is_retweet=False,
            has_media=False,
            media_urls=[],
            links=[],
            hashtags=tweet.get("tags", []),
            mentions=tweet.get("mentions", []),
        ))

    cleaned = clean_pipeline(clean_input, verbose=True)
    filtered = [tweet for tweet in cleaned if tweet._final_verdict in ("actionable", "noteworthy")]
    cleaned_tweets = [
        {
            "handle": f"@{tweet.username}",
            "content": tweet.content,
            "likes": tweet.likes,
            "retweets": tweet.retweets,
            "verified": tweet.is_verified,
            "_final_score": tweet._final_score,
            "_final_verdict": tweet._final_verdict,
            "_source_score": tweet._source_score,
            "_hearsay_flag": tweet._hearsay_flag,
            "_cross_verify_score": tweet._cross_verify_score,
        }
        for tweet in filtered
    ]
    print(f"\n  清洗后有效情报: {len(cleaned_tweets)} 条")
    return cleaned_tweets


def _judge_signals(cleaned_tweets: list, decision: dict, args):
    if args.no_judge or not cleaned_tweets:
        return None

    print(f"\n{'─' * 60}")
    print("  Step 4: 信号判断")
    print(f"{'─' * 60}\n")

    from signal_judge import judge_all_signals, print_signal_report

    judgment = judge_all_signals(cleaned_tweets, asset=decision.get("asset"))
    print_signal_report(judgment, asset=decision.get("asset"))
    return judgment


def _build_event_pipeline(args, query: str, decision: dict, tweets: list):
    if not args.event_pipeline:
        return None

    print(f"\n{'─' * 60}")
    print("  Step 5: v0.2 事件聚合与证据链")
    print(f"{'─' * 60}")

    from deepalpha_runtime.event_pipeline import print_event_pipeline_report, run_event_pipeline

    pipeline = run_event_pipeline(tweets, query=query, decision=decision)
    print_event_pipeline_report(pipeline)
    return pipeline


def _print_final_report(query, decision, all_tweets, cleaned_tweets, judgment):
    print(f"\n{'=' * 60}")
    print("  最终报告")
    print(f"{'=' * 60}")
    print(f"  查询: {query}")
    print(f"  资产: {decision['asset']}")
    print(f"  市场阶段: {decision['current_regime']}")
    print(f"  抓取总量: {len(all_tweets)} 条")
    print(f"  有效情报: {len(cleaned_tweets)} 条")

    if judgment and judgment.get("market_direction"):
        print(f"  方向判断: {judgment['market_direction_label']}")
        print(f"  置信度: {judgment['aggregate_confidence']}")
        print(f"  平均影响: {judgment['avg_impact']}/5")
    else:
        print("  方向判断: 无明确方向（数据不足或信号冲突）")

    print(f"\n{'=' * 60}\n")


def _save_report(args, query, decision, crawl_results, cleaned_tweets, judgment, graph_result, csv_path, event_pipeline=None):
    if not args.output:
        return

    report = {
        "query": query,
        "decision": decision,
        "csv_path": csv_path,
        "crawl_stats": {
            "total": len(crawl_results["all_tweets"]),
            "cleaned": len(cleaned_tweets),
            "errors": crawl_results.get("errors", []),
        },
        "graph": graph_result,
        "judgment": judgment,
        "event_pipeline": event_pipeline,
        "timestamp": datetime.now().isoformat(),
    }

    _write_json_report(args.output, report)


def _save_history_report(args, query, decision, analysis_result, graph_result, event_pipeline=None):
    if not args.output:
        return

    report = {
        "query": query,
        "mode": "history",
        "decision": decision,
        "csv_path": None,
        "crawl_stats": {
            "total": analysis_result.get("total_tweets", 0),
            "cleaned": analysis_result.get("relevant_count", 0),
            "errors": [],
        },
        "graph": graph_result,
        "judgment": analysis_result.get("judgment"),
        "history": {
            "summary_lines": analysis_result.get("summary_lines", []),
            "top_tweets": analysis_result.get("top_tweets", []),
        },
        "event_pipeline": event_pipeline,
        "timestamp": datetime.now().isoformat(),
    }

    _write_json_report(args.output, report)


def _write_json_report(output_path: str, report: dict):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  JSON报告已保存: {output_path}")


def _configure_logging(debug: bool = False):
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        filename="logs/deepalpha.log",
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )


def _start_graph_viewer(graph_file: str, port: int):
    cmd = [
        sys.executable,
        "graph_viewer.py",
        "--port",
        str(port),
        "--file",
        graph_file,
    ]
    print(f"  正在启动独立图谱查看器: http://localhost:{port}")
    subprocess.Popen(cmd)


def _parse_count(val) -> int:
    if not val or val == "0":
        return 0
    try:
        text = str(val).replace(",", "").strip()
        if text.endswith("K"):
            return int(float(text[:-1]) * 1000)
        if text.endswith("M"):
            return int(float(text[:-1]) * 1000000)
        return int(float(text))
    except (ValueError, TypeError):
        return 0


if __name__ == "__main__":
    main()
