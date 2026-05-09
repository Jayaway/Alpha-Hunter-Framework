# -*- coding: utf-8 -*-
"""
X 实时情报系统 - Obsidian 关系图谱生成器
================================================
从抓取的推文中提取实体和关系，生成 Obsidian 兼容的 Markdown 文件，
支持双向链接 [[entity]]，在 Obsidian 中形成可视化的关系图谱。

功能：
  1. 实体提取：人物、组织、地点、事件、资产、话题标签
  2. 关系建立：推文-实体、实体-实体共现关系
  3. 生成 Obsidian 兼容的 Markdown 文件（双向链接）
  4. 支持增量更新，避免重复生成

用法：
  from obsidian_graph import generate_obsidian_graph
  generate_obsidian_graph(tweets, output_dir="./obsidian_vault/")
"""

import os
import re
import json
import hashlib
import ast
import glob
from datetime import datetime
from collections import defaultdict
from typing import Optional, List, Dict, Set, Tuple


ENTITY_TYPES = {
    "person": "人物",
    "organization": "组织机构",
    "location": "地点",
    "event": "事件",
    "asset": "资产",
    "hashtag": "话题",
    "account": "账号",
    "keyword": "关键词",
}

ORGANIZATIONS = {
    "OPEC": "organization",
    "OPEC+": "organization",
    "Saudi Arabia": "location",
    "Russia": "location",
    "Iran": "location",
    "Israel": "location",
    "China": "location",
    "US": "location",
    "USA": "location",
    "United States": "location",
    "Federal Reserve": "organization",
    "Fed": "organization",
    "美联储": "organization",
    "ECB": "organization",
    "IMF": "organization",
    "World Bank": "organization",
    "Reuters": "organization",
    "Bloomberg": "organization",
    "WSJ": "organization",
    "IDF": "organization",
    "NATO": "organization",
    "UN": "organization",
    "White House": "organization",
    "Pentagon": "organization",
    "Kremlin": "organization",
    "Hormuz": "location",
    "Red Sea": "location",
    "Middle East": "location",
    "Gulf": "location",
    "Persian Gulf": "location",
    "Tel Aviv": "location",
    "Tehran": "location",
    "Moscow": "location",
    "Beijing": "location",
    "Washington": "location",
}


def _parse_list_value(value) -> List[str]:
    """把 scraper 里的列表字段和 CSV 读回来的字符串都统一成 list。"""
    if value is None:
        return []
    try:
        import pandas as pd
        if pd.isna(value):
            return []
    except (ImportError, TypeError, ValueError):
        pass

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple) or isinstance(value, set):
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


def _normalize_tweet(row: dict) -> dict:
    """兼容 crawler_runner 和 scraper.save_to_csv 的字段名。"""
    def pick(*names, default=""):
        for name in names:
            value = row.get(name)
            if value is not None and str(value) != "nan":
                return value
        return default

    tweet_id = str(pick("tweet_id", "Tweet ID", "tweet id", default="")).replace("tweet_id:", "")
    content = str(pick("content", "Content", default="")).strip()
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
        "tags": _parse_list_value(pick("tags", "Tags", default=[])),
        "mentions": _parse_list_value(pick("mentions", "Mentions", default=[])),
        "tweet_link": pick("tweet_link", "Tweet Link"),
        "tweet_id": tweet_id,
    }


def load_tweets_from_csv_dir(input_dir: str = "./抓取的信息/") -> List[dict]:
    """读取已有抓取 CSV，按 tweet_id/content 去重后返回标准推文字典。"""
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("读取历史 CSV 需要 pandas，请先安装 requirements.txt") from exc

    tweets = []
    seen = set()
    pattern = os.path.join(input_dir, "*.csv")

    for csv_path in sorted(glob.glob(pattern)):
        df = pd.read_csv(csv_path)
        for row in df.to_dict(orient="records"):
            tweet = _normalize_tweet(row)
            dedupe_key = tweet.get("tweet_id") or hashlib.md5(
                tweet.get("content", "").encode("utf-8")
            ).hexdigest()
            if dedupe_key in seen or not tweet.get("content"):
                continue
            seen.add(dedupe_key)
            tweets.append(tweet)

    return tweets

ASSETS = {
    "oil": "asset",
    "crude": "asset",
    "WTI": "asset",
    "Brent": "asset",
    "gold": "asset",
    "bitcoin": "asset",
    "BTC": "asset",
    "crypto": "asset",
    "dollar": "asset",
    "DXY": "asset",
    "原油": "asset",
    "黄金": "asset",
    "美元": "asset",
    "加密货币": "asset",
}

