#!/usr/bin/env python3
"""Serve the DeepAlpha web UI and local JSON APIs."""

from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from deepalpha.graph_engine import DEFAULT_GRAPH_FILE, generate_graph_data
from deepalpha.intel_analyzer import analyze_history
from deepalpha.intel_router_v2 import decide


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = PROJECT_ROOT / "web"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8090


def load_graph() -> dict:
    graph_path = PROJECT_ROOT / DEFAULT_GRAPH_FILE
    if graph_path.exists():
        return json.loads(graph_path.read_text(encoding="utf-8"))
    return {"query": None, "generated": None, "nodes": [], "edges": []}


def refresh_graph(query: str | None = None) -> dict:
    try:
        generate_graph_data(
            input_dir=str(PROJECT_ROOT / "抓取的信息"),
            output_file=str(PROJECT_ROOT / DEFAULT_GRAPH_FILE),
            query=query,
        )
    except Exception:
        pass
    return load_graph()


def build_analysis(query: str) -> dict:
    decision = decide(query).to_dict()
    analysis = analyze_history(query, decision)
    graph = refresh_graph(query)
    judgment = analysis.get("judgment") or {}
    top_tweets = analysis.get("top_tweets") or []
    summary_lines = analysis.get("summary_lines") or []

    direction = judgment.get("market_direction_label") or "无明确方向"
    confidence = judgment.get("aggregate_confidence", 0)
    avg_impact = judgment.get("avg_impact", 0)
    source_names = [item.lstrip("@") for item in decision.get("top_accounts", [])]

    return {
        "query": query,
        "mode": "history",
        "decision": decision,
        "plan": {
            "core_variable": _core_variable(query, decision),
            "time_window": "默认覆盖短期事件冲击，并结合历史库做证据确认",
            "sources": source_names,
            "signals": _signals(decision, analysis),
        },
        "stats": {
            "total": analysis.get("total_tweets", 0),
            "relevant": analysis.get("relevant_count", 0),
            "graph_nodes": len(graph.get("nodes", [])),
            "graph_edges": len(graph.get("edges", [])),
        },
        "report": {
            "title": f"{query}：DeepAlpha 情报分析",
            "lead": "系统基于问题路由、历史情报、关系图谱和信号判断生成结论；没有足够证据时会保持不确定。",
            "summary_lines": summary_lines,
            "rows": _rows(analysis, judgment),
            "events": _events(top_tweets),
            "direction": direction,
            "evidence": f"相关情报 {analysis.get('relevant_count', 0)} 条 / 置信度 {confidence} / 平均影响 {avg_impact}/5",
            "risk": "本报告只基于当前本地历史库和可用公开数据，不构成投资建议；低样本或同源扩散会降低方向可靠性。",
            "top_tweets": top_tweets[:5],
        },
        "graph": graph,
    }


def _core_variable(query: str, decision: dict) -> str:
    asset = decision.get("asset") or "unknown"
    intent = decision.get("user_intent") or "general"
    return f"{query} / asset={asset} / intent={intent}"


def _signals(decision: dict, analysis: dict) -> list[dict]:
    signals = []
    for account in decision.get("top_accounts", [])[:8]:
        signals.append({"label": account.lstrip("@"), "provider": "x", "status": "success"})
    if analysis.get("relevant_count", 0) > 0:
        signals.append({"label": "history_match", "provider": "local", "status": "success"})
    else:
        signals.append({"label": "history_match", "provider": "local", "status": "error"})
    return signals


def _rows(analysis: dict, judgment: dict) -> list[list[str]]:
    signal_count = judgment.get("signal_count") or {}
    rows = [
        ["历史库", f"{analysis.get('total_tweets', 0)} 条", f"命中相关情报 {analysis.get('relevant_count', 0)} 条"],
        ["方向判断", judgment.get("market_direction_label") or "无明确方向", "证据不足或信号冲突时不强行给方向"],
        ["影响等级", f"{judgment.get('avg_impact', 0)}/5", "平均影响越高，越可能进入行动级观察"],
    ]
    if signal_count:
        rows.append(["信号分布", "；".join(f"{key}: {value}" for key, value in signal_count.items()), "用于检查方向是否集中"])
    return rows


def _events(top_tweets: list[dict]) -> list[dict]:
    if not top_tweets:
        return [
            {
                "title": "暂无高置信事件簇",
                "body": "当前历史库没有足够相关情报。可以执行实时抓取后再刷新分析。",
                "tags": ["needs_crawl", "low_sample"],
            }
        ]
    events = []
    for tweet in top_tweets[:4]:
        events.append(
            {
                "title": tweet.get("handle") or "未知来源",
                "body": str(tweet.get("content", "")).replace("\n", " ")[:180],
                "tags": ["evidence", str(tweet.get("_final_verdict") or "history")],
            }
        )
    return events


class DeepAlphaHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            self._send_json({"ok": True, "service": "deepalpha_web"})
            return
        if path == "/api/graph":
            self._send_json(load_graph())
            return
        if path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/analyze":
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown API endpoint")
            return
        try:
            payload = self._read_json()
            query = str(payload.get("query") or "").strip()
            if not query:
                raise ValueError("query is required")
            self._send_json(build_analysis(query))
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def guess_type(self, path: str) -> str:
        if path.endswith(".js"):
            return "application/javascript"
        return mimetypes.guess_type(path)[0] or super().guess_type(path)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return json.loads(raw or "{}")

    def _send_json(self, data: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local DeepAlpha web server.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DeepAlphaHandler)
    print(f"DeepAlpha Web: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
