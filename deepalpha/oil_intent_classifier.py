# -*- coding: utf-8 -*-
"""
Oil-specific intent classifier for DeepAlpha.

This module only classifies the user's oil question into oil sub-intents.
It does not crawl, clean, cluster events, generate evidence chains, judge
signals, or call any AI/model API.

Example:
  python3 oil_intent_classifier.py "霍尔木兹是不是出问题了？"
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any


OIL_INTENT_RULES = {
    "price_direction": {
        "tags": ["price", "direction", "short_term"],
        "keyword_groups": ["oil_price", "market_direction", "short_term"],
        "patterns": [
            r"涨|跌|上涨|下跌|拉升|回落|走势|方向|短线|今天.*油价|油价.*今天",
            r"\b(up|down|rise|fall|rally|drop|price|direction|trend|short[- ]?term)\b",
        ],
    },
    "geopolitics": {
        "tags": ["geopolitics", "war", "middle_east"],
        "keyword_groups": ["iran_conflict", "middle_east_war", "sanctions"],
        "patterns": [
            r"战争|冲突|中东|伊朗|以色列|导弹|袭击|制裁|停火|军事|地缘",
            r"\b(war|conflict|iran|israel|missile|attack|sanction|ceasefire|military|geopolitics)\b",
        ],
    },
    "opec_policy": {
        "tags": ["opec", "policy", "production"],
        "keyword_groups": ["opec_policy", "saudi_policy", "production_quota"],
        "patterns": [
            r"OPEC|欧佩克|沙特|减产|增产|产量|配额|会议|部长会议",
            r"\b(opec|opec\+|saudi|production|output|quota|cut|increase|meeting)\b",
        ],
    },
    "shipping_risk": {
        "tags": ["shipping", "hormuz", "tanker"],
        "keyword_groups": ["hormuz", "red_sea", "tanker_shipping"],
        "patterns": [
            r"霍尔木兹|红海|油轮|航运|海峡|封锁|航道|胡塞|船只|运输",
            r"\b(hormuz|red sea|tanker|shipping|strait|blockade|vessel|houthi|shipment)\b",
        ],
    },
    "inventory_macro": {
        "tags": ["inventory", "macro", "demand"],
        "keyword_groups": ["eia_inventory", "demand_macro", "fed_usd"],
        "patterns": [
            r"库存|EIA|API|美元|美联储|需求|消费|衰退|通胀|利率|炼厂|开工率",
            r"\b(inventory|eia|api|dollar|usd|fed|demand|consumption|recession|inflation|rate|refinery)\b",
        ],
    },
    "general_risk": {
        "tags": ["risk", "alert", "monitoring"],
        "keyword_groups": ["oil_risk_watch", "breaking_news", "broad_monitoring"],
        "patterns": [
            r"风险|预警|突发|异常|有什么事|出问题|发生了什么|关注什么|监控|监听",
            r"\b(risk|alert|breaking|urgent|watch|monitor|what happened|developing)\b",
        ],
    },
}

TIME_HORIZON_PATTERNS = {
    "intraday": [
        r"今天|现在|刚刚|马上|短线|日内|今晚",
        r"\b(today|now|intraday|right now|tonight|just)\b",
    ],
    "near_term": [
        r"明天|本周|这周|未来几天|短期|近期",
        r"\b(tomorrow|this week|near[- ]?term|next few days|soon)\b",
    ],
    "medium_term": [
        r"下周|本月|这个月|未来几周|中期",
        r"\b(next week|this month|next month|medium[- ]?term)\b",
    ],
}

REALTIME_PATTERNS = [
    r"现在|刚刚|突发|出问题|是不是.*了|有没有.*消息|最新|实时|马上|今天|短线|走势|怎么走|会不会",
    r"\b(now|breaking|latest|real[- ]?time|urgent|today|just in|short[- ]?term|trend)\b",
]


def classify_oil_intent(query: str) -> dict[str, Any]:
    text = query.strip()
    scores = score_intents(text)
    best_intent, best_score = pick_best_intent(scores)
    confidence = calculate_confidence(scores, best_intent)
    focus_tags = build_focus_tags(best_intent, scores)
    time_horizon = detect_time_horizon(text)
    need_realtime_crawl = detect_realtime_need(text, best_intent, confidence)

    return {
        "asset": "oil",
        "oil_intent": best_intent,
        "focus_tags": focus_tags,
        "time_horizon": time_horizon,
        "need_realtime_crawl": need_realtime_crawl,
        "suggested_keyword_groups": suggested_keyword_groups(best_intent, scores),
        "confidence": confidence,
    }


def score_intents(query: str) -> dict[str, int]:
    scores = {}
    for intent, rule in OIL_INTENT_RULES.items():
        score = 0
        for pattern in rule["patterns"]:
            matches = re.findall(pattern, query, flags=re.IGNORECASE)
            score += len(matches)
        scores[intent] = score
    return scores


def pick_best_intent(scores: dict[str, int]) -> tuple[str, int]:
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_intent, best_score = ranked[0]
    if best_score <= 0:
        return "general_risk", 0
    return best_intent, best_score


def calculate_confidence(scores: dict[str, int], best_intent: str) -> float:
    best = scores.get(best_intent, 0)
    if best <= 0:
        return 0.35

    total = sum(scores.values())
    second = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0
    dominance = (best - second) / max(best, 1)
    coverage = best / max(total, 1)
    confidence = 0.45 + dominance * 0.3 + coverage * 0.25
    return round(min(max(confidence, 0.35), 0.95), 2)


def build_focus_tags(best_intent: str, scores: dict[str, int]) -> list[str]:
    tags = []
    for intent, score in sorted(scores.items(), key=lambda item: item[1], reverse=True):
        if score <= 0 and intent != best_intent:
            continue
        tags.extend(OIL_INTENT_RULES[intent]["tags"])
        if len(tags) >= 6:
            break
    return dedupe(tags)


def suggested_keyword_groups(best_intent: str, scores: dict[str, int]) -> list[str]:
    groups = []
    for intent, score in sorted(scores.items(), key=lambda item: item[1], reverse=True):
        if intent != best_intent and score <= 0:
            continue
        groups.extend(OIL_INTENT_RULES[intent]["keyword_groups"])
        if len(groups) >= 6:
            break
    return dedupe(groups)


def detect_time_horizon(query: str) -> str:
    for horizon, patterns in TIME_HORIZON_PATTERNS.items():
        if any(re.search(pattern, query, flags=re.IGNORECASE) for pattern in patterns):
            return horizon
    return "unspecified"


def detect_realtime_need(query: str, intent: str, confidence: float) -> bool:
    if any(re.search(pattern, query, flags=re.IGNORECASE) for pattern in REALTIME_PATTERNS):
        return True
    if intent in {"geopolitics", "shipping_risk", "general_risk"} and confidence >= 0.5:
        return True
    return False


def dedupe(items: list[str]) -> list[str]:
    result = []
    seen = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classify oil-specific user intent")
    parser.add_argument("query", help="User oil question")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = classify_oil_intent(args.query)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
