# -*- coding: utf-8 -*-
"""
X 实时情报系统 - 6层数据清洗引擎
================================================
对抓取后的原始推文数据进行逐层清洗，从海量噪音中提取高价值情报。

清洗流水线：
  原始数据 → ①去重 → ②来源可信度 → ③时效 → ④情绪噪音 → ⑤二手转述 → ⑥多源交叉验证 → 清洁情报

依赖：x_intel_rules.py（账号分级数据）
"""

import re
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from deepalpha.x_intel_rules import (
    S_LEVEL, A_LEVEL, B_LEVEL, C_LEVEL,
    LEADERS_GROUP, JOURNALIST_SCOOP_GROUP,
)


# ============================================================
# 0. 数据模型
# ============================================================

class Tweet:
    """推文数据模型"""
    __slots__ = [
        "tweet_id", "username", "content", "timestamp",
        "likes", "retweets", "replies", "impressions",
        "is_verified", "is_retweet", "has_media",
        "media_urls", "links", "hashtags", "mentions",
        # 清洗后新增字段
        "_dedup_cluster_id", "_source_score", "_timeliness_score",
        "_sentiment_noise_score", "_hearsay_flag", "_cross_verify_score",
        "_final_score", "_final_verdict", "_clean_tags",
    ]

    def __init__(self, **kwargs):
        for slot in self.__slots__:
            setattr(self, slot, kwargs.get(slot))
        # 初始化清洗标签
        if not hasattr(self, '_clean_tags') or self._clean_tags is None:
            self._clean_tags = []

    def to_dict(self) -> dict:
        return {slot: getattr(self, slot) for slot in self.__slots__}

    def __repr__(self):
        return f"<Tweet @{self.username}: {self.content[:60]}...>"


# ============================================================
# ① 去重清洗（最重要）
# ============================================================
"""
大量账号会转同一条消息。例如 Reuters 发一条，100个账号转载，
不能当100条利多。

聚类维度：
  - 正文相似度（SimHash / 编辑距离）
  - 发布时间接近（±30分钟内）
  - 同一链接
  - 同一图片/视频
  - 同一事件词

保留源头账号（最早发布 + 最高可信度）。
"""

# 事件关键词（用于聚类）
EVENT_KEYWORDS = [
    # 原油事件
    "opec", "cut", "production", "inventory", "eia", "api",
    "hormuz", "strait", "tanker", "sanction", "embargo",
    # 地缘事件
    "ceasefire", "strike", "missile", "invasion", "attack",
    "nuclear", "mobilization", "escalation",
    # 宏观事件
    "rate cut", "rate hike", "fed", "ecb", "cpi", "pce",
    "nonfarm", "payroll", "recession",
    # 通用突发
    "breaking", "just in", "exclusive", "developing",
    "confirmed", "official", "announced",
]

# SimHash 简化实现（基于字符n-gram特征哈希）
def _simhash(text: str, hash_bits: int = 64) -> int:
    """计算文本的SimHash指纹"""
    text = text.lower()
    # 提取3-gram特征
    features = [text[i:i+3] for i in range(len(text) - 2)]
    if not features:
        return 0

    v = [0] * hash_bits
    for f in features:
        h = int(hashlib.md5(f.encode()).hexdigest(), 16)
        for i in range(hash_bits):
            if h & (1 << i):
                v[i] += 1
            else:
                v[i] -= 1

    fingerprint = 0
    for i in range(hash_bits):
        if v[i] > 0:
            fingerprint |= (1 << i)
    return fingerprint


def _hamming_distance(h1: int, h2: int) -> int:
    """计算两个哈希的汉明距离"""
    return bin(h1 ^ h2).count('1')


def _extract_event_words(text: str) -> set:
    """提取文本中的事件关键词"""
    text_lower = text.lower()
    found = set()
    for kw in EVENT_KEYWORDS:
        if kw in text_lower:
            found.add(kw)
    return found


def _extract_links(text: str) -> set:
    """提取URL链接"""
    return set(re.findall(r'https?://\S+', text))


