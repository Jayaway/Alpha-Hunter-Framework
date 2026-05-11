# -*- coding: utf-8 -*-
"""
X 实时情报系统 - 精简数据清洗引擎（3层核心）
================================================
从6层精简到3层核心，保留最关键的能力：

核心流水线：
  ① 时效 + 来源可信度（合并计算）
  ② 交叉验证（多源确认）
  ③ 噪音过滤（情绪/垃圾/二手）

优化点：
  - 去除冗余的SimHash聚类（计算重、效果有限）
  - 简化情绪噪音检测（正则匹配足够）
  - 保留最重要的多源交叉验证
  - 目标：清洗时间从 O(n²) 降到 O(n)
"""

import re
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from deepalpha.x_intel_rules import S_LEVEL, A_LEVEL, B_LEVEL, LEADERS_GROUP, JOURNALIST_SCOOP_GROUP


# ============================================================
# 1. 推文数据模型
# ============================================================

@dataclass
class CleanedTweet:
    """清洗后的推文"""
    tweet_id: str
    username: str
    content: str
    timestamp: str

    likes: int = 0
    retweets: int = 0
    replies: int = 0
    is_verified: bool = False

    source_score: float = 5.0
    timeliness_score: float = 0.5
    cross_verify_score: float = 0.0
    noise_score: float = 0.0

    is_hearsay: bool = False
    direction: Optional[str] = None
    final_score: float = 0.0
    verdict: str = "low_value"

    tags: List[str] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict) -> 'CleanedTweet':
        """从原始数据创建"""
        return cls(
            tweet_id=raw.get('id', raw.get('tweet_id', '')),
            username=raw.get('username', raw.get('handle', '')),
            content=raw.get('text', raw.get('content', '')),
            timestamp=raw.get('created_at', raw.get('timestamp', '')),
            likes=cls._parse_count(raw.get('like_count', raw.get('likes', 0))),
            retweets=cls._parse_count(raw.get('retweet_count', raw.get('retweets', 0))),
            replies=cls._parse_count(raw.get('reply_count', raw.get('replies', 0))),
            is_verified=raw.get('is_verified', raw.get('verified', False)),
        )

    @staticmethod
    def _parse_count(val) -> int:
        if isinstance(val, int):
            return val
        if isinstance(val, str):
            val = val.strip()
            if not val:
                return 0
            multipliers = {'K': 1000, 'M': 1000000}
            for suffix, mult in multipliers.items():
                if suffix in val.upper():
                    try:
                        return int(float(val.upper().replace(suffix, '')) * mult)
                    except:
                        return 0
            try:
                return int(val.replace(',', ''))
            except:
                return 0
        return 0


# ============================================================
# 2. 第一层：时效 + 来源可信度评分
# ============================================================

# 高可信来源
OFFICIAL_ACCOUNTS = {
    "@realDonaldTrump", "@VladimirPutin", "@KSAmofaEN",
    "@RTErdogan", "@federalreserve", "@ecb", "@WhiteHouse",
    "@PentagonPressSec", "@IDF", "@DefenceU",
}

WIRE_SERVICES = {
    "@Reuters", "@Bloomberg", "@WSJ", "@CNBC",
    "@FT", "@AP", "@NBCNews", "@BBCBreaking",
}

一线记者 = {
    "@RichardEngel", "@samdagher", "@JavierBlas",
    "@JKempEnergy", "@OilSheppard", "@JackDetsch",
}

STALE_PATTERNS = [
    r'\b20[12]\d\b', r'\blast\s+year\b', r'\bpreviously\b',
    r'\bearlier\s+this\b', r'\baccording\s+to.*\d{4}\b',
]

FRESH_PATTERNS = [
    r'\btoday\b', r'\bnow\b', r'\bbreaking\b', r'\bjust\s+in\b',
    r'\bdeveloping\b', r'\blive\b', r'\bimminent\b', r'\bhours?\s+ago\b',
    r'刚刚', r'突发', r'快讯', r'最新', r'分钟前',
]

