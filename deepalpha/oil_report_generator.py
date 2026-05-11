# -*- coding: utf-8 -*-
"""
Oil risk warning report generator for DeepAlpha.

Core input: evidence_chain.py results.
CLI pipeline:
  local_intel_store.py -> event_cluster.py -> evidence_chain.py -> Markdown report

Example:
  python3 oil_report_generator.py --asset oil --hours 24
  python3 oil_report_generator.py --input evidence.json --output oil_report.md
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BULLISH_RULES = {
    "Hormuz blockade": ("hormuz", "blockade"),
    "tanker attack": ("tanker", "attack"),
    "OPEC cut": ("opec", "cut"),
    "sanction": ("sanction",),
    "supply disruption": ("supply", "disruption"),
    "pipeline explosion": ("pipeline", "explosion"),
}

BEARISH_RULES = {
    "OPEC increase": ("opec", "increase"),
    "demand slowdown": ("demand", "slowdown"),
    "recession": ("recession",),
    "ceasefire": ("ceasefire",),
    "SPR release": ("spr", "release"),
    "inventory build": ("inventory", "build"),
}

MULTI_SOURCE_SCORES = {
    "strong_multi_source": 1.0,
    "initial_multi_source": 0.7,
    "single_source": 0.35,
}


@dataclass
class EventSignal:
    event_id: str
    event_title: str
    direction: str
    direction_label: str
    confidence: float
    confidence_parts: dict[str, float]
    matched_bullish: list[str]
    matched_bearish: list[str]
    evidence_chain: dict[str, Any]


def generate_oil_report(evidence_chains: list[dict[str, Any]], asset: str = "oil", hours: int | float = 24) -> str:
    signals = [classify_event(chain) for chain in evidence_chains]
    bullish = [item for item in signals if item.direction == "bullish_oil"]
    bearish = [item for item in signals if item.direction == "bearish_oil"]
    neutral = [item for item in signals if item.direction == "neutral"]
    overall = build_overall_judgment(signals)
    overall_confidence = round(sum(item.confidence for item in signals) / len(signals), 2) if signals else 0.0

    lines = [
        "# 石油风险预警报告",
        "",
        f"- 资产：{asset}",
        f"- 时间范围：最近 {hours:g} 小时",
        f"- 生成时间：{datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"- 事件数量：{len(signals)}",
        "",
        "## 今日核心事件",
        "",
    ]

    if signals:
        for item in signals[:8]:
            lines.append(
                f"- **{item.event_title}**：{item.direction_label}，"
                f"置信度 {item.confidence:.2f}，来源 {item.evidence_chain.get('source_count', 0)} 个"
            )
    else:
        lines.append("- 暂无可用事件。")

    lines.extend(["", "## 利多因素", ""])
    append_signal_section(lines, bullish, positive=True)

    lines.extend(["", "## 利空因素", ""])
    append_signal_section(lines, bearish, positive=False)

    if neutral:
        lines.extend(["", "## 中性/待确认事件", ""])
        for item in neutral[:5]:
            lines.append(f"- **{item.event_title}**：未触发明确方向关键词，置信度 {item.confidence:.2f}")

    lines.extend(["", "## 关键证据链", ""])
    append_evidence_section(lines, signals)

    lines.extend(
        [
            "",
            "## 综合判断",
            "",
            overall,
            "",
            "## 置信度",
            "",
            f"- 综合置信度：**{overall_confidence:.2f}**",
            "- 置信度由来源可信度、多源确认程度、信息时效、关键词强度加权得到。",
            "",
        ]
    )

    if signals:
        lines.append("| 事件 | 方向 | 来源可信度 | 多源确认 | 时效 | 关键词强度 | 置信度 |")
        lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
        for item in signals[:10]:
            parts = item.confidence_parts
            lines.append(
                f"| {item.event_title} | {item.direction_label} | "
                f"{parts['source_credibility']:.2f} | {parts['multi_source']:.2f} | "
                f"{parts['recency']:.2f} | {parts['keyword_strength']:.2f} | {item.confidence:.2f} |"
            )

    lines.extend(
        [
            "",
            "## 风险提示",
            "",
            "- 本报告基于规则判断生成，不构成交易建议。",
            "- X/Twitter 信息可能存在误传、延迟、断章取义或账号被盗风险。",
            "- 单一来源事件即使触发方向关键词，也应等待更多来源确认。",
            "- 高影响地缘事件变化很快，应持续跟踪后续官方与通讯社更新。",
        ]
    )

    return "\n".join(lines) + "\n"


def classify_event(chain: dict[str, Any]) -> EventSignal:
    text = evidence_text(chain)
    matched_bullish = match_rules(text, BULLISH_RULES)
    matched_bearish = match_rules(text, BEARISH_RULES)

    if len(matched_bullish) > len(matched_bearish):
        direction = "bullish_oil"
        direction_label = "利多原油"
    elif len(matched_bearish) > len(matched_bullish):
        direction = "bearish_oil"
        direction_label = "利空原油"
    elif matched_bullish and matched_bearish:
        direction = "neutral"
        direction_label = "中性/信号冲突"
    else:
        direction = "neutral"
        direction_label = "中性"

    confidence_parts = confidence_components(chain, len(matched_bullish) + len(matched_bearish))
    confidence = weighted_confidence(confidence_parts)

    return EventSignal(
        event_id=str(chain.get("event_id") or ""),
        event_title=str(chain.get("event_title") or "未命名事件"),
        direction=direction,
        direction_label=direction_label,
        confidence=confidence,
        confidence_parts=confidence_parts,
        matched_bullish=matched_bullish,
        matched_bearish=matched_bearish,
        evidence_chain=chain,
    )


def match_rules(text: str, rules: dict[str, tuple[str, ...]]) -> list[str]:
    lower = text.lower()
    matched = []
    for label, parts in rules.items():
        if all(part in lower for part in parts):
            matched.append(label)
    return matched


def confidence_components(chain: dict[str, Any], keyword_hit_count: int) -> dict[str, float]:
    source_credibility = min(float(chain.get("average_credibility") or 0) / 10.0, 1.0)
    multi_source = MULTI_SOURCE_SCORES.get(str(chain.get("multi_source_status")), 0.35)
    recency = recency_score(chain)
    keyword_strength = min(keyword_hit_count / 2.0, 1.0)
    return {
        "source_credibility": round(source_credibility, 2),
        "multi_source": round(multi_source, 2),
        "recency": round(recency, 2),
        "keyword_strength": round(keyword_strength, 2),
    }


def weighted_confidence(parts: dict[str, float]) -> float:
    score = (
        parts["source_credibility"] * 0.35
        + parts["multi_source"] * 0.25
        + parts["recency"] * 0.20
        + parts["keyword_strength"] * 0.20
    )
    return round(score, 2)


def recency_score(chain: dict[str, Any]) -> float:
    last_seen = parse_datetime(chain.get("last_seen_time"))
    if last_seen is None:
        return 0.3
    age_hours = (datetime.now(timezone.utc) - last_seen).total_seconds() / 3600
    if age_hours <= 3:
        return 1.0
    if age_hours <= 24:
        return 0.75
    if age_hours <= 72:
        return 0.5
    return 0.25


def evidence_text(chain: dict[str, Any]) -> str:
    parts = [str(chain.get("event_title") or "")]
    for evidence in chain.get("evidence", []):
        parts.append(str(evidence.get("summary") or ""))
    return "\n".join(parts)


def append_signal_section(lines: list[str], signals: list[EventSignal], positive: bool) -> None:
    if not signals:
        lines.append("- 暂无明确因素。")
        return
    for item in signals[:6]:
        matched = item.matched_bullish if positive else item.matched_bearish
        lines.append(
            f"- **{item.event_title}**：触发 `{', '.join(matched)}`，"
            f"置信度 {item.confidence:.2f}。"
        )


def append_evidence_section(lines: list[str], signals: list[EventSignal]) -> None:
    if not signals:
        lines.append("- 暂无证据链。")
        return
    for item in signals[:5]:
        chain = item.evidence_chain
        lines.append(f"### {item.event_title}")
        lines.append("")
        lines.append(
            f"- 方向：{item.direction_label}；多源状态：{chain.get('multi_source_status')}；"
            f"平均可信度：{chain.get('average_credibility')}"
        )
        for evidence in chain.get("evidence", [])[:4]:
            account = evidence.get("source_account") or "未知来源"
            source_type = evidence.get("source_type") or "普通账号"
            published = evidence.get("published_time") or "未知时间"
            credibility = evidence.get("credibility_score")
            summary = evidence.get("summary") or ""
            url = evidence.get("url")
            suffix = f" [{url}]({url})" if url else ""
            lines.append(f"- `{account}`（{source_type}，{published}，可信度 {credibility}）：{summary}{suffix}")
        lines.append("")


def build_overall_judgment(signals: list[EventSignal]) -> str:
    bullish_score = sum(item.confidence for item in signals if item.direction == "bullish_oil")
    bearish_score = sum(item.confidence for item in signals if item.direction == "bearish_oil")

    if not signals:
        return "当前没有足够本地证据形成石油风险判断。"
    if bullish_score > bearish_score * 1.2:
        return "当前规则信号偏向 **利多原油**。主要风险来自供应中断、制裁、航运或 OPEC 减产相关事件。"
    if bearish_score > bullish_score * 1.2:
        return "当前规则信号偏向 **利空原油**。主要压力来自需求走弱、库存累积、SPR 释放或地缘缓和相关事件。"
    return "当前规则信号整体 **中性或多空交织**，需要等待更多来源确认和后续事件演化。"


def build_chains_from_local_store(asset: str, hours: int | float) -> list[dict[str, Any]]:
    from deepalpha.evidence_chain import build_evidence_chains
    from deepalpha.event_cluster import cluster_events
    from deepalpha.local_intel_store import read_intel

    records = read_intel(asset=asset, hours=hours)
    events = cluster_events(records)
    return build_evidence_chains(events)


def load_chains(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("evidence_chains"), list):
        return [item for item in data["evidence_chains"] if isinstance(item, dict)]
    raise ValueError("Input JSON must be an evidence chain list or contain evidence_chains")


def parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return ensure_aware(value)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return ensure_aware(datetime.fromisoformat(text))
    except ValueError:
        return None


def ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate oil risk warning Markdown report")
    parser.add_argument("--asset", default="oil", help="Asset to read from local store")
    parser.add_argument("--hours", type=float, default=24, help="Local store lookback window")
    parser.add_argument("--input", help="Optional evidence_chain.py JSON output")
    parser.add_argument("--output", help="Optional Markdown output path")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    chains = load_chains(args.input) if args.input else build_chains_from_local_store(args.asset, args.hours)
    report = generate_oil_report(chains, asset=args.asset, hours=args.hours)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"report_saved={output_path}")
        return

    print(report)


if __name__ == "__main__":
    main()