def deduplicate(tweets: list) -> list:
    """
    第①层：去重清洗

    聚类逻辑：
    1. 同一链接 → 直接聚类
    2. SimHash相似度 + 时间接近 + 事件词重叠 → 聚类
    3. 每个聚类只保留源头（最早发布 + 最高可信度）

    Returns: 去重后的推文列表
    """
    if not tweets:
        return []

    # --- Phase 1: 按链接聚类 ---
    link_clusters = defaultdict(list)
    no_link_tweets = []

    for t in tweets:
        links = _extract_links(t.content)
        if links:
            # 用第一个链接作为聚类key
            key = min(links)  # 取最小URL作为规范key
            link_clusters[key].append(t)
        else:
            no_link_tweets.append(t)

    # --- Phase 2: 按SimHash + 时间 + 事件词聚类（无链接的推文）---
    SIMHASH_THRESHOLD = 8      # 汉明距离阈值（越小越严格）
    TIME_WINDOW_MINUTES = 30   # 时间窗口

    clusters = []
    assigned = [False] * len(no_link_tweets)

    for i in range(len(no_link_tweets)):
        if assigned[i]:
            continue
        cluster = [no_link_tweets[i]]
        assigned[i] = True

        t_i = no_link_tweets[i]
        hash_i = _simhash(t_i.content)
        time_i = t_i.timestamp
        events_i = _extract_event_words(t_i.content)

        for j in range(i + 1, len(no_link_tweets)):
            if assigned[j]:
                continue
            t_j = no_link_tweets[j]

            # 时间检查
            if time_i and t_j.timestamp:
                try:
                    dt_i = datetime.fromisoformat(str(time_i).replace('Z', '+00:00'))
                    dt_j = datetime.fromisoformat(str(t_j.timestamp).replace('Z', '+00:00'))
                    if abs((dt_i - dt_j).total_seconds()) > TIME_WINDOW_MINUTES * 60:
                        continue
                except (ValueError, TypeError):
                    pass

            # SimHash检查
            hash_j = _simhash(t_j.content)
            if _hamming_distance(hash_i, hash_j) > SIMHASH_THRESHOLD:
                continue

            # 事件词重叠检查（至少1个共同事件词）
            events_j = _extract_event_words(t_j.content)
            if events_i and events_j and not (events_i & events_j):
                continue

            cluster.append(t_j)
            assigned[j] = True

        clusters.append(cluster)

    # --- Phase 3: 每个聚类保留源头 ---
    def pick_source(cluster: list) -> Tweet:
        """选择源头推文：最早发布 + 最高可信度"""
        # 按时间排序（最早的优先）
        def sort_key(t):
            try:
                dt = datetime.fromisoformat(str(t.timestamp).replace('Z', '+00:00'))
                return dt
            except (ValueError, TypeError):
                return datetime.max

        cluster_sorted = sorted(cluster, key=sort_key)
        # 如果时间相同，按可信度排序（后面第②层会打分，这里先用简单规则）
        return cluster_sorted[0]

    result = []
    for cluster in link_clusters.values():
        source = pick_source(cluster)
        source._dedup_cluster_id = f"link_{hashlib.md5(str(id(cluster)).encode()).hexdigest()[:8]}"
        source._clean_tags = getattr(source, '_clean_tags', []) + ["dedup:source"]
        result.append(source)
        # 标记其他为重复
        for t in cluster:
            if t is not source:
                t._dedup_cluster_id = source._dedup_cluster_id
                t._clean_tags = getattr(t, '_clean_tags', []) + ["dedup:duplicate"]

    for cluster in clusters:
        source = pick_source(cluster)
        source._dedup_cluster_id = f"simhash_{hashlib.md5(str(id(cluster)).encode()).hexdigest()[:8]}"
        source._clean_tags = getattr(source, '_clean_tags', []) + ["dedup:source"]
        result.append(source)
        for t in cluster:
            if t is not source:
                t._dedup_cluster_id = source._dedup_cluster_id
                t._clean_tags = getattr(t, '_clean_tags', []) + ["dedup:duplicate"]

    return result


# ============================================================
# ② 来源可信度评分
# ============================================================
"""
给每条消息打来源分：
  官方账号 = 10
  Reuters/Bloomberg = 9
  一线记者 = 8
  专业分析师 = 6
  普通用户 = 3
  匿名号 = 1
"""

# 官方账号（政府/央行/国际组织/军队）
OFFICIAL_ACCOUNTS = set(LEADERS_GROUP + [
    "@federalreserve", "@ecb", "@IMFNews", "@WhiteHouse",
    "@PentagonPressSec", "@NATO", "@UN",
    "@IDF", "@DefenceU", "@KSAmofaEN",
])

# 顶级新闻机构
WIRE_SERVICES = {
    "@Reuters", "@Bloomberg", "@WSJ", "@FT", "@FinancialTimes",
    "@CNBC", "@AP", "@BBCBreaking", "@NBCNews",
}