EXTREME_NOISE_PATTERNS = [
    r'TO\s+\$\d{3,}\s*(NOW|SOON)', r'\d{4,}%\s*(GAIN|CRASH)',
    r'FOLLOW\s+ME', r'CLICK\s+HERE', r'DM\s+ME',
    r'FREE\s+SIGNAL', r'PREMIUM\s+GROUP',
]


def score_source_and_timeliness(tweet: CleanedTweet) -> Tuple[float, float]:
    """
    第一层：来源 + 时效评分（合并计算，更快）

    Returns:
        (source_score, timeliness_score)
    """
    username = tweet.username.lower() if tweet.username else ""

    # === 来源评分 (1-10) ===
    source_score = 5.0  # 默认

    if any(a.lower() in username for a in OFFICIAL_ACCOUNTS):
        source_score = 10.0
    elif any(a.lower() in username for a in WIRE_SERVICES):
        source_score = 9.0
    elif any(a.lower() in username for a in 一线记者):
        source_score = 8.5
    elif any(a.lower() in username for a in S_LEVEL):
        source_score = 7.5
    elif any(a.lower() in username for a in A_LEVEL):
        source_score = 6.5
    elif tweet.is_verified:
        source_score = 4.0

    # === 时效评分 (0-1) ===
    content = tweet.content.lower()
    is_stale = any(re.search(p, content, re.I) for p in STALE_PATTERNS)
    is_fresh = any(re.search(p, content, re.I) for p in FRESH_PATTERNS)

    if is_stale and not is_fresh:
        timeliness = 0.3
    elif is_fresh and not is_stale:
        timeliness = 0.9
    else:
        timeliness = 0.5

    tweet.source_score = source_score
    tweet.timeliness_score = timeliness
    tweet.tags.append(f"source:{source_score:.0f}")
    tweet.tags.append(f"time:{timeliness:.1f}")

    return source_score, timeliness


# ============================================================
# 3. 第二层：多源交叉验证
# ============================================================

def cross_verify_tweets(tweets: List[CleanedTweet]) -> Dict[str, float]:
    """
    第二层：多源交叉验证

    简化版：检查同一事件是否有多个独立来源确认

    策略：
      - 按内容关键词聚类（只取前3个关键词）
      - 计算每个聚类的来源多样性
      - 有多个来源 = 高可信度
    """
    clusters: Dict[str, List[CleanedTweet]] = {}

    for tweet in tweets:
        keywords = extract_event_keywords(tweet.content)
        if not keywords:
            continue

        key = "|".join(sorted(keywords[:2]))
        if key not in clusters:
            clusters[key] = []
        clusters[key].append(tweet)

    cluster_scores = {}

    for key, cluster in clusters.items():
        if len(cluster) < 2:
            cluster_scores[key] = 0.5
            continue

        sources = set()
        has_official = False
        has_wire = False
        has_journalist = False

        for t in cluster:
            username = t.username.lower()

            if any(a.lower() in username for a in OFFICIAL_ACCOUNTS):
                sources.add("official")
                has_official = True
            elif any(a.lower() in username for a in WIRE_SERVICES):
                sources.add("wire")
                has_wire = True
            elif any(a.lower() in username for a in 一线记者):
                sources.add("journalist")
                has_journalist = True
            else:
                sources.add("other")

        score = min(len(sources) * 2.0, 8.0)
        if has_official:
            score += 2.0
        if has_wire:
            score += 1.0

        cluster_scores[key] = min(score, 10.0)

    for tweet in tweets:
        keywords = extract_event_keywords(tweet.content)
        if keywords:
            key = "|".join(sorted(keywords[:2]))
            score = cluster_scores.get(key, 0.5)
            tweet.cross_verify_score = score

    return cluster_scores


def extract_event_keywords(content: str) -> List[str]:
    """提取事件关键词"""
    content = content.lower()

    keywords = []

    oil_keywords = ["opec", "crude", "sanction", "hormuz", "tanker", "inventory"]
    war_keywords = ["attack", "missile", "strike", "invasion", "ceasefire", "war"]
    macro_keywords = ["fed", "rate", "inflation", "tariff", "sanction"]

    for kw in oil_keywords:
        if kw in content:
            keywords.append(kw)

    for kw in war_keywords:
        if kw in content:
            keywords.append(kw)

    for kw in macro_keywords:
        if kw in content:
            keywords.append(kw)

    return keywords[:3]