EVENT_KEYWORDS = {
    "production cut": "event",
    "output cut": "event",
    "rate cut": "event",
    "rate hike": "event",
    "sanction": "event",
    "embargo": "event",
    "blockade": "event",
    "attack": "event",
    "strike": "event",
    "missile": "event",
    "invasion": "event",
    "ceasefire": "event",
    "war": "event",
    "conflict": "event",
    "recession": "event",
    "inflation": "event",
    "inventory": "event",
    "supply disruption": "event",
    "demand surge": "event",
    "增产": "event",
    "减产": "event",
    "降息": "event",
    "加息": "event",
    "制裁": "event",
    "战争": "event",
    "冲突": "event",
    "衰退": "event",
    "通胀": "event",
}


class Entity:
    """实体类"""
    def __init__(self, name: str, entity_type: str, source: str = ""):
        self.name = name
        self.entity_type = entity_type
        self.source = source
        self.mentions: List[Dict] = []
        self.related_entities: Set[str] = set()
        self.first_seen = datetime.now().isoformat()
        self.last_seen = datetime.now().isoformat()
        self.mention_count = 0
        self.total_engagement = 0

    def add_mention(self, tweet_id: str, content: str, timestamp: str,
                   engagement: int = 0, sentiment: str = "neutral"):
        self.mentions.append({
            "tweet_id": tweet_id,
            "content": content[:200],
            "timestamp": timestamp,
            "engagement": engagement,
            "sentiment": sentiment,
        })
        self.mention_count += 1
        self.total_engagement += engagement
        self.last_seen = timestamp or datetime.now().isoformat()

    def to_dict(self):
        return {
            "name": self.name,
            "type": self.entity_type,
            "type_label": ENTITY_TYPES.get(self.entity_type, self.entity_type),
            "source": self.source,
            "mention_count": self.mention_count,
            "total_engagement": self.total_engagement,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "related_entities": list(self.related_entities),
        }


class Relation:
    """关系类"""
    def __init__(self, source: str, target: str, relation_type: str, weight: int = 1):
        self.source = source
        self.target = target
        self.relation_type = relation_type
        self.weight = weight
        self.evidence: List[str] = []

    def add_evidence(self, tweet_id: str):
        if tweet_id not in self.evidence:
            self.evidence.append(tweet_id)
            self.weight += 1


