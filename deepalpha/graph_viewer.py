# -*- coding: utf-8 -*-
"""
X 实时情报系统 - 独立关系图谱可视化
================================================
实现轻量、去重后的交互式关系图谱界面，无需依赖 Obsidian。

功能：
  1. 节点去重与低价值节点压缩
  2. 平面简约布局
  3. 缩放平移
  4. 点击聚焦关系
  5. 悬浮查看节点信息

启动方式：
  python3 graph_viewer.py
  然后访问 http://localhost:8080
"""

import os
import json
import http.server
import socketserver
import webbrowser
from datetime import datetime
from typing import List
from pathlib import Path


TEMPLATE_PATH = Path(__file__).with_name("graph_viewer_template.html")
HTML_TEMPLATE = TEMPLATE_PATH.read_text(encoding="utf-8")


class GraphHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """图谱 HTTP 请求处理器"""

    def __init__(self, *args, graph_data=None, **kwargs):
        self.graph_data = graph_data or {"nodes": [], "edges": []}
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode('utf-8'))

        elif self.path == '/api/graph':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(self.graph_data, ensure_ascii=False).encode('utf-8'))

        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass


def create_handler(graph_data):
    """创建带有图谱数据的处理器"""
    def handler(*args, **kwargs):
        return GraphHTTPHandler(*args, graph_data=graph_data, **kwargs)
    return handler


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


class GraphViewer:
    """关系图谱查看器"""

    def __init__(self, port: int = 8080):
        self.port = port
        self.graph_data = {"nodes": [], "edges": []}
        self.server = None

    def update_data(self, nodes: List[dict], edges: List[dict]):
        """更新图谱数据"""
        self.graph_data = {
            "nodes": nodes,
            "edges": edges,
            "generated": datetime.now().isoformat()
        }

    def load_from_file(self, filepath: str):
        """从文件加载图谱数据"""
        with open(filepath, 'r', encoding='utf-8') as f:
            self.graph_data = json.load(f)

    def start(self, open_browser: bool = True):
        """启动图谱服务器"""
        handler = create_handler(self.graph_data)

        with ReusableTCPServer(("", self.port), handler) as httpd:
            url = f"http://localhost:{self.port}"
            print(f"\n{'=' * 60}")
            print(f"  情报关系图谱服务已启动")
            print(f"  访问地址: {url}")
            print(f"{'=' * 60}\n")

            if open_browser:
                webbrowser.open(url)

            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\n服务已停止")


def run_viewer(port: int = 8080, graph_file: str = "./graph_data/关系图谱.json"):
    """运行图谱查看器"""
    viewer = GraphViewer(port)

    if graph_file and os.path.exists(graph_file):
        viewer.load_from_file(graph_file)

    viewer.start()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="情报关系图谱查看器")
    parser.add_argument("--port", type=int, default=8080, help="服务端口")
    parser.add_argument("--file", type=str, default="./graph_data/关系图谱.json", help="图谱数据文件")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")

    args = parser.parse_args()

    viewer = GraphViewer(args.port)

    if args.file and os.path.exists(args.file):
        viewer.load_from_file(args.file)
    else:
        print(f"图谱数据文件不存在: {args.file}")
        print("可先运行: python3 graph_engine.py")

    viewer.start(open_browser=not args.no_browser)