# ============================================================
# 4. 第三层：噪音过滤
# ============================================================

HEARSAY_PATTERNS = [
    r'\bsomeone\s+says?\b', r'\brumors?\b', r'\bunconfirmed\b',
    r'\bhearing\s+(that|we\s+might)\b', r'\bsources?\s+(say|tell)\b',
    r'\ballegedly\b', r'\bspeculation\b',
    r'据说', r'传闻', r'据传', r'未经证实', r'可能', r'或许',
]

def filter_noise(tweet: CleanedTweet) -> float:
    """
    第三层：噪音过滤

    Returns:
        noise_score (0=干净, 1=纯噪音)
    """
    content = tweet.content
    if not content:
        return 0.0

    noise = 0.0

    alpha_chars = [c for c in content if c.isalpha()]
    if alpha_chars:
        upper_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
        if upper_ratio > 0.8 and len(alpha_chars) > 10:
            noise += 0.4
        elif upper_ratio > 0.6:
            noise += 0.2

    exclamation_count = content.count('!')
    if exclamation_count >= 5:
        noise += 0.3
    elif exclamation_count >= 3:
        noise += 0.15

    if any(re.search(p, content, re.I) for p in EXTREME_NOISE_PATTERNS):
        noise += 0.5

    is_hearsay = any(re.search(p, content, re.I) for p in HEARSAY_PATTERNS)
    tweet.is_hearsay = is_hearsay

    if is_hearsay:
        tweet.tags.append("hearsay")

    tweet.noise_score = min(noise, 1.0)
    return noise


# ============================================================
# 5. 方向判断
# ============================================================

DIRECTION_SIGNALS = {
    "利多原油": ["cut", "supply disruption", "blockade", "sanction", "attack", "strike", "hormuz"],
    "利空原油": ["production increase", "supply surge", "recession", "ceasefire", "SPR release"],
    "利多黄金": ["rate cut", "war", "conflict", "nuclear", "safe haven", "inflation"],
    "利空黄金": ["rate hike", "strong dollar", "peace deal"],
}

def detect_direction(tweet: CleanedTweet) -> Optional[str]:
    """检测市场方向"""
    content = tweet.content.lower()

    for direction, signals in DIRECTION_SIGNALS.items():
        if any(sig in content for sig in signals):
            return direction

    return None


# ============================================================
# 6. 综合评分 + 最终裁决
# ============================================================

def calculate_final_score(tweet: CleanedTweet) -> Tuple[float, str]:
    """
    计算最终评分和裁决

    权重：
      来源: 35%
      时效: 25%
      交叉验证: 25%
      噪音: -15%
    """
    source = tweet.source_score / 10.0
    timeliness = tweet.timeliness_score
    cross = tweet.cross_verify_score / 10.0
    noise_penalty = tweet.noise_score * 0.15

    score = (
        source * 0.35 +
        timeliness * 0.25 +
        cross * 0.25 -
        noise_penalty
    ) * 10

    if tweet.is_hearsay:
        score *= 0.7

    score = max(0.0, min(10.0, score))
    tweet.final_score = round(score, 1)

    if score >= 7.0:
        verdict = "actionable"
    elif score >= 5.0:
        verdict = "noteworthy"
    elif score >= 3.0:
        verdict = "low_value"
    else:
        verdict = "discard"

    tweet.verdict = verdict
    tweet.tags.append(f"verdict:{verdict}")
    tweet.tags.append(f"final:{score:.1f}")

    return score, verdict


# ============================================================
# 7. 完整清洗流水线
# ============================================================

