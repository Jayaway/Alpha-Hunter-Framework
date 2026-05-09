# -*- coding: utf-8 -*-
"""
独立情报关系图谱引擎。

输入抓取后的推文 CSV 或推文字典，输出给 graph_viewer.py 使用的纯 JSON：
{
  "nodes": [{"id": "...", "type": "...", "mention_count": 1, "engagement": 0}],
  "edges": [{"source": "...", "target": "...", "type": "...", "weight": 1}]
}
"""

import ast
import glob
import hashlib
import json
import os
import re
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple


DEFAULT_INPUT_DIR = "./抓取的信息/"
DEFAULT_GRAPH_FILE = "./graph_data/关系图谱.json"
MAX_GRAPH_NODES = 80
MAX_GRAPH_EDGES = 140
MAX_EDGES_PER_NODE = 6
MIN_EDGE_WEIGHT = 2
RELATION_PRIORITY = {
    "mentions": 4,
    "discusses": 4,
    "reports": 4,
    "posts_about": 3,
    "co_occurs": 1,
}

ACCOUNT_LABELS = {
    "JavierBlas": ("石油分析家", "Javier Blas / @JavierBlas"),
    "Reuters": ("路透社", "@Reuters"),
    "KSAmofaEN": ("沙特外交部", "@KSAmofaEN"),
    "TankersTrackers": ("油轮追踪员", "@TankersTrackers"),
    "realDonaldTrump": ("特朗普", "@realDonaldTrump"),
    "DeItaone": ("快讯账号", "@DeItaone"),
    "ZeroHedge": ("市场快讯", "@ZeroHedge"),
    "CathieDWood": ("木头姐", "@CathieDWood"),
    "howardlindzon": ("投资人", "@howardlindzon"),
    "federalreserve": ("美联储", "@federalreserve"),
    "FaisalbinFarhan": ("沙特外长", "@FaisalbinFarhan"),
    "KingSalman": ("沙特国王", "@KingSalman"),
    "grok": ("AI摘要源", "@grok"),
    "badralbusaidi": ("海湾外交官", "@badralbusaidi"),
}

ENTITY_LABELS = {
    "Iran": "伊朗",
    "Israel": "以色列",
    "US": "美国",
    "USA": "美国",
    "United States": "美国",
    "China": "中国",
    "Russia": "俄罗斯",
    "Saudi Arabia": "沙特",
    "Hormuz": "霍尔木兹",
    "Red Sea": "红海",
    "Middle East": "中东",
    "Persian Gulf": "波斯湾",
    "Gulf": "海湾",
    "Riyadh": "利雅得",
    "FaisalbinFarhan": "沙特外长",
    "KingSalman": "沙特国王",
    "Tehran": "德黑兰",
    "Moscow": "莫斯科",
    "Beijing": "北京",
    "Washington": "华盛顿",
    "Tel Aviv": "特拉维夫",
    "oil": "原油",
    "crude": "原油",
    "WTI": "WTI原油",
    "Brent": "布伦特原油",
    "gold": "黄金",
    "bitcoin": "比特币",
    "BTC": "比特币",
    "crypto": "加密货币",
    "dollar": "美元",
    "DXY": "美元指数",
    "stock": "股票",
    "equity": "股市",
    "production cut": "减产",
    "output cut": "减产",
    "rate cut": "降息",
    "rate hike": "加息",
    "sanction": "制裁",
    "embargo": "禁运",
    "blockade": "封锁",
    "attack": "袭击",
    "strike": "打击",
    "missile": "导弹",
    "invasion": "入侵",
    "ceasefire": "停火",
    "war": "战争",
    "conflict": "冲突",
    "recession": "衰退",
    "inflation": "通胀",
    "inventory": "库存",
    "supply disruption": "供应中断",
    "demand surge": "需求激增",
    "tariff": "关税",
    "OPEC": "欧佩克",
    "OPEC+": "欧佩克+",
    "Federal Reserve": "美联储",
    "Fed": "美联储",
    "ECB": "欧洲央行",
    "IMF": "国际货币基金组织",
    "World Bank": "世界银行",
    "Bloomberg": "彭博社",
    "WSJ": "华尔街日报",
    "CNBC": "CNBC",
    "Axios": "Axios",
    "IDF": "以色列军方",
    "NATO": "北约",
    "UN": "联合国",
    "White House": "白宫",
    "Pentagon": "五角大楼",
    "Kremlin": "克里姆林宫",
}

