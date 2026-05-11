# -*- coding: utf-8 -*-
"""
历史情报分析器。

用户提问时优先读取已经抓取过的 CSV，筛选相关推文并汇总判断，
避免每次询问都启动浏览器实时抓取。
"""

from collections import Counter
import re
from typing import List, Tuple

from deepalpha.graph_engine import DEFAULT_INPUT_DIR, load_tweets_from_csv_dir, parse_count


ASSET_TERMS = {
    "oil": ["oil", "crude", "wti", "brent", "opec", "hormuz", "tanker", "red sea", "原油", "油价", "欧佩克"],
    "gold": ["gold", "xau", "safe haven", "rate cut", "dxy", "黄金", "避险", "降息"],
    "crypto": [
        "bitcoin", "btc", "ethereum", "eth", "crypto", "etf", "whale",
        "sui", "sol", "xrp", "bnb", "doge", "ada", "ton", "apt", "arb",
        "比特币", "以太坊", "加密", "链上",
    ],
    "fx": ["dollar", "dxy", "fed", "rate", "currency", "美元", "汇率", "美联储"],
    "equity": ["stock", "equity", "nasdaq", "s&p", "earnings", "股市", "股票", "纳指", "标普"],
    "macro": ["fed", "inflation", "cpi", "jobs", "tariff", "recession", "美联储", "通胀", "关税", "衰退"],
    "geopolitics": ["war", "conflict", "iran", "israel", "missile", "sanction", "战争", "冲突", "制裁"],
}

QUERY_TERMS = {
    "涨": ["bullish", "surge", "rise", "rally", "利多", "上涨", "涨"],
    "跌": ["bearish", "drop", "fall", "selloff", "利空", "下跌", "跌"],
    "风险": ["risk", "war", "conflict", "sanction", "风险", "冲突", "制裁"],
}


def analyze_history(query: str, decision: dict, input_dir: str = DEFAULT_INPUT_DIR) -> dict:
    tweets = load_tweets_from_csv_dir(input_dir)
    relevant = filter_relevant_tweets(tweets, query, decision)

    if not relevant:
        return {
            "total_tweets": len(tweets),
            "relevant_count": 0,
            "judgment": None,
            "top_tweets": [],
            "summary_lines": ["历史库中没有找到足够相关的情报。可以使用 --crawl 执行一次实时抓取。"],
        }

    from deepalpha.signal_judge import judge_all_signals

    judgment = judge_all_signals(relevant, asset=decision.get("asset"))
    top_tweets = sorted(relevant, key=_tweet_weight, reverse=True)[:8]
    summary_lines = build_summary_lines(query, decision, relevant, judgment, top_tweets)

    return {
        "total_tweets": len(tweets),
        "relevant_count": len(relevant),
        "judgment": judgment,
        "top_tweets": top_tweets,
        "relevant_tweets": relevant,
        "summary_lines": summary_lines,
    }


def filter_relevant_tweets(tweets: List[dict], query: str, decision: dict, limit: int = 80) -> List[dict]:
    terms = build_terms(query, decision)
    asset_terms = build_asset_terms(query, decision)
    scored: List[Tuple[int, dict]] = []

    for tweet in tweets:
        content = str(tweet.get("content", "")).lower()
        tags = " ".join(tweet.get("tags", []) or []).lower()
        haystack = f"{content} {tags}"
        if asset_terms and not any(term_matches(haystack, term) for term in asset_terms):
            continue
        score = sum(1 for term in terms if term and term_matches(haystack, term))
        if score <= 0:
            continue
        score += min(_tweet_weight(tweet) // 1000, 5)
        scored.append((score, tweet))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [tweet for _, tweet in scored[:limit]]


def build_terms(query: str, decision: dict) -> List[str]:
    terms = []
    asset = decision.get("asset")
    terms.extend(ASSET_TERMS.get(asset, []))
    terms.extend(extract_query_tickers(query))
    terms.extend(decision.get("top_event_phrases", []) or [])

    query_lower = query.lower()
    for key, values in QUERY_TERMS.items():
        if key in query_lower:
            terms.extend(values)

    for raw in query.replace("？", " ").replace("?", " ").replace("，", " ").split():
        if len(raw) >= 2:
            terms.append(raw)

    return list(dict.fromkeys(terms))


def build_asset_terms(query: str, decision: dict) -> List[str]:
    asset = decision.get("asset")
    tickers = extract_query_tickers(query)
    if asset == "crypto" and tickers:
        return list(dict.fromkeys(tickers))
    terms = list(ASSET_TERMS.get(asset, []))
    if asset == "crypto":
        terms.extend(tickers)
    return list(dict.fromkeys(term for term in terms if term))


def extract_query_tickers(query: str) -> List[str]:
    return [
        token
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_]{1,9}", query)
        if len(token) <= 10
    ]


def term_matches(haystack: str, term: str) -> bool:
    text = str(term or "").strip().lower()
    if not text:
        return False
    if re.fullmatch(r"[a-z0-9_]{2,5}", text):
        return re.search(rf"(?<![a-z0-9_]){re.escape(text)}(?![a-z0-9_])", haystack) is not None
    return text in haystack


def build_summary_lines(query: str, decision: dict, tweets: List[dict], judgment: dict, top_tweets: List[dict]) -> List[str]:
    direction = judgment.get("market_direction_label") or "暂无明确方向"
    confidence = judgment.get("aggregate_confidence", 0)
    avg_impact = judgment.get("avg_impact", 0)

    sources = Counter(str(tweet.get("handle", "")).lstrip("@") for tweet in tweets if tweet.get("handle"))
    top_sources = "、".join([source for source, _ in sources.most_common(4)]) or "暂无"

    lines = [
        f"基于历史库中 {len(tweets)} 条相关情报，当前结论：{direction}。",
        f"聚合置信度 {confidence}，平均影响等级 {avg_impact}/5；主要信息源：{top_sources}。",
    ]

    if judgment.get("signal_count"):
        signal_text = "；".join([f"{name} {count}条" for name, count in judgment["signal_count"].items()])
        lines.append(f"信号分布：{signal_text}。")

    if top_tweets:
        lines.append("关键依据：")
        for tweet in top_tweets[:3]:
            handle = tweet.get("handle", "")
            content = str(tweet.get("content", "")).replace("\n", " ")[:90]
            lines.append(f"- {handle}: {content}...")

    return lines


def print_history_report(query: str, decision: dict, result: dict):
    print(f"\n{'=' * 60}")
    print("  历史情报汇总")
    print(f"{'=' * 60}")
    print(f"  查询: {query}")
    print(f"  历史总量: {result['total_tweets']} 条")
    print(f"  相关情报: {result['relevant_count']} 条")
    print()
    for line in result["summary_lines"]:
        print(f"  {line}" if not line.startswith("- ") else f"    {line}")
    print(f"{'=' * 60}\n")


def _tweet_weight(tweet: dict) -> int:
    return (
        parse_count(tweet.get("likes"))
        + parse_count(tweet.get("retweets")) * 2
        + parse_count(tweet.get("replies"))
    )