def clean_tweets(raw_tweets: List[dict], verbose: bool = False) -> List[CleanedTweet]:
    """
    精简3层清洗流水线

    性能目标：
      - 时间复杂度：O(n)
      - 单次清洗 < 10ms/条

    Args:
        raw_tweets: 原始推文列表
        verbose: 是否打印统计

    Returns:
        清洗后的推文列表（按评分降序）
    """
    if not raw_tweets:
        return []

    cleaned = []

    for raw in raw_tweets:
        try:
            tweet = CleanedTweet.from_raw(raw)

            score_source_and_timeliness(tweet)

            filter_noise(tweet)

            direction = detect_direction(tweet)
            tweet.direction = direction

            calculate_final_score(tweet)

            if tweet.verdict != "discard":
                cleaned.append(tweet)

        except Exception as e:
            continue

    cross_verify_tweets(cleaned)

    for tweet in cleaned:
        calculate_final_score(tweet)

    cleaned.sort(key=lambda t: t.final_score, reverse=True)

    if verbose:
        stats = {
            "input": len(raw_tweets),
            "output": len(cleaned),
            "actionable": sum(1 for t in cleaned if t.verdict == "actionable"),
            "noteworthy": sum(1 for t in cleaned if t.verdict == "noteworthy"),
            "low_value": sum(1 for t in cleaned if t.verdict == "low_value"),
        }

        print("\n  3层数据清洗报告")
        print("=" * 60)
        print(f"  输入: {stats['input']} 条 → 输出: {stats['output']} 条")
        print(f"  actionable: {stats['actionable']}")
        print(f"  noteworthy: {stats['noteworthy']}")
        print(f"  low_value: {stats['low_value']}")

        if cleaned:
            print("\n  Top 3:")
            for i, t in enumerate(cleaned[:3], 1):
                print(f"    {i}. [{t.verdict}] {t.final_score}分 @{t.username}")
                print(f"       {t.content[:60]}...")

    return cleaned


# ============================================================
# 8. 快速过滤（用于实时场景）
# ============================================================

def quick_filter(raw_tweets: List[dict], min_score: float = 5.0) -> List[dict]:
    """
    快速过滤（跳过复杂计算）

    适用于实时场景，要求 < 5ms/条

    策略：
      - 只检查来源和时效
      - 不做交叉验证
      - 不做复杂情绪分析
    """
    results = []

    for raw in raw_tweets:
        username = raw.get('username', raw.get('handle', '')).lower()
        content = raw.get('text', raw.get('content', ''))

        score = 5.0

        if any(a.lower() in username for a in OFFICIAL_ACCOUNTS):
            score = 9.0
        elif any(a.lower() in username for a in WIRE_SERVICES):
            score = 8.0
        elif any(a.lower() in username for a in S_LEVEL):
            score = 7.0

        is_fresh = any(re.search(p, content, re.I) for p in FRESH_PATTERNS)
        is_stale = any(re.search(p, content, re.I) for p in STALE_PATTERNS)

        if is_fresh:
            score += 0.5
        elif is_stale:
            score -= 1.0

        if score >= min_score:
            raw['_quick_score'] = score
            results.append(raw)

    return results


# ============================================================
# 9. 测试
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  精简数据清洗引擎 - 测试")
    print("=" * 60)

    test_data = [
        {
            "username": "@Reuters",
            "content": "BREAKING: OPEC+ agrees to cut production by 2.2 million barrels per day",
            "likes": 5000,
            "is_verified": True,
        },
        {
            "username": "@JavierBlas",
            "content": "Just in: Saudi Arabia announces voluntary cut of 1 million bpd",
            "likes": 3000,
            "is_verified": True,
        },
        {
            "username": "@oil_trader",
            "content": "OIL TO $200!!! BUY NOW!!! 🚀🚀🚀 FOLLOW ME!!!",
            "likes": 5,
            "is_verified": False,
        },
        {
            "username": "@random_user",
            "content": "Good morning everyone",
            "likes": 2,
            "is_verified": False,
        },
    ]

    print("\n  完整清洗:")
    cleaned = clean_tweets(test_data, verbose=True)

    print("\n  快速过滤:")
    filtered = quick_filter(test_data, min_score=6.0)
    print(f"  过滤后: {len(filtered)} 条")
