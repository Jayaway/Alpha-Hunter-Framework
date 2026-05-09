# -*- coding: utf-8 -*-
"""
Format DeepAlpha JSON reports as Markdown.

This module is local-only:
  - no network access
  - no X/Twitter calls
  - no scraper usage

Example:
  python3 report_formatter.py reports/test_oil_report.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DISCLAIMER = "本报告仅用于信息分析与风险提示，不构成投资建议"


def format_report(report: dict[str, Any]) -> str:
    query = report.get("query") or "未知问题"
    decision = report.get("decision") or {}
    judgment = report.get("judgment") or {}
    graph = report.get("graph") or {}
    crawl_stats = report.get("crawl_stats") or {}

    direction = extract_direction(judgment)
    confidence = extract_confidence(judgment)
    evidence = extract_key_evidence(judgment)
    sources = extract_sources(report, judgment)
    graph_path = extract_graph_path(graph)

    lines = [
        "# DeepAlpha 石油情报分析报告",
        "",
        "## 用户问题",
        "",
        str(query),
        "",
        "## 系统识别结果",
        "",
        f"- 资产类型：{decision.get('asset', 'unknown')}",
        f"- 用户意图：{decision.get('user_intent', 'unknown')}",
        f"- 紧急程度：{decision.get('urgency', 'unknown')}",
        f"- 推荐账号：{format_list(decision.get('top_accounts'))}",
        f"- 抓取任务：{format_list(decision.get('crawl_tasks'))}",
        f"- 路由原因：{decision.get('why_this_route', '暂无')}",
        "",
        "## 当前市场阶段",
        "",
        f"- 阶段：{decision.get('current_regime', 'unknown')}",
        "",
        "## 综合判断",
        "",
        f"- 方向：**{direction}**",
        f"- 抓取总量：{crawl_stats.get('total', '未知')}",
        f"- 清洗后有效情报：{crawl_stats.get('cleaned', '未知')}",
        f"- 错误数：{len(crawl_stats.get('errors') or [])}",
        "",
        "## 置信度",
        "",
        f"- 聚合置信度：**{confidence}**",
        f"- 平均影响等级：{judgment.get('avg_impact', '暂无')}",
        "",
        "## 关键证据",
        "",
    ]

    if evidence:
        for item in evidence:
            lines.append(f"- {item}")
    else:
        lines.append("- 暂无结构化关键证据。")

    lines.extend(
        [
            "",
            "## 相关来源账号",
            "",
        ]
    )

    if sources:
        for source in sources:
            lines.append(f"- `{source}`")
    else:
        lines.append("- 暂无来源账号。")

    lines.extend(
        [
            "",
            "## 图谱文件路径",
            "",
            f"- `{graph_path}`",
            "",
            "## 风险提示",
            "",
            "- X/Twitter 信息可能存在误传、延迟、删除、账号改名或上下文缺失。",
            "- 单一来源消息需要等待更多高可信来源确认。",
            "- 地缘和能源市场变化较快，应结合后续官方公告、通讯社报道和市场价格反应继续跟踪。",
            "",
            "## 免责声明",
            "",
            DISCLAIMER,
            "",
        ]
    )

    return "\n".join(lines)


def extract_direction(judgment: dict[str, Any]) -> str:
    label = judgment.get("market_direction_label")
    if label:
        return str(label)

    direction = str(judgment.get("market_direction") or "").lower()
    if "bullish" in direction:
        return "利多"
    if "bearish" in direction:
        return "利空"
    return "中性"


def extract_confidence(judgment: dict[str, Any]) -> Any:
    if "aggregate_confidence" in judgment:
        return judgment.get("aggregate_confidence")
    if "confidence" in judgment:
        return judgment.get("confidence")
    return "暂无"


def extract_key_evidence(judgment: dict[str, Any]) -> list[str]:
    evidence = []
    for signal in judgment.get("top_signals") or []:
        handle = signal.get("tweet_handle") or "未知来源"
        content = one_line(signal.get("tweet_content") or "")
        direction = signal.get("direction_label") or signal.get("direction") or "未知方向"
        impact = signal.get("impact_level", "未知")
        reason = one_line(signal.get("impact_reason") or "")
        evidence.append(f"`{handle}` [{direction}, 影响{impact}级] {content} {reason}".strip())
    return evidence


def extract_sources(report: dict[str, Any], judgment: dict[str, Any]) -> list[str]:
    sources = []
    decision = report.get("decision") or {}
    for account in decision.get("top_accounts") or []:
        sources.append(str(account))

    for signal in judgment.get("top_signals") or []:
        handle = signal.get("tweet_handle")
        if handle:
            sources.append(str(handle))

    return dedupe([normalize_handle(item) for item in sources if item])


def extract_graph_path(graph: dict[str, Any]) -> str:
    for key in ("output_file", "graph_file", "path", "file"):
        value = graph.get(key)
        if value:
            return str(value)
    return "./graph_data/关系图谱.json"


def normalize_handle(value: str) -> str:
    text = value.strip()
    if not text:
        return text
    if not text.startswith("@"):
        text = f"@{text}"
    return text


def format_list(value: Any) -> str:
    if not value:
        return "暂无"
    if isinstance(value, list):
        return "、".join(str(item) for item in value) or "暂无"
    return str(value)


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


def one_line(value: str) -> str:
    return " ".join(str(value).split())


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Report JSON must be an object")
    return data


def output_path_for(input_path: Path, output: str | None) -> Path:
    if output:
        return Path(output)
    return input_path.with_suffix(".md")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert DeepAlpha JSON report to Markdown")
    parser.add_argument("input", help="Input JSON report path, e.g. reports/test_oil_report.json")
    parser.add_argument("--output", help="Output Markdown path; default uses the input stem with .md")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    input_path = Path(args.input)
    output_path = output_path_for(input_path, args.output)

    report = load_json(input_path)
    markdown = format_report(report)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    print(f"Markdown report saved: {output_path}")


if __name__ == "__main__":
    main()