# 一线记者（从S/A级记者账号中提取）
FRONTLINE_JOURNALISTS = set(JOURNALIST_SCOOP_GROUP) | {
    "@RichardEngel", "@samdagher", "@ChristopherJM", "@yarotrof",
    "@JackDetsch", "@SangerNYT", "@AlexCrawfordSky", "@markmackinnon",
    "@JavierBlas", "@JKempEnergy", "@OilSheppard",
}

# 专业分析师/机构
ANALYST_ACCOUNTS = set(S_LEVEL + A_LEVEL) - OFFICIAL_ACCOUNTS - WIRE_SERVICES - FRONTLINE_JOURNALISTS


def score_source(tweet: Tweet) -> int:
    """
    第②层：来源可信度评分

    Returns: 1-10 分
    """
    username = tweet.username.lower() if tweet.username else ""

    # 官方账号 = 10
    if username in {a.lower() for a in OFFICIAL_ACCOUNTS}:
        return 10

    # 顶级通讯社 = 9
    if username in {a.lower() for a in WIRE_SERVICES}:
        return 9

    # 一线记者 = 8
    if username in {a.lower() for a in FRONTLINE_JOURNALISTS}:
        return 8

    # S级账号 = 7
    if username in {a.lower() for a in S_LEVEL}:
        return 7

    # A级分析师 = 6
    if username in {a.lower() for a in ANALYST_ACCOUNTS}:
        return 6

    # B级账号 = 5
    if username in {a.lower() for a in B_LEVEL}:
        return 5

    # 蓝V认证 = 4
    if tweet.is_verified:
        return 4

    # 普通用户 = 3
    # 匿名号检测
    if tweet.username:
        # 检测匿名特征：纯数字、随机字母、无头像等
        un = tweet.username.lower()
        if re.match(r'^[a-z]{0,2}\d{4,}$', un):  # 如 x9928374
            return 1
        if 'anon' in un or 'breaking' in un.lower() and len(un) > 15:
            return 1

    return 3


def apply_source_scoring(tweets: list) -> list:
    """对推文列表应用来源可信度评分"""
    for t in tweets:
        t._source_score = score_source(t)
        t._clean_tags = getattr(t, '_clean_tags', []) + [f"source:{t._source_score}"]
    return tweets


# ============================================================
# ③ 时效清洗（旧闻翻炒）
# ============================================================
"""
很多消息是2025年旧新闻今天又被转发，会误导价格判断。

识别正文时间词：
  today, now, breaking → 新鲜
  last year, 2024, previously announced → 旧闻

如果是旧闻，降权。
"""

# 旧闻指示词（出现则判定为旧闻）
STALE_INDICATORS = [
    r'\b20[12]\d\b',                    # 具体年份 201x, 202x
    r'\blast\s+year\b',                  # 去年
    r'\blast\s+month\b',                 # 上个月
    r'\blast\s+week\b',                  # 上周
    r'\bpreviously\s+announced\b',       # 此前已宣布
    r'\bearlier\s+this\s+year\b',        # 今年早些时候
    r'\bback\s+in\b',                    # 回溯到...
    r'\brecall\s+that\b',                # 回想一下...
    r'\bwas\s+reported\b',               # 曾报道
    r'\baccording\s+to.*\d{4}\b',        # 据...年...
]

# 新鲜指示词（出现则判定为新鲜）
FRESH_INDICATORS = [
    r'\btoday\b',
    r'\bnow\b',
    r'\bbreaking\b',
    r'\bjust\s+in\b',
    r'\bjust\s+announced\b',
    r'\bdeveloping\b',
    r'\blive\b',
    r'\bimminent\b',
    r'\bthis\s+morning\b',
    r'\bthis\s+afternoon\b',
    r'\bthis\s+evening\b',
    r'\btonight\b',
    r'\bhours?\s+ago\b',
    r'\bminutes?\s+ago\b',
    r'\bjust\s+happened\b',
]

# 中文旧闻指示词
STALE_INDICATORS_ZH = [
    r'去年', r'前年', r'上月', r'上周',
    r'此前', r'曾经', r'旧闻', r'回顾',
    r'据了解.*年', r'据.*报道',
]

# 中文新鲜指示词
FRESH_INDICATORS_ZH = [
    r'刚刚', r'突发', r'快讯', r'最新',
    r'今天', r'今晚', r'今早', r'今午',
    r'分钟前', r'小时前', r'正在',
]


