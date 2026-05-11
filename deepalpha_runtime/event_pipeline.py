# -*- coding: utf-8 -*-
"""
DeepAlpha v0.2 event-level pipeline.

This module is intentionally a thin orchestration layer. It keeps the v0.1
tweet-level pipeline intact while adding event clustering, evidence chains, and
event-level signal summaries.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


MARKET_MOVERS = {
    "@realdonaldtrump",
    "@elonmusk",
    "@federalreserve",
    "@potus",
    "@whitehouse",
    "@opecsecretariat",
    "@ksamofaen",
    "@ustreasury",
}


def run_event_pipeline(
    tweets: list[dict[str, Any]],
    query: str,
    decision: dict[str, Any],
    max_events: int = 8,
) -> dict[str, Any]:
    from deepalpha.event_cluster import cluster_events
    from deepalpha.evidence_chain import build_evidence_chain

    asset = decision.get("asset") or "unknown"
    events = cluster_events(tweets)
    event_reports = []

    for event in events[:max_events]:
        chain = build_evidence_chain(event)
        signal = judge_event_signal(event, chain, asset=asset)
        event_reports.append(
            {
                "event_id": event.get("event_id"),
                "event_title": event.get("event_title"),
                "asset": asset,
                "first_seen_time": event.get("first_seen_time"),
                "last_seen_time": event.get("last_seen_time"),
                "sources": event.get("sources", []),
                "independent_source_count": event.get("source_count", 0),
                "echo_source_count": max(
                    len(event.get("related_tweets", [])) - int(event.get("source_count", 0) or 0),
                    0,
                ),
                "main_keywords": event.get("main_keywords", []),
                "related_tweet_count": len(event.get("related_tweets", [])),
                "evidence_chain": chain,
                "signal": signal,
                "summary": summarize_event(event, chain, signal),
            }
        )

    aggregate = aggregate_event_signals(event_reports)
    return {
        "version": "v0.2",
        "query": query,
        "asset": asset,
        "input_tweet_count": len(tweets),
        "event_count": len(event_reports),
        "aggregate_signal": aggregate,
        "events": event_reports,
    }


def judge_event_signal(event: dict[str, Any], chain: dict[str, Any], asset: str | None = None) -> dict[str, Any]:
    from deepalpha.signal_judge import judge_all_signals

    related_tweets = event.get("related_tweets", []) or []
    tweet_signal = judge_all_signals(related_tweets, asset=asset)
    market_movers = find_market_movers(related_tweets)
    evidence_score = score_evidence(chain)
    evidence_quality = classify_evidence_quality(chain, evidence_score)

    signal_type = "impact_signal" if market_movers else "information_signal"
    requires_confirmation = (
        bool(market_movers)
        or chain.get("multi_source_status") == "single_source"
        or evidence_quality in {"weak", "single_source"}
        or not tweet_signal.get("market_direction")
    )

    return {
        "signal_type": signal_type,
        "market_direction": tweet_signal.get("market_direction"),
        "market_direction_label": tweet_signal.get("market_direction_label"),
        "confidence": round(float(tweet_signal.get("aggregate_confidence") or 0) * evidence_score, 2),
        "raw_signal_confidence": tweet_signal.get("aggregate_confidence", 0),
        "impact_level": tweet_signal.get("avg_impact", 0),
        "evidence_score": evidence_score,
        "evidence_quality": evidence_quality,
        "multi_source_status": chain.get("multi_source_status"),
        "requires_confirmation": requires_confirmation,
        "market_movers": market_movers,
        "reason": build_signal_reason(tweet_signal, chain, market_movers),
    }


def aggregate_event_signals(events: list[dict[str, Any]]) -> dict[str, Any]:
    if not events:
        return {
            "market_direction": None,
            "market_direction_label": None,
            "confidence": 0.0,
            "requires_confirmation": True,
            "reason": "暂无可聚合事件。",
        }

    weighted: Counter[str] = Counter()
    labels: dict[str, str] = {}
    total_confidence = 0.0
    directional_events = 0
    requires_confirmation = False

    for event in events:
        signal = event.get("signal", {})
        direction = signal.get("market_direction")
        confidence = float(signal.get("confidence") or 0)
        if signal.get("requires_confirmation"):
            requires_confirmation = True
        if not direction:
            continue
        weighted[direction] += max(confidence, 0.05)
        labels[direction] = signal.get("market_direction_label") or direction
        total_confidence += confidence
        directional_events += 1

    if not weighted:
        return {
            "market_direction": None,
            "market_direction_label": None,
            "confidence": 0.0,
            "requires_confirmation": True,
            "reason": "事件已聚合，但没有形成稳定方向。",
        }

    direction, _ = weighted.most_common(1)[0]
    confidence = round(total_confidence / max(directional_events, 1), 2)
    return {
        "market_direction": direction,
        "market_direction_label": labels.get(direction, direction),
        "confidence": confidence,
        "directional_event_count": directional_events,
        "requires_confirmation": requires_confirmation,
        "reason": f"基于 {directional_events} 个事件级方向信号聚合。",
    }


def score_evidence(chain: dict[str, Any]) -> float:
    source_count = int(chain.get("source_count", 0) or 0)
    credibility = float(chain.get("average_credibility", 0) or 0) / 10.0
    source_score = min(source_count / 3.0, 1.0)
    status_bonus = {
        "strong_multi_source": 0.12,
        "initial_multi_source": 0.05,
        "single_source": -0.08,
    }.get(chain.get("multi_source_status"), 0)
    return round(min(max(credibility * 0.62 + source_score * 0.38 + status_bonus, 0.0), 1.0), 2)


def classify_evidence_quality(chain: dict[str, Any], evidence_score: float) -> str:
    status = chain.get("multi_source_status")
    if status == "single_source":
        return "single_source"
    if status == "strong_multi_source" and evidence_score >= 0.7:
        return "strong"
    if status == "initial_multi_source" or evidence_score >= 0.45:
        return "medium"
    return "weak"


def find_market_movers(tweets: list[dict[str, Any]]) -> list[str]:
    movers = []
    for tweet in tweets:
        handle = normalize_handle(tweet.get("handle") or tweet.get("username") or tweet.get("source"))
        if handle and handle.lower() in MARKET_MOVERS:
            movers.append(handle)
    return dedupe(movers)


def build_signal_reason(tweet_signal: dict[str, Any], chain: dict[str, Any], market_movers: list[str]) -> str:
    parts = []
    status = chain.get("multi_source_status")
    source_count = chain.get("source_count", 0)
    if status:
        parts.append(f"证据状态 {status}，独立来源 {source_count} 个")
    if tweet_signal.get("market_direction_label"):
        parts.append(f"方向信号为 {tweet_signal['market_direction_label']}")
    if market_movers:
        parts.append(f"包含市场冲击源 {', '.join(market_movers)}，需要二次确认")
    return "；".join(parts) or "事件证据不足，暂不形成强信号"


def summarize_event(event: dict[str, Any], chain: dict[str, Any], signal: dict[str, Any]) -> str:
    title = event.get("event_title") or "未知事件"
    evidence_quality = signal.get("evidence_quality") or "unknown"
    direction = signal.get("market_direction_label") or "暂无明确方向"
    confirm = "需要二次确认" if signal.get("requires_confirmation") else "可进入方向判断"
    return f"{title}：证据质量 {evidence_quality}，方向 {direction}，{confirm}。"


def normalize_handle(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if not text.startswith("@"):
        text = f"@{text}"
    return text


def dedupe(items: list[str]) -> list[str]:
    result = []
    seen = set()
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def print_event_pipeline_report(pipeline: dict[str, Any]) -> None:
    aggregate = pipeline.get("aggregate_signal", {})
    print("\n" + "=" * 60)
    print("  v0.2 事件级情报报告")
    print("=" * 60)
    print(f"  输入推文: {pipeline.get('input_tweet_count', 0)} 条")
    print(f"  事件数量: {pipeline.get('event_count', 0)} 个")
    print(f"  聚合方向: {aggregate.get('market_direction_label') or '暂无明确方向'}")
    print(f"  聚合置信度: {aggregate.get('confidence', 0)}")
    print(f"  需要二次确认: {'是' if aggregate.get('requires_confirmation') else '否'}")

    for i, event in enumerate(pipeline.get("events", [])[:5], 1):
        signal = event.get("signal", {})
        print(f"\n  {i}. {event.get('event_title')}")
        print(f"     来源: {', '.join(event.get('sources', [])[:5]) or '暂无'}")
        print(f"     证据: {signal.get('evidence_quality')} / {signal.get('multi_source_status')}")
        print(f"     方向: {signal.get('market_direction_label') or '暂无明确方向'}")
        print(f"     提醒: {'需要二次确认' if signal.get('requires_confirmation') else '可进入判断'}")
    print("=" * 60)