TYPE_LABELS = {
    "account": "账号/角色",
    "organization": "机构",
    "location": "地点",
    "asset": "资产",
    "event": "事件",
    "hashtag": "话题",
    "keyword": "关键词",
}

ORGANIZATIONS = {
    "OPEC": "organization",
    "OPEC+": "organization",
    "Federal Reserve": "organization",
    "Fed": "organization",
    "美联储": "organization",
    "ECB": "organization",
    "IMF": "organization",
    "World Bank": "organization",
    "Reuters": "organization",
    "Bloomberg": "organization",
    "WSJ": "organization",
    "CNBC": "organization",
    "Axios": "organization",
    "IDF": "organization",
    "NATO": "organization",
    "UN": "organization",
    "White House": "organization",
    "Pentagon": "organization",
    "Kremlin": "organization",
}

LOCATIONS = {
    "Saudi Arabia",
    "Russia",
    "Iran",
    "Israel",
    "China",
    "US",
    "USA",
    "United States",
    "Hormuz",
    "Red Sea",
    "Middle East",
    "Gulf",
    "Persian Gulf",
    "Tel Aviv",
    "Tehran",
    "Moscow",
    "Beijing",
    "Washington",
}

ASSETS = {
    "oil",
    "crude",
    "WTI",
    "Brent",
    "gold",
    "bitcoin",
    "BTC",
    "crypto",
    "dollar",
    "DXY",
    "stock",
    "equity",
    "原油",
    "黄金",
    "美元",
    "比特币",
    "加密货币",
}

EVENT_KEYWORDS = {
    "production cut",
    "output cut",
    "rate cut",
    "rate hike",
    "sanction",
    "embargo",
    "blockade",
    "attack",
    "strike",
    "missile",
    "invasion",
    "ceasefire",
    "war",
    "conflict",
    "recession",
    "inflation",
    "inventory",
    "supply disruption",
    "demand surge",
    "tariff",
    "增产",
    "减产",
    "降息",
    "加息",
    "制裁",
    "战争",
    "冲突",
    "衰退",
    "通胀",
    "关税",
}


def parse_list_value(value) -> List[str]:
    if value is None:
        return []
    try:
        import pandas as pd
        if pd.isna(value):
            return []
    except (ImportError, TypeError, ValueError):
        pass

    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]

    text = str(value).strip()
    if not text or text in ("[]", "nan", "None"):
        return []

    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, (list, tuple, set)):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except (SyntaxError, ValueError):
            pass

    return [item.strip() for item in re.split(r"[,;，；]\s*", text) if item.strip()]


def parse_count(value) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    try:
        text = str(value).replace(",", "").strip()
        if not text or text == "nan":
            return 0
        if text.endswith("K"):
            return int(float(text[:-1]) * 1000)
        if text.endswith("M"):
            return int(float(text[:-1]) * 1000000)
        return int(float(text))
    except (TypeError, ValueError):
        return 0


def contains_entity(content_lower: str, entity_name: str) -> bool:
    name = str(entity_name).strip()
    if not name:
        return False

    name_lower = name.lower()
    if re.search(r"[\u4e00-\u9fff]", name_lower):
        return name_lower in content_lower

    pattern = r"(?<![A-Za-z0-9_])" + re.escape(name_lower) + r"(?![A-Za-z0-9_])"
    return re.search(pattern, content_lower) is not None


def display_info(node_id: str, node_type: str) -> Tuple[str, str]:
    if node_type == "account":
        label, detail = ACCOUNT_LABELS.get(node_id, ("情报账号", f"@{node_id}"))
        return label, detail

    label = ENTITY_LABELS.get(node_id, node_id)
    detail = node_id if label != node_id else TYPE_LABELS.get(node_type, node_type)
    return label, detail