def score_timeliness(tweet: Tweet) -> float:
    """
    第③层：时效评分

    Returns: 0.0 - 1.0
      1.0 = 最新鲜
      0.0 = 明确旧闻
      0.5 = 无法判断
    """
    content = tweet.content or ""
    content_lower = content.lower()

    # 检查旧闻指示词
    stale_count = 0
    for pattern in STALE_INDICATORS + STALE_INDICATORS_ZH:
        if re.search(pattern, content_lower, re.IGNORECASE):
            stale_count += 1

    # 检查新鲜指示词
    fresh_count = 0
    for pattern in FRESH_INDICATORS + FRESH_INDICATORS_ZH:
        if re.search(pattern, content_lower, re.IGNORECASE):
            fresh_count += 1

    # 检查时间戳（如果有）
    timestamp_age_hours = None
    if tweet.timestamp:
        try:
            dt = datetime.fromisoformat(str(tweet.timestamp).replace('Z', '+00:00'))
            age = datetime.now(dt.tzinfo) - dt
            timestamp_age_hours = age.total_seconds() / 3600
        except (ValueError, TypeError):
            pass

    # 综合评分
    if stale_count > 0 and fresh_count == 0:
        # 明确旧闻
        return max(0.0, 0.3 - stale_count * 0.1)
    elif fresh_count > 0 and stale_count == 0:
        # 明确新鲜
        return min(1.0, 0.7 + fresh_count * 0.1)
    elif timestamp_age_hours is not None:
        # 根据时间戳判断
        if timestamp_age_hours < 1:
            return 0.9
        elif timestamp_age_hours < 6:
            return 0.8
        elif timestamp_age_hours < 24:
            return 0.6
        elif timestamp_age_hours < 72:
            return 0.3
        else:
            return 0.1
    else:
        return 0.5  # 无法判断


def apply_timeliness_scoring(tweets: list) -> list:
    """对推文列表应用时效评分"""
    for t in tweets:
        t._timeliness_score = score_timeliness(t)
        t._clean_tags = getattr(t, '_clean_tags', []) + [f"timeliness:{t._timeliness_score:.1f}"]
    return tweets


# ============================================================
# ④ 情绪噪音清洗
# ============================================================
"""
OIL TO $150 NOW!!!
BUY BUY BUY!!!
CRASH COMING!!!

规则：
  - 全大写比例过高
  - 过多感叹号
  - 夸张价格预测
  - 极端情绪词
  降权或删除。
"""

# 极端情绪词
EXTREME_EMOTION_WORDS = [
    "moon", "to the moon", "lambo", "buy buy", "sell sell",
    "crash coming", "collapse", "apocalypse", "end of world",
    "guaranteed", "100%", "sure thing", "can't lose",
    "pump", "dump", "rug pull", "scam",
    "bull trap", "bear trap", "dead cat bounce",
]

# 夸张价格预测模式
EXAGGERATED_PRICE_PATTERNS = [
    r'\$\s*\d{3,}\s*(NOW|SOON|IMMINENT|TODAY)',   # $150 NOW
    r'(TO|WILL|GOING TO)\s+\$\s*\d{3,}',            # TO $200
    r'\d{4,}%\s*(GAIN|RISE|DROP|CRASH)',            # 5000% GAIN
    r'(WILL|GOING TO)\s+(ZERO|NOTHING|CRASH)',       # WILL CRASH
]

# 垃圾内容模式
SPAM_PATTERNS = [
    r'🔥{3,}',           # 过多火焰emoji
    r'🚀{3,}',           # 过多火箭emoji
    r'❗{3,}',           # 过多感叹emoji
    r'(.)\1{5,}',        # 重复字符 aaaaaaa
    r'FOLLOW\s+ME',      # 涨粉
    r'CLICK\s+HERE',     # 点击链接
    r'JOIN\s+MY',        # 加入群组
    r'DM\s+ME',          # 私信我
    r'FREE\s+SIGNAL',    # 免费信号
    r'PREMIUM\s+GROUP',  # 付费群
]


