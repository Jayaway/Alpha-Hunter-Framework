# -*- coding: utf-8 -*-
"""
X 实时情报系统 - 信号判断器
================================================
清洗后的推文 → 价格方向 / 幅度 / 可信度 / 影响等级

前置AI不判断涨跌，这里才判断。
"""

import re
from typing import Optional


# ============================================================
# 1. 方向信号词库
# ============================================================

# 格式: {信号方向: [触发词列表]}
DIRECTION_SIGNALS = {
    "bullish_oil": {
        "label": "利多原油",
        "triggers": [
            "cut", "supply disruption", "blockade", "sanction", "embargo",
            "attack", "strike", "escalation", "ceasefire collapse", "force majeure",
            "shutdown", "inventory draw", "demand surge", "OPEC+", "voluntary cut",
            "Hormuz", "Red Sea", "tanker seizure", "pipeline sabotage",
            "production cut", "output cut", "lower supply",
        ],
        "asset": "oil",
    },
    "bearish_oil": {
        "label": "利空原油",
        "triggers": [
            "production increase", "output increase", "supply surge", "demand drop",
            "recession", "demand destruction", "inventory build", "OPEC+ increase",
            "SPR release", "ceasefire agreement", "de-escalation", "peace deal",
            "higher supply", "demand weakness", "slowing demand", "global slowdown",
            "trade war", "tariff impact demand",
        ],
        "asset": "oil",
    },
    "bullish_gold": {
        "label": "利多黄金",
        "triggers": [
            "rate cut", "dovish", "pivot", "recession risk", "war", "conflict",
            "nuclear", "geopolitical risk", "safe haven", "inflation",
            "banking crisis", "debt crisis", "DXY weak", "dollar weak",
            "central bank buying", "uncertainty",
        ],
        "asset": "gold",
    },
    "bearish_gold": {
        "label": "利空黄金",
        "triggers": [
            "rate hike", "hawkish", "strong dollar", "DXY surge", "risk on",
            "peace deal", "ceasefire", "de-escalation", "strong jobs",
            "cooling inflation", "economic boom", "equity rally",
        ],
        "asset": "gold",
    },
    "bullish_fx_emerging": {
        "label": "利多新兴货币",
        "triggers": [
            "dollar weak", "DXY drop", "risk on", "Fed rate cut", "hawkish BOJ",
            "intervention", "emerging market inflow",
        ],
        "asset": "fx",
    },
    "bearish_fx_emerging": {
        "label": "利空新兴货币",
        "triggers": [
            "dollar strong", "DXY surge", "risk off", "Fed rate hike",
            "tariff", "trade war", "capital outflow", "currency crisis",
        ],
        "asset": "fx",
    },
    "bullish_dollar": {
        "label": "利多美元",
        "triggers": [
            "rate hike", "hawkish Fed", "strong jobs", "hot inflation",
            "safe haven demand", "risk off", "DXY breakout",
        ],
        "asset": "fx",
    },
    "bearish_dollar": {
        "label": "利空美元",
        "triggers": [
            "rate cut", "dovish Fed", "weak jobs", "recession",
            "debt ceiling", "money printing", "QE", "DXY breakdown",
        ],
        "asset": "fx",
    },
    "bullish_crypto": {
        "label": "利多加密",
        "triggers": [
            "ETF approval", "ETF inflow", "rate cut", "institutional buying",
            "adoption", "regulation clarity", "halving", "whale accumulation",
            "rally", "surge", "breakout", "new high", "all-time high", "ath",
            "spot buying", "inflow", "accumulation", "short squeeze",
            "price jumps", "price rises", "uptrend",
        ],
        "asset": "crypto",
    },
    "bearish_crypto": {
        "label": "利空加密",
        "triggers": [
            "SEC rejection", "regulation crackdown", "ban", "ETF outflow",
            "hack", "exchange collapse", "whale selling", "rate hike",
            "selloff", "drop", "breakdown", "liquidation", "long liquidation",
            "outflow", "distribution", "price falls", "price drops", "downtrend",
        ],
        "asset": "crypto",
    },
    "bullish_equity": {
        "label": "利多股市",
        "triggers": [
            "rate cut", "earnings beat", "strong economy", "stimulus",
            "tax cut", "deregulation", "peace deal", "risk on",
        ],
        "asset": "equity",
    },
    "bearish_equity": {
        "label": "利空股市",
        "triggers": [
            "rate hike", "recession", "inflation surge", "war escalation",
            "tariff", "banking crisis", "circuit breaker", "crash", "selloff",
        ],
        "asset": "equity",
    },
}


# ============================================================
# 2. 影响等级判断
# ============================================================

# 影响等级关键词（出现即触发高影响）
HIGH_IMPACT_KEYWORDS = [
    "breaking", "just in", "exclusive", "confirmed", "official",
    "emergency", "immediate", "effective immediately",
    "突发", "紧急", "正式宣布", "即刻生效",
]

# 极端影响（可能移动价格3%+）
EXTREME_IMPACT_KEYWORDS = [
    "Hormuz", "nuclear", "Article 5", "invasion", "full-scale",
    "emergency OPEC", "SPR release", "surprise rate",
    "霍尔木兹", "核", "全面入侵", "紧急OPEC",
]