def normalize_tweet(row: dict) -> dict:
    def pick(*names, default=""):
        for name in names:
            value = row.get(name)
            if value is not None and str(value) != "nan":
                return value
        return default

    content = str(pick("content", "Content", default="")).strip()
    tweet_id = str(pick("tweet_id", "Tweet ID", "tweet id", default="")).replace("tweet_id:", "")
    if not tweet_id:
        tweet_id = hashlib.md5(content.encode("utf-8")).hexdigest()[:12]

    return {
        "name": pick("name", "Name"),
        "handle": pick("handle", "Handle"),
        "timestamp": pick("timestamp", "Timestamp"),
        "verified": pick("verified", "Verified", default=False),
        "content": content,
        "replies": pick("replies", "Comments", default=0),
        "retweets": pick("retweets", "Retweets", default=0),
        "likes": pick("likes", "Likes", default=0),
        "analytics": pick("analytics", "Analytics", default=0),
        "tags": parse_list_value(pick("tags", "Tags", default=[])),
        "mentions": parse_list_value(pick("mentions", "Mentions", default=[])),
        "tweet_link": pick("tweet_link", "Tweet Link"),
        "tweet_id": tweet_id,
    }


def load_tweets_from_csv_dir(input_dir: str = DEFAULT_INPUT_DIR) -> List[dict]:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("读取 CSV 需要 pandas，请先安装 requirements.txt") from exc

    tweets = []
    seen = set()

    for csv_path in sorted(glob.glob(os.path.join(input_dir, "*.csv"))):
        df = pd.read_csv(csv_path)
        for row in df.to_dict(orient="records"):
            tweet = normalize_tweet(row)
            key = tweet["tweet_id"] or hashlib.md5(tweet["content"].encode("utf-8")).hexdigest()
            if key in seen or not tweet["content"]:
                continue
            seen.add(key)
            tweets.append(tweet)

    return tweets