def score_sentiment_noise(tweet: Tweet) -> float:
    """
    第④层：情绪噪音评分

    Returns: 0.0 - 1.0
      0.0 = 干净内容
      1.0 = 纯噪音（应删除）
    """
    content = tweet.content or ""
    if not content:
        return 0.0

    noise_score = 0.0

    # 1. 全大写比例
    alpha_chars = [c for c in content if c.isalpha()]
    if alpha_chars:
        upper_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
        if upper_ratio > 0.8 and len(alpha_chars) > 10:
            noise_score += 0.4
        elif upper_ratio > 0.6 and len(alpha_chars) > 10:
            noise_score += 0.2

    # 2. 感叹号密度
    exclamation_count = content.count('!')
    if exclamation_count >= 5:
        noise_score += 0.3
    elif exclamation_count >= 3:
        noise_score += 0.15

    # 3. 极端情绪词
    content_lower = content.lower()
    emotion_count = sum(1 for w in EXTREME_EMOTION_WORDS if w in content_lower)
    noise_score += emotion_count * 0.15

    # 4. 夸张价格预测
    for pattern in EXAGGERATED_PRICE_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            noise_score += 0.3
            break

    # 5. 垃圾/诈骗模式
    for pattern in SPAM_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            noise_score += 0.5
            break

    return min(1.0, noise_score)


def apply_sentiment_noise_scoring(tweets: list) -> list:
    """对推文列表应用情绪噪音评分"""
    for t in tweets:
        t._sentiment_noise_score = score_sentiment_noise(t)
        t._clean_tags = getattr(t, '_clean_tags', []) + [f"noise:{t._sentiment_noise_score:.1f}"]
    return tweets


# ============================================================
# ⑤ 二手转述清洗
# ============================================================
"""
Someone says...
Rumor:
Unconfirmed:
Hearing that...

这类必须标记：未经证实，不能直接当事实。
"""

# 未证实标记词
HEARSAY_INDICATORS = [
    # 英文
    r'\bsomeone\s+says?\b',
    r'\brumor\b',
    r'\brumour\b',
    r'\bunconfirmed\b',
    r'\bhearing\s+(that|we\s+might)\b',
    r'\bi\s+hear\b',
    r'\bword\s+on\s+the\s+street\b',
    r'\bsources?\s+(say|tell|suggest|indicate)\b',
    r'\breportedly\b',
    r'\ballegedly\b',
    r'\bsupposedly\b',
    r'\bmay\s+(be|have)\b',
    r'\bcould\s+(be|mean)\b',
    r'\bpotentially\b',
    r'\bit\s+is\s+said\b',
    r'\bthere\s+are\s+reports?\b',
    r'\bif\s+true\b',
    r'\btake\s+this\s+with\s+a\s+grain\s+of\s+salt\b',
    r'\bunverified\b',
    r'\bspeculation\b',
    r'\bchatter\b',
    # 中文
    r'据说', r'传闻', r'据传', r'未经证实',
    r'有人称', r'消息称', r'市场传言',
    r'可能', r'或许', r'据知情人士',
]

# 明确事实标记词（反向信号：有这些词说明是确认的事实）
FACT_INDICATORS = [
    r'\bconfirmed\b',
    r'\bofficially\s+announced\b',
    r'\bstatement\s+from\b',
    r'\baccording\s+to\s+(officials?|statement)\b',
    r'\bpress\s+release\b',
    r'\bexecutive\s+order\b',
    r'\bsigned\s+into\s+law\b',
    r'官方宣布', r'已确认', r'正式发布',
]


def flag_hearsay(tweet: Tweet) -> bool:
    """
    第⑤层：二手转述标记

    Returns: True = 未经证实内容
    """
    content = tweet.content or ""
    if not content:
        return False

    # 检查未证实标记
    has_hearsay = False
    for pattern in HEARSAY_INDICATORS:
        if re.search(pattern, content, re.IGNORECASE):
            has_hearsay = True
            break

    # 如果同时有事实确认词，则不算二手
    if has_hearsay:
        for pattern in FACT_INDICATORS:
            if re.search(pattern, content, re.IGNORECASE):
                return False

    return has_hearsay


def apply_hearsay_flagging(tweets: list) -> list:
    """对推文列表应用二手转述标记"""
    for t in tweets:
        is_hearsay = flag_hearsay(t)
        t._hearsay_flag = is_hearsay
        if is_hearsay:
            t._clean_tags = getattr(t, '_clean_tags', []) + ["hearsay:unconfirmed"]
        else:
            t._clean_tags = getattr(t, '_clean_tags', []) + ["hearsay:factual"]
    return tweets


# ============================================================
# ⑥ 多源交叉验证（最高级）
# ============================================================
"""
同一事件如果同时被 Reuters + Bloomberg + WSJ + 官方账号 提及，
可信度暴涨。
"""