class EntityExtractor:
    """实体提取器"""

    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.relations: Dict[Tuple[str, str, str], Relation] = {}

    def extract_from_tweet(self, tweet: dict) -> Dict[str, Entity]:
        """从单条推文提取实体"""
        content = tweet.get("content", "")
        handle = tweet.get("handle", "")
        tweet_id = tweet.get("tweet_id", str(hash(content)))
        timestamp = tweet.get("timestamp", "")
        engagement = self._calc_engagement(tweet)

        found_entities: Dict[str, Entity] = {}

        author_entity = self._get_or_create_entity(
            handle.lstrip("@"), "account", "tweet_author"
        )
        author_entity.add_mention(tweet_id, content, timestamp, engagement)
        found_entities[author_entity.name] = author_entity

        mentions = _parse_list_value(tweet.get("mentions", []))
        for mention in mentions:
            mention_name = mention.lstrip("@")
            if mention_name:
                mention_entity = self._get_or_create_entity(
                    mention_name, "account", "tweet_mention"
                )
                mention_entity.add_mention(tweet_id, content, timestamp, engagement)
                found_entities[mention_entity.name] = mention_entity

                self._add_relation(author_entity.name, mention_entity.name, "mentions")

        tags = _parse_list_value(tweet.get("tags", []))
        for tag in tags:
            if tag:
                tag_entity = self._get_or_create_entity(
                    tag.lstrip("#"), "hashtag", "tweet_hashtag"
                )
                tag_entity.add_mention(tweet_id, content, timestamp, engagement)
                found_entities[tag_entity.name] = tag_entity

                self._add_relation(author_entity.name, tag_entity.name, "posts_about")

        content_lower = content.lower()
        for org_name, entity_type in ORGANIZATIONS.items():
            if org_name.lower() in content_lower:
                org_entity = self._get_or_create_entity(org_name, entity_type, "named_entity")
                org_entity.add_mention(tweet_id, content, timestamp, engagement)
                found_entities[org_entity.name] = org_entity

                self._add_relation(author_entity.name, org_entity.name, "mentions")

        for asset_name, entity_type in ASSETS.items():
            if asset_name.lower() in content_lower:
                asset_entity = self._get_or_create_entity(asset_name, entity_type, "asset")
                asset_entity.add_mention(tweet_id, content, timestamp, engagement)
                found_entities[asset_entity.name] = asset_entity

                self._add_relation(author_entity.name, asset_entity.name, "discusses")

        for event_kw, entity_type in EVENT_KEYWORDS.items():
            if event_kw.lower() in content_lower:
                event_entity = self._get_or_create_entity(event_kw, entity_type, "event_keyword")
                event_entity.add_mention(tweet_id, content, timestamp, engagement)
                found_entities[event_entity.name] = event_entity

                self._add_relation(author_entity.name, event_entity.name, "reports")

        entity_names = list(found_entities.keys())
        for i, name1 in enumerate(entity_names):
            for name2 in entity_names[i+1:]:
                if name1 != name2:
                    self._add_relation(name1, name2, "co_occurs")

        return found_entities

    def _get_or_create_entity(self, name: str, entity_type: str, source: str) -> Entity:
        """获取或创建实体"""
        key = f"{entity_type}:{name}"
        if key not in self.entities:
            self.entities[key] = Entity(name, entity_type, source)
        return self.entities[key]

    def _add_relation(self, source: str, target: str, relation_type: str):
        """添加关系"""
        if source == target:
            return
        key = (source, target, relation_type)
        if key not in self.relations:
            self.relations[key] = Relation(source, target, relation_type)
        else:
            self.relations[key].weight += 1

    def _calc_engagement(self, tweet: dict) -> int:
        """计算互动量"""
        likes = tweet.get("likes", 0)
        retweets = tweet.get("retweets", 0)
        replies = tweet.get("replies", 0)

        def parse_count(val):
            if not val:
                return 0
            if isinstance(val, int):
                return val
            val = str(val).replace(",", "").strip()
            if val.endswith("K"):
                return int(float(val[:-1]) * 1000)
            elif val.endswith("M"):
                return int(float(val[:-1]) * 1000000)
            try:
                return int(val)
            except ValueError:
                return 0

        return parse_count(likes) + parse_count(retweets) + parse_count(replies)

    def get_all_entities(self) -> Dict[str, Entity]:
        return self.entities

    def get_all_relations(self) -> List[Relation]:
        return list(self.relations.values())