class GraphBuilder:
    def __init__(self):
        self.nodes: Dict[str, dict] = {}
        self.edges: Dict[Tuple[str, str, str], dict] = {}

    def add_tweet(self, tweet: dict):
        tweet = normalize_tweet(tweet)
        content = tweet["content"]
        content_lower = content.lower()
        engagement = parse_count(tweet["likes"]) + parse_count(tweet["retweets"]) + parse_count(tweet["replies"])
        found = []

        author = str(tweet.get("handle") or "").lstrip("@").strip()
        if author:
            self._add_node(author, "account", engagement)
            found.append(author)

        for mention in parse_list_value(tweet.get("mentions")):
            name = mention.lstrip("@")
            self._add_node(name, "account", engagement)
            found.append(name)
            if author:
                self._add_edge(author, name, "mentions")

        for tag in parse_list_value(tweet.get("tags")):
            name = tag.lstrip("#")
            self._add_node(name, "hashtag", engagement)
            found.append(name)
            if author:
                self._add_edge(author, name, "posts_about")

        for name, entity_type in ORGANIZATIONS.items():
            if contains_entity(content_lower, name):
                self._add_node(name, entity_type, engagement)
                found.append(name)
                if author:
                    self._add_edge(author, name, "mentions")

        for name in LOCATIONS:
            if contains_entity(content_lower, name):
                self._add_node(name, "location", engagement)
                found.append(name)
                if author:
                    self._add_edge(author, name, "mentions")

        for name in ASSETS:
            if contains_entity(content_lower, name):
                self._add_node(name, "asset", engagement)
                found.append(name)
                if author:
                    self._add_edge(author, name, "discusses")

        for name in EVENT_KEYWORDS:
            if contains_entity(content_lower, name):
                self._add_node(name, "event", engagement)
                found.append(name)
                if author:
                    self._add_edge(author, name, "reports")

        unique_found = list(dict.fromkeys(found))
        for i, source in enumerate(unique_found):
            for target in unique_found[i + 1:]:
                self._add_edge(source, target, "co_occurs")

    def to_graph(self, query: str = "") -> dict:
        nodes, edges = self._prune_graph()
        return {
            "nodes": nodes,
            "edges": edges,
            "query": query,
            "generated": datetime.now().isoformat(),
        }

    def _prune_graph(self) -> Tuple[List[dict], List[dict]]:
        top_nodes = sorted(
            self.nodes.values(),
            key=lambda n: (n.get("mention_count", 0), n.get("engagement", 0)),
            reverse=True,
        )[:MAX_GRAPH_NODES]
        node_ids = {node["id"] for node in top_nodes}

        candidate_edges = [
            edge for edge in self.edges.values()
            if edge["source"] in node_ids
            and edge["target"] in node_ids
            and edge.get("weight", 0) >= MIN_EDGE_WEIGHT
        ]
        candidate_edges.sort(
            key=lambda e: (RELATION_PRIORITY.get(e.get("type"), 0), e.get("weight", 0)),
            reverse=True,
        )

        edge_count_by_node = defaultdict(int)
        kept_edges = []
        seen_pairs = set()
        for edge in candidate_edges:
            source = edge["source"]
            target = edge["target"]
            pair_key = tuple(sorted((source, target)))
            if pair_key in seen_pairs:
                continue
            if edge_count_by_node[source] >= MAX_EDGES_PER_NODE:
                continue
            if edge_count_by_node[target] >= MAX_EDGES_PER_NODE:
                continue
            kept_edges.append(edge)
            seen_pairs.add(pair_key)
            edge_count_by_node[source] += 1
            edge_count_by_node[target] += 1
            if len(kept_edges) >= MAX_GRAPH_EDGES:
                break

        return top_nodes, kept_edges

    def _add_node(self, node_id: str, node_type: str, engagement: int = 0):
        if not node_id:
            return
        if node_id not in self.nodes:
            label, detail = display_info(node_id, node_type)
            self.nodes[node_id] = {
                "id": node_id,
                "label": label,
                "detail": detail,
                "type": node_type,
                "type_label": TYPE_LABELS.get(node_type, node_type),
                "mention_count": 0,
                "engagement": 0,
            }
        self.nodes[node_id]["mention_count"] += 1
        self.nodes[node_id]["engagement"] += engagement

    def _add_edge(self, source: str, target: str, edge_type: str):
        if not source or not target or source == target:
            return
        key = (source, target, edge_type)
        if key not in self.edges:
            self.edges[key] = {
                "source": source,
                "target": target,
                "type": edge_type,
                "weight": 0,
            }
        self.edges[key]["weight"] += 1


def build_graph(tweets: List[dict], query: str = "") -> dict:
    builder = GraphBuilder()
    for tweet in tweets:
        builder.add_tweet(tweet)
    return builder.to_graph(query=query)


def save_graph_data(graph_data: dict, output_file: str = DEFAULT_GRAPH_FILE) -> str:
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)
    return output_file


def generate_graph_data(tweets: Optional[List[dict]] = None,
                        input_dir: str = DEFAULT_INPUT_DIR,
                        output_file: str = DEFAULT_GRAPH_FILE,
                        query: str = "") -> dict:
    if tweets is None:
        tweets = load_tweets_from_csv_dir(input_dir)
        print(f"  已从 {input_dir} 读取历史推文 {len(tweets)} 条")
    else:
        tweets = [normalize_tweet(tweet) for tweet in tweets]

    graph_data = build_graph(tweets, query=query)
    save_graph_data(graph_data, output_file)

    print(f"  独立图谱已生成: {output_file}")
    print(f"  节点: {len(graph_data['nodes'])} | 关系: {len(graph_data['edges'])}")
    return {
        "output_file": output_file,
        "node_count": len(graph_data["nodes"]),
        "edge_count": len(graph_data["edges"]),
        "tweet_count": len(tweets),
    }


if __name__ == "__main__":
    generate_graph_data()