# 高可信新闻源（用于交叉验证）
CROSS_VERIFY_SOURCES = {
    "wire": {"@Reuters", "@Bloomberg", "@AP", "@AFP"},
    "newspaper": {"@WSJ", "@FT", "@FinancialTimes", "@NYTimes", "@WashingtonPost"},
    "tv": {"@CNBC", "@BBCBreaking", "@NBCNews", "@CNN"},
    "official": set(OFFICIAL_ACCOUNTS),
    "journalist": set(FRONTLINE_JOURNALISTS),
}


def cross_verify(tweets: list) -> dict:
    """
    第⑥层：多源交叉验证

    对已去重的推文，检查同一事件是否被多个独立来源确认。

    Returns: {cluster_id: cross_verify_score} 映射
    """
    # 按去重聚类分组
    clusters = defaultdict(list)
    for t in tweets:
        cluster_id = getattr(t, '_dedup_cluster_id', t.tweet_id)
        clusters[cluster_id].append(t)

    cross_scores = {}

    for cluster_id, cluster_tweets in clusters.items():
        # 统计每个来源类别的独立来源数
        source_categories = set()
        source_count = 0

        for t in cluster_tweets:
            username = (t.username or "").lower()

            for cat, accounts in CROSS_VERIFY_SOURCES.items():
                if username in {a.lower() for a in accounts}:
                    source_categories.add(cat)
                    source_count += 1
                    break

        # 计算交叉验证分数
        # 基础分：独立来源类别数
        category_score = len(source_categories)

        # 加分：来源数量
        count_bonus = min(source_count - 1, 3) * 0.5  # 每多一个来源+0.5，最多+1.5

        # 加分：有官方来源
        official_bonus = 1.0 if "official" in source_categories else 0.0

        # 加分：有通讯社来源
        wire_bonus = 0.5 if "wire" in source_categories else 0.0

        # 加分：有记者来源
        journalist_bonus = 0.5 if "journalist" in source_categories else 0.0

        total_score = category_score + count_bonus + official_bonus + wire_bonus + journalist_bonus
        cross_scores[cluster_id] = min(total_score, 10.0)  # 封顶10分

    # 将分数写回推文
    for t in tweets:
        cluster_id = getattr(t, '_dedup_cluster_id', t.tweet_id)
        t._cross_verify_score = cross_scores.get(cluster_id, 0.0)
        cv = t._cross_verify_score
        if cv >= 5:
            tag = "cross_verify:strong"
        elif cv >= 3:
            tag = "cross_verify:moderate"
        elif cv >= 1:
            tag = "cross_verify:weak"
        else:
            tag = "cross_verify:none"
        t._clean_tags = getattr(t, '_clean_tags', []) + [tag]

    return cross_scores


# ============================================================
# 综合评分 + 最终裁决
# ============================================================

def calculate_final_score(tweet: Tweet) -> float:
    """
    综合所有清洗层分数，计算最终情报价值分

    权重：
      来源可信度: 30%
      时效性: 25%
      情绪噪音: 20%（反向，噪音越高分越低）
      交叉验证: 25%
      二手转述: 扣分项
    """
    source = getattr(tweet, '_source_score', 5)
    timeliness = getattr(tweet, '_timeliness_score', 0.5)
    noise = getattr(tweet, '_sentiment_noise_score', 0.0)
    cross = getattr(tweet, '_cross_verify_score', 0.0)
    hearsay = getattr(tweet, '_hearsay_flag', False)

    # 加权计算
    score = (
        source * 0.30 +
        timeliness * 10 * 0.25 +      # 将0-1映射到0-10
        (1.0 - noise) * 10 * 0.20 +   # 噪音反向
        cross * 0.25
    )

    # 二手转述扣分
    if hearsay:
        score *= 0.6

    return round(min(score, 10.0), 2)


def final_verdict(tweet: Tweet) -> str:
    """
    最终裁决

    Returns:
      'actionable'  - 高价值可行动情报（≥7分）
      'noteworthy'  - 值得关注（5-7分）
      'low_value'   - 低价值（3-5分）
      'discard'     - 丢弃（<3分 或 噪音>0.7）
    """
    score = getattr(tweet, '_final_score', 0)
    noise = getattr(tweet, '_sentiment_noise_score', 0)

    if noise >= 0.7:
        return "discard"
    if score >= 7.0:
        return "actionable"
    elif score >= 5.0:
        return "noteworthy"
    elif score >= 3.0:
        return "low_value"
    else:
        return "discard"


# ============================================================
# 完整清洗流水线
# ============================================================