class ObsidianGenerator:
    """Obsidian Markdown 生成器"""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.entities_dir = os.path.join(output_dir, "entities")
        self.tweets_dir = os.path.join(output_dir, "tweets")
        self.index_file = os.path.join(output_dir, "情报图谱.md")
        self.graph_file = os.path.join(output_dir, "关系图谱.json")

        os.makedirs(self.entities_dir, exist_ok=True)
        os.makedirs(self.tweets_dir, exist_ok=True)

    def generate(self, entities: Dict[str, Entity], relations: List[Relation],
                tweets: List[dict], query: str = ""):
        """生成完整的 Obsidian 知识库"""

        self._generate_entity_notes(entities, relations)
        self._generate_tweet_notes(tweets, entities)
        self._generate_index(entities, relations, query)
        self._generate_graph_json(entities, relations)

        return {
            "output_dir": self.output_dir,
            "entity_count": len(entities),
            "relation_count": len(relations),
            "tweet_count": len(tweets),
        }

    def _sanitize_filename(self, name: str) -> str:
        """清理文件名"""
        invalid_chars = r'[<>:"/\\|?*#\[\]]'
        clean_name = re.sub(invalid_chars, '_', str(name)).strip()
        return clean_name or "unknown"

    def _entity_link(self, name: str) -> str:
        """生成稳定的 Obsidian 实体链接。"""
        filename = self._sanitize_filename(name)
        return f"[[entities/{filename}|{name}]]"

    def _mermaid_id(self, name: str) -> str:
        """生成 Mermaid 可解析且稳定的节点 ID。"""
        digest = hashlib.md5(str(name).encode("utf-8")).hexdigest()[:10]
        return f"n_{digest}"

    def _mermaid_label(self, name: str) -> str:
        """转义 Mermaid 节点标签。"""
        return str(name).replace('"', '\\"')

    def _generate_entity_notes(self, entities: Dict[str, Entity], relations: List[Relation]):
        """为每个实体生成 Markdown 笔记"""

        relation_map = defaultdict(list)
        for r in relations:
            relation_map[r.source].append(r)

        for key, entity in entities.items():
            filename = self._sanitize_filename(entity.name) + ".md"
            filepath = os.path.join(self.entities_dir, filename)

            lines = []

            lines.append("---")
            lines.append(f"type: entity")
            lines.append(f"entity_type: {entity.entity_type}")
            lines.append(f"entity_type_label: {ENTITY_TYPES.get(entity.entity_type, entity.entity_type)}")
            lines.append(f"mention_count: {entity.mention_count}")
            lines.append(f"total_engagement: {entity.total_engagement}")
            lines.append(f"first_seen: {entity.first_seen}")
            lines.append(f"last_seen: {entity.last_seen}")
            lines.append(f"tags:")
            lines.append(f"  - entity")
            lines.append(f"  - {entity.entity_type}")
            lines.append("---")
            lines.append("")

            lines.append(f"# {entity.name}")
            lines.append("")

            type_emoji = {
                "person": "👤",
                "organization": "🏛️",
                "location": "📍",
                "event": "⚡",
                "asset": "💰",
                "hashtag": "🏷️",
                "account": "🐦",
                "keyword": "🔑",
            }
            emoji = type_emoji.get(entity.entity_type, "📌")
            lines.append(f"**类型**: {emoji} {ENTITY_TYPES.get(entity.entity_type, entity.entity_type)}")
            lines.append(f"**提及次数**: {entity.mention_count}")
            lines.append(f"**总互动量**: {entity.total_engagement:,}")
            lines.append("")

            entity_relations = relation_map.get(entity.name, [])
            if entity_relations:
                lines.append("## 关联实体")
                lines.append("")
                for r in entity_relations[:20]:
                    target_link = self._entity_link(r.target)
                    relation_label = self._format_relation_type(r.relation_type)
                    lines.append(f"- {relation_label} → {target_link} (x{r.weight})")
                lines.append("")

            if entity.mentions:
                lines.append("## 相关推文")
                lines.append("")
                for mention in entity.mentions[:10]:
                    tweet_link = f"[[tweets/{mention['tweet_id'][:12]}|推文]]"
                    timestamp = mention.get('timestamp', '')[:10] if mention.get('timestamp') else ''
                    lines.append(f"- {timestamp} {tweet_link}: {mention['content'][:80]}...")
                lines.append("")

            content = "\n".join(lines)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

    def _generate_tweet_notes(self, tweets: List[dict], entities: Dict[str, Entity]):
        """为每条推文生成笔记"""

        for tweet in tweets:
            tweet_id = tweet.get("tweet_id", "")
            if not tweet_id:
                tweet_id = hashlib.md5(tweet.get("content", "").encode()).hexdigest()[:12]

            filename = f"{tweet_id[:12]}.md"
            filepath = os.path.join(self.tweets_dir, filename)

            lines = []

            lines.append("---")
            lines.append(f"type: tweet")
            lines.append(f"tweet_id: {tweet_id}")
            lines.append(f"author: {tweet.get('handle', '')}")
            lines.append(f"timestamp: {tweet.get('timestamp', '')}")
            lines.append(f"likes: {tweet.get('likes', 0)}")
            lines.append(f"retweets: {tweet.get('retweets', 0)}")
            lines.append(f"verified: {tweet.get('verified', False)}")
            lines.append(f"tags:")
            lines.append(f"  - tweet")
            lines.append("---")
            lines.append("")

            handle = tweet.get("handle", "")
            if handle:
                lines.append(f"**作者**: {self._entity_link(handle.lstrip('@'))}")
            lines.append(f"**时间**: {tweet.get('timestamp', '')}")
            lines.append(f"**互动**: 👍{tweet.get('likes', 0)} 🔄{tweet.get('retweets', 0)} 💬{tweet.get('replies', 0)}")
            lines.append("")

            lines.append("## 内容")
            lines.append("")
            lines.append(tweet.get("content", ""))
            lines.append("")

            tags = _parse_list_value(tweet.get("tags", []))
            if tags:
                lines.append("## 话题标签")
                lines.append("")
                lines.append(" ".join([self._entity_link(t.lstrip('#')) for t in tags]))
                lines.append("")

            mentions = _parse_list_value(tweet.get("mentions", []))
            if mentions:
                lines.append("## 提及")
                lines.append("")
                lines.append(" ".join([self._entity_link(m.lstrip('@')) for m in mentions]))
                lines.append("")

            content = "\n".join(lines)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

    def _generate_index(self, entities: Dict[str, Entity], relations: List[Relation],
                       query: str):
        """生成索引页面"""

        lines = []

        lines.append("---")
        lines.append(f"type: index")
        lines.append(f"generated: {datetime.now().isoformat()}")
        lines.append(f"query: {query}")
        lines.append(f"entity_count: {len(entities)}")
        lines.append(f"relation_count: {len(relations)}")
        lines.append(f"tags:")
        lines.append(f"  - index")
        lines.append(f"  - knowledge_graph")
        lines.append("---")
        lines.append("")

        lines.append("# 📊 情报关系图谱")
        lines.append("")
        lines.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"> 查询: {query}")
        lines.append(f"> 实体数: {len(entities)} | 关系数: {len(relations)}")
        lines.append("")

        entities_by_type = defaultdict(list)
        for key, entity in entities.items():
            entities_by_type[entity.entity_type].append(entity)

        type_order = ["account", "organization", "location", "asset", "event", "hashtag", "keyword"]
        type_emoji = {
            "account": "🐦",
            "organization": "🏛️",
            "location": "📍",
            "asset": "💰",
            "event": "⚡",
            "hashtag": "🏷️",
            "keyword": "🔑",
        }

        for entity_type in type_order:
            if entity_type in entities_by_type:
                emoji = type_emoji.get(entity_type, "📌")
                type_label = ENTITY_TYPES.get(entity_type, entity_type)
                entities_list = sorted(entities_by_type[entity_type],
                                      key=lambda e: e.mention_count, reverse=True)

                lines.append(f"## {emoji} {type_label} ({len(entities_list)})")
                lines.append("")

                for entity in entities_list[:15]:
                    link = self._entity_link(entity.name)
                    lines.append(f"- {link} (提及 {entity.mention_count} 次, 互动 {entity.total_engagement:,})")
                lines.append("")

        lines.append("## 🔗 关系网络")
        lines.append("")
        lines.append("```mermaid")
        lines.append("graph LR")

        sorted_relations = sorted(relations, key=lambda r: r.weight, reverse=True)[:30]
        for r in sorted_relations:
            source = self._mermaid_id(r.source)
            target = self._mermaid_id(r.target)
            source_label = self._mermaid_label(r.source)
            target_label = self._mermaid_label(r.target)
            label = self._format_relation_type(r.relation_type)
            lines.append(f"    {source}[\"{source_label}\"] -->|{label}| {target}[\"{target_label}\"]")

        lines.append("```")
        lines.append("")

        lines.append("## 📈 高互动实体")
        lines.append("")
        top_entities = sorted(entities.values(), key=lambda e: e.total_engagement, reverse=True)[:10]
        for i, entity in enumerate(top_entities, 1):
            link = self._entity_link(entity.name)
            lines.append(f"{i}. {link} - 互动量 {entity.total_engagement:,}")
        lines.append("")

        content = "\n".join(lines)
        with open(self.index_file, 'w', encoding='utf-8') as f:
            f.write(content)

    def _generate_graph_json(self, entities: Dict[str, Entity], relations: List[Relation]):
        """生成关系图谱 JSON（供 Obsidian 插件使用）"""

        nodes = []
        for key, entity in entities.items():
            nodes.append({
                "id": entity.name,
                "type": entity.entity_type,
                "mention_count": entity.mention_count,
                "engagement": entity.total_engagement,
            })

        edges = []
        for r in relations:
            edges.append({
                "source": r.source,
                "target": r.target,
                "type": r.relation_type,
                "weight": r.weight,
            })

        graph_data = {
            "nodes": nodes,
            "edges": edges,
            "generated": datetime.now().isoformat(),
        }

        with open(self.graph_file, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)

    def _format_relation_type(self, relation_type: str) -> str:
        """格式化关系类型"""
        relation_labels = {
            "mentions": "提及",
            "posts_about": "发布",
            "discusses": "讨论",
            "reports": "报道",
            "co_occurs": "共现",
        }
        return relation_labels.get(relation_type, relation_type)