# ============================================================
# 3. 信号判断引擎
# ============================================================

def judge_signal(tweet: dict, asset: str = None) -> dict:
    """
    对单条推文进行信号判断

    Args:
        tweet: 推文字典（scraper输出格式）
        asset: 资产类别（用于过滤相关信号）

    Returns:
        {
            "direction": str | None,     # e.g. "bullish_oil"
            "direction_label": str | None, # e.g. "利多原油"
            "confidence": float,          # 0.0 - 1.0
            "impact_level": int,          # 1-5
            "impact_reason": str,         # 影响原因
            "key_signals": list[str],     # 触发的信号词
        }
    """
    content = (tweet.get("content") or "").lower()
    handle = (tweet.get("handle") or "").lower()

    if not content:
        return _empty_signal()

    # 扫描所有方向信号
    best_signal = None
    best_score = 0
    best_signals_found = []

    for signal_key, signal_info in DIRECTION_SIGNALS.items():
        # 如果指定了资产，只看相关资产的信号
        if asset and signal_info.get("asset") != asset:
            continue

        found = []
        for trigger in signal_info["triggers"]:
            if trigger.lower() in content:
                found.append(trigger)

        if len(found) > best_score:
            best_score = len(found)
            best_signal = signal_key
            best_signals_found = found

    # 计算影响等级
    impact_level = _calculate_impact(content, tweet, best_score)

    # 计算置信度
    confidence = _calculate_confidence(best_score, impact_level, tweet)

    if best_signal:
        signal_info = DIRECTION_SIGNALS[best_signal]
        return {
            "direction": best_signal,
            "direction_label": signal_info["label"],
            "confidence": round(confidence, 2),
            "impact_level": impact_level,
            "impact_reason": f"触发 {len(best_signals_found)} 个信号: {', '.join(best_signals_found[:3])}",
            "key_signals": best_signals_found,
        }

    return _empty_signal()


def _calculate_impact(content: str, tweet: dict, signal_count: int) -> int:
    """计算影响等级 1-5"""
    impact = 1  # 基础

    # 信号数量加分
    if signal_count >= 3:
        impact += 2
    elif signal_count >= 2:
        impact += 1

    # 极端影响词
    for kw in EXTREME_IMPACT_KEYWORDS:
        if kw.lower() in content:
            impact = max(impact, 5)
            break

    # 高影响词
    for kw in HIGH_IMPACT_KEYWORDS:
        if kw.lower() in content:
            impact = max(impact, 4)
            break

    # 互动量加分
    try:
        likes_raw = tweet.get("likes")
        retweets_raw = tweet.get("retweets")
        if isinstance(likes_raw, str):
            likes = int(likes_raw.replace(",", "").replace("K", "000").replace("M", "000000"))
        else:
            likes = int(likes_raw or 0)
        if isinstance(retweets_raw, str):
            retweets = int(retweets_raw.replace(",", "").replace("K", "000").replace("M", "000000"))
        else:
            retweets = int(retweets_raw or 0)
        if likes + retweets > 10000:
            impact = max(impact, 4)
        elif likes + retweets > 1000:
            impact = max(impact, 3)
    except (ValueError, TypeError):
        pass

    # 来源加分（蓝V/官方）
    if tweet.get("verified"):
        impact = max(impact, impact + 1)

    return min(impact, 5)


def _calculate_confidence(signal_count: int, impact: int, tweet: dict) -> float:
    """计算置信度 0.0 - 1.0"""
    base = 0.3

    # 信号数量
    base += min(signal_count * 0.15, 0.3)

    # 影响等级
    base += impact * 0.05

    # 来源可信度
    if tweet.get("verified"):
        base += 0.1

    # 内容长度（太短不可信）
    content = tweet.get("content") or ""
    if len(content) > 100:
        base += 0.1
    elif len(content) < 30:
        base -= 0.2

    return min(max(base, 0.0), 1.0)


def _empty_signal() -> dict:
    return {
        "direction": None,
        "direction_label": None,
        "confidence": 0.0,
        "impact_level": 1,
        "impact_reason": "未检测到明确方向信号",
        "key_signals": [],
    }


# ============================================================
# 4. 批量判断 + 聚合
# ============================================================