def clean_pipeline(raw_tweets: list, verbose: bool = False) -> list:
    """
    6层清洗流水线

    Args:
        raw_tweets: 原始推文列表（Tweet对象）
        verbose: 是否打印清洗统计

    Returns: 清洗后的高价值推文列表
    """
    if not raw_tweets:
        return []

    stats = {"input": len(raw_tweets)}

    # ① 去重清洗
    tweets = deduplicate(raw_tweets)
    stats["after_dedup"] = len(tweets)
    stats["duplicates_removed"] = stats["input"] - stats["after_dedup"]

    # ② 来源可信度评分
    tweets = apply_source_scoring(tweets)

    # ③ 时效评分
    tweets = apply_timeliness_scoring(tweets)

    # ④ 情绪噪音评分
    tweets = apply_sentiment_noise_scoring(tweets)

    # ⑤ 二手转述标记
    tweets = apply_hearsay_flagging(tweets)

    # ⑥ 多源交叉验证
    cross_scores = cross_verify(tweets)

    # 综合评分 + 最终裁决
    for t in tweets:
        t._final_score = calculate_final_score(t)
        t._final_verdict = final_verdict(t)
        t._clean_tags = getattr(t, '_clean_tags', []) + [
            f"final:{t._final_score}",
            f"verdict:{t._final_verdict}",
        ]

    # 按最终分数排序
    tweets.sort(key=lambda t: t._final_score, reverse=True)

    # 统计
    actionable = sum(1 for t in tweets if t._final_verdict == "actionable")
    noteworthy = sum(1 for t in tweets if t._final_verdict == "noteworthy")
    low_value = sum(1 for t in tweets if t._final_verdict == "low_value")
    discard = sum(1 for t in tweets if t._final_verdict == "discard")
    hearsay_count = sum(1 for t in tweets if t._hearsay_flag)
    noise_count = sum(1 for t in tweets if t._sentiment_noise_score > 0.5)

    stats.update({
        "actionable": actionable,
        "noteworthy": noteworthy,
        "low_value": low_value,
        "discard": discard,
        "hearsay_flagged": hearsay_count,
        "noise_flagged": noise_count,
    })

    if verbose:
        print_clean_stats(stats, tweets)

    return tweets


def print_clean_stats(stats: dict, tweets: list):
    """打印清洗统计"""
    print("=" * 60)
    print("  6层数据清洗报告")
    print("=" * 60)
    print(f"  输入推文: {stats['input']}")
    print(f"  ① 去重后: {stats['after_dedup']} (去除 {stats['duplicates_removed']} 条重复)")
    print(f"  ⑤ 二手转述标记: {stats['hearsay_flagged']} 条")
    print(f"  ④ 情绪噪音标记: {stats['noise_flagged']} 条")
    print("-" * 60)
    print(f"  最终裁决:")
    print(f"    🟢 可行动情报 (actionable): {stats['actionable']}")
    print(f"    🟡 值得关注 (noteworthy):   {stats['noteworthy']}")
    print(f"    🟠 低价值 (low_value):      {stats['low_value']}")
    print(f"    🔴 丢弃 (discard):          {stats['discard']}")
    print("=" * 60)

    # 显示Top5
    print("\n  Top 5 高价值情报:")
    for i, t in enumerate(tweets[:5], 1):
        source = getattr(t, '_source_score', '?')
        time_s = getattr(t, '_timeliness_score', '?')
        noise_s = getattr(t, '_sentiment_noise_score', '?')
        cross_s = getattr(t, '_cross_verify_score', '?')
        hearsay = "⚠️未证实" if getattr(t, '_hearsay_flag', False) else "✅事实"
        print(f"    {i}. [{t._final_verdict}] {t._final_score}分 | @{t.username}")
        print(f"       来源:{source} 时效:{time_s} 噪音:{noise_s} 交叉:{cross_s} {hearsay}")
        print(f"       {t.content[:80]}...")
    print()


# ============================================================
# 测试
# ============================================================

def _make_tweet(tweet_id, username, content, timestamp=None,
                likes=0, retweets=0, is_verified=False, is_retweet=False):
    """快速构造测试推文"""
    return Tweet(
        tweet_id=tweet_id, username=username, content=content,
        timestamp=timestamp or datetime.now().isoformat(),
        likes=likes, retweets=retweets, replies=0, impressions=0,
        is_verified=is_verified, is_retweet=is_retweet, has_media=False,
        media_urls=[], links=[], hashtags=[], mentions=[],
    )