def generate_obsidian_graph(tweets: Optional[List[dict]] = None,
                           output_dir: str = "./obsidian_vault/",
                           query: str = "",
                           input_dir: Optional[str] = None) -> dict:
    """
    从推文列表生成 Obsidian 关系图谱

    Args:
        tweets: 推文列表（scraper 输出格式）。为空时可配合 input_dir 读取历史 CSV
        output_dir: Obsidian vault 输出目录
        query: 查询关键词（用于索引页）
        input_dir: 历史抓取 CSV 目录

    Returns:
        {
            "output_dir": str,
            "entity_count": int,
            "relation_count": int,
            "tweet_count": int,
        }
    """
    if tweets is None and input_dir:
        tweets = load_tweets_from_csv_dir(input_dir)
        print(f"  已从 {input_dir} 读取历史推文 {len(tweets)} 条")

    tweets = [_normalize_tweet(tweet) for tweet in (tweets or [])]

    if not tweets:
        print("  无推文数据，跳过图谱生成")
        return {"output_dir": output_dir, "entity_count": 0, "relation_count": 0, "tweet_count": 0}

    print(f"\n{'=' * 60}")
    print("  Obsidian 关系图谱生成器")
    print(f"{'=' * 60}")

    extractor = EntityExtractor()

    print(f"  正在提取实体...")
    for tweet in tweets:
        extractor.extract_from_tweet(tweet)

    entities = extractor.get_all_entities()
    relations = extractor.get_all_relations()

    print(f"  提取到 {len(entities)} 个实体, {len(relations)} 条关系")

    generator = ObsidianGenerator(output_dir)
    result = generator.generate(entities, relations, tweets, query)

    print(f"\n  ✓ 图谱已生成:")
    print(f"    - 输出目录: {output_dir}")
    print(f"    - 实体笔记: {result['entity_count']} 个")
    print(f"    - 关系数量: {result['relation_count']} 条")
    print(f"    - 推文笔记: {result['tweet_count']} 条")
    print(f"    - 索引文件: {os.path.join(output_dir, '情报图谱.md')}")
    print(f"{'=' * 60}\n")

    return result