def judge_all_signals(tweets: list, asset: str = None) -> dict:
    """
    对一批推文进行信号判断，并聚合为市场整体判断

    Args:
        tweets: 推文列表
        asset: 资产类别

    Returns:
        {
            "market_direction": str,       # e.g. "bullish_oil"
            "market_direction_label": str,  # e.g. "利多原油"
            "aggregate_confidence": float,
            "signal_count": dict,           # {方向: 出现次数}
            "avg_impact": float,
            "top_signals": list[dict],      # Top5高影响推文
            "details": list[dict],          # 每条推文的判断结果
        }
    """
    if not tweets:
        return {
            "market_direction": None,
            "market_direction_label": None,
            "aggregate_confidence": 0.0,
            "signal_count": {},
            "avg_impact": 0.0,
            "top_signals": [],
            "details": [],
        }

    details = []
    signal_counts = {}
    total_impact = 0
    total_confidence = 0

    for tweet in tweets:
        result = judge_signal(tweet, asset)
        result["tweet_handle"] = tweet.get("handle", "")
        result["tweet_content"] = tweet.get("content", "")[:100]
        details.append(result)

        if result["direction"]:
            signal_counts[result["direction"]] = signal_counts.get(result["direction"], 0) + 1
        total_impact += result["impact_level"]
        total_confidence += result["confidence"]

    # 找出最强方向
    market_direction = None
    market_direction_label = None
    if signal_counts:
        market_direction = max(signal_counts, key=signal_counts.get)
        market_direction_label = DIRECTION_SIGNALS.get(market_direction, {}).get("label", market_direction)

    # 聚合指标
    n = len(tweets)
    avg_impact = round(total_impact / n, 1) if n else 0
    aggregate_confidence = round(total_confidence / n, 2) if n else 0

    # Top5高影响推文
    top_signals = sorted(
        [d for d in details if d["direction"]],
        key=lambda x: (x["impact_level"], x["confidence"]),
        reverse=True,
    )[:5]

    return {
        "market_direction": market_direction,
        "market_direction_label": market_direction_label,
        "aggregate_confidence": aggregate_confidence,
        "signal_count": signal_counts,
        "avg_impact": avg_impact,
        "top_signals": top_signals,
        "details": details,
    }


# ============================================================
# 5. 格式化输出
# ============================================================

def print_signal_report(judgment: dict, asset: str = None):
    """打印信号判断报告"""
    print("=" * 60)
    print("  信号判断报告")
    print("=" * 60)

    direction = judgment["market_direction_label"] or "无明确方向"
    confidence = judgment["aggregate_confidence"]
    avg_impact = judgment["avg_impact"]
    signal_counts = judgment["signal_count"]

    # 方向指示器
    if judgment["market_direction"]:
        d = judgment["market_direction"]
        if "bullish" in d:
            arrow = "🟢"
        elif "bearish" in d:
            arrow = "🔴"
        else:
            arrow = "⚪"
        print(f"  {arrow} 市场方向: {direction} (置信度: {confidence})")
    else:
        print(f"  ⚪ 市场方向: 无明确方向")

    print(f"  平均影响等级: {avg_impact}/5")

    if signal_counts:
        print(f"\n  信号分布:")
        for sig, count in sorted(signal_counts.items(), key=lambda x: x[1], reverse=True):
            label = DIRECTION_SIGNALS.get(sig, {}).get("label", sig)
            bar = "█" * count
            print(f"    {label}: {bar} ({count})")

    top = judgment["top_signals"]
    if top:
        print(f"\n  Top {len(top)} 高影响信号:")
        for i, s in enumerate(top, 1):
            print(f"    {i}. [{s['direction_label']}] 影响{s['impact_level']}级 置信{s['confidence']}")
            print(f"       @{s['tweet_handle']}: {s['tweet_content'][:60]}...")
            print(f"       原因: {s['impact_reason']}")

    print("=" * 60)


# ============================================================
# 6. 测试
# ============================================================

if __name__ == "__main__":
    # 模拟清洗后的推文数据
    test_tweets = [
        {"handle": "@JavierBlas", "content": "BREAKING: OPEC+ agrees to emergency production cut of 2.2 million bpd amid Hormuz blockade fears. Supply disruption risk at highest level since 2022.", "likes": "5.2K", "retweets": "3.1K", "verified": True},
        {"handle": "@Reuters", "content": "Saudi Arabia announces voluntary cut of 1 million barrels per day, effective immediately. OPEC+ emergency meeting called for next week.", "likes": "8.1K", "retweets": "5.3K", "verified": True},
        {"handle": "@IDF", "content": "ALERT: Missile attack detected from Iran. Civilian shelters open. This is not a drill.", "likes": "12K", "retweets": "9K", "verified": True},
        {"handle": "@realDonaldTrump", "content": "Iran sanctions will be SNAPBACK effective immediately. No more exceptions. OPEC better watch supply.", "likes": "45K", "retweets": "22K", "verified": True},
        {"handle": "@anon_trader", "content": "OIL TO $200!!! BUY NOW!!!", "likes": "5", "retweets": "1", "verified": False},
        {"handle": "@JKempEnergy", "content": "EIA crude inventory draw of 4.2 million barrels vs expected 1.5 million. Bullish surprise. Demand remains resilient.", "likes": "800", "retweets": "300", "verified": True},
        {"handle": "@federalreserve", "content": "The Federal Reserve has decided to maintain the target range for the federal funds rate at 4.75-5.00%.", "likes": "15K", "retweets": "8K", "verified": True},
        {"handle": "@random", "content": "Good morning everyone, nice weather today.", "likes": "2", "retweets": "0", "verified": False},
    ]

    print("信号判断器 - 测试\n")
    judgment = judge_all_signals(test_tweets, asset="oil")
    print_signal_report(judgment, asset="oil")