if __name__ == "__main__":
    now = datetime.now()

    # 构造测试数据：模拟真实抓取场景
    test_tweets = [
        # --- 场景1: Reuters发一条突发，被多人转发 ---
        _make_tweet("t1", "@Reuters", "BREAKING: OPEC+ agrees to cut production by 2.2 million barrels per day starting next month, sources say",
                    now.isoformat(), likes=5000, retweets=3000, is_verified=True),
        _make_tweet("t2", "@Bloomberg", "OPEC+ production cut of 2.2 million bpd confirmed by Saudi and Russian officials",
                    now.isoformat(), likes=3000, retweets=2000, is_verified=True),
        _make_tweet("t3", "@WSJ", "OPEC+ to cut output by 2.2 million barrels per day in historic agreement",
                    now.isoformat(), likes=2000, retweets=1500, is_verified=True),
        _make_tweet("t4", "@random_trader", "OPEC+ CUT 2.2M BPD!!! OIL TO $150 NOW!!! 🚀🚀🚀 BUY BUY BUY!!!",
                    now.isoformat(), likes=50, retweets=5),
        _make_tweet("t5", "@anon_breaking99283", "Hearing that OPEC might cut production. Unconfirmed. Someone says big move coming",
                    now.isoformat()),

        # --- 场景2: 旧闻翻炒 ---
        _make_tweet("t6", "@oil_trader", "Remember last year when OPEC cut production? That was 2024. Back then oil went to $95.",
                    now.isoformat(), likes=10, retweets=2),
        _make_tweet("t7", "@energy_news", "Previously announced OPEC+ cuts from earlier this year are still in effect, sources say",
                    now.isoformat(), likes=100, retweets=30, is_verified=True),

        # --- 场景3: 地缘突发事件 ---
        _make_tweet("t8", "@IDF", "ALERT: Incoming missile attack detected. Civilian shelters open in central Israel. This is not a drill.",
                    now.isoformat(), likes=10000, retweets=8000, is_verified=True),
        _make_tweet("t9", "@Conflicts", "🚨 BREAKING: Missile attack reported in central Israel. Sirens sounding in Tel Aviv area.",
                    now.isoformat(), likes=5000, retweets=4000, is_verified=True),
        _make_tweet("t10", "@RichardEngel", "Reports of missile attack in Israel. Developing situation. I'm working to confirm details.",
                    now.isoformat(), likes=3000, retweets=2000, is_verified=True),

        # --- 场景4: 垃圾内容 ---
        _make_tweet("t11", "@crypto_pump", "🔥🔥🔥 OIL GOING TO $500!!! CRASH COMING!!! FOLLOW ME FOR FREE SIGNALS!!! DM ME NOW!!!",
                    now.isoformat(), likes=5, retweets=1),
        _make_tweet("t12", "@premium_signals", "JOIN MY PREMIUM GROUP! 100% GUARANTEED OIL CALLS! CLICK HERE https://scam.link",
                    now.isoformat()),

        # --- 场景5: 正常分析内容 ---
        _make_tweet("t13", "@JKempEnergy", "EIA crude inventory draw of 4.2 million barrels vs expected 1.5 million. Bullish surprise.",
                    now.isoformat(), likes=800, retweets=300, is_verified=True),
        _make_tweet("t14", "@charliebilello", "Fed rate decision coming this week. Markets pricing in 78% chance of 25bps cut.",
                    now.isoformat(), likes=1500, retweets=500, is_verified=True),

        # --- 场景6: 中文内容 ---
        _make_tweet("t15", "@haohong_cfa", "美联储本周大概率降息25个基点，市场已定价78%。关注CPI数据。",
                    now.isoformat(), likes=200, retweets=50, is_verified=True),
        _make_tweet("t16", "@caolei1", "据传OPEC+将紧急开会讨论增产，但未经证实。此前曾有类似传闻。",
                    now.isoformat(), likes=150, retweets=30, is_verified=True),
    ]

    print("X 实时情报系统 - 6层数据清洗引擎测试")
    print("=" * 60)
    print(f"  输入: {len(test_tweets)} 条原始推文\n")

    # 执行清洗
    cleaned = clean_pipeline(test_tweets, verbose=True)

    # 详细展示每条推文的清洗结果
    print("\n  逐条清洗详情:")
    print("-" * 60)
    for t in cleaned:
        tags = " | ".join(getattr(t, '_clean_tags', []))
        print(f"  @{t.username} [{t._final_verdict}] {t._final_score}分")
        print(f"    {t.content[:70]}...")
        print(f"    标签: {tags}")
        print()