def print_graph_summary(entities: Dict[str, Entity], relations: List[Relation]):
    """打印图谱摘要"""
    print("\n" + "=" * 60)
    print("  实体关系图谱摘要")
    print("=" * 60)

    entities_by_type = defaultdict(list)
    for key, entity in entities.items():
        entities_by_type[entity.entity_type].append(entity)

    for entity_type, entity_list in entities_by_type.items():
        type_label = ENTITY_TYPES.get(entity_type, entity_type)
        print(f"\n  {type_label} ({len(entity_list)} 个):")
        for entity in sorted(entity_list, key=lambda e: e.mention_count, reverse=True)[:5]:
            print(f"    - {entity.name}: {entity.mention_count} 次提及")

    print(f"\n  关系类型分布:")
    relation_types = defaultdict(int)
    for r in relations:
        relation_types[r.relation_type] += 1
    for rt, count in sorted(relation_types.items(), key=lambda x: x[1], reverse=True):
        print(f"    - {rt}: {count} 条")


if __name__ == "__main__":
    test_tweets = [
        {
            "tweet_id": "t1",
            "handle": "@Reuters",
            "content": "BREAKING: OPEC+ agrees to cut production by 2.2 million barrels per day. Saudi Arabia and Russia lead the initiative amid Hormuz tensions.",
            "timestamp": datetime.now().isoformat(),
            "likes": "5.2K",
            "retweets": "3.1K",
            "replies": 450,
            "verified": True,
            "tags": ["#OPEC", "#Oil"],
            "mentions": ["@JavierBlas"],
        },
        {
            "tweet_id": "t2",
            "handle": "@JavierBlas",
            "content": "Saudi voluntary cut of 1 million bpd is significant. Oil prices likely to surge. WTI and Brent both reacting to supply disruption fears.",
            "timestamp": datetime.now().isoformat(),
            "likes": "2.1K",
            "retweets": "1.5K",
            "replies": 200,
            "verified": True,
            "tags": ["#Oil", "#Energy"],
            "mentions": [],
        },
        {
            "tweet_id": "t3",
            "handle": "@federalreserve",
            "content": "The Federal Reserve monitors inflation closely. Rate decisions will depend on economic data including jobs and CPI.",
            "timestamp": datetime.now().isoformat(),
            "likes": "8.5K",
            "retweets": "4.2K",
            "replies": 1200,
            "verified": True,
            "tags": ["#Fed", "#Economy"],
            "mentions": [],
        },
    ]

    print("Obsidian 关系图谱生成器 - 测试\n")
    result = generate_obsidian_graph(
        test_tweets,
        output_dir="./test_obsidian_vault/",
        query="油价会涨吗？"
    )

    print(f"\n生成结果: {result}")
