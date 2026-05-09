# -*- coding: utf-8 -*-
"""
X 实时情报系统 - 抓取前极速决策器
================================================
交易员级前置AI：用户一句话 → 最少账号 + 最精准事件短语 + 最短抓取路径

核心原则：快、准、少、能执行
  - 最多 Top5 账号
  - 最多 Top5 事件短语（事件+主体+动作）
  - 最多 2 条搜索任务
  - 先判市场阶段，再定抓取路径
"""

from x_intel_rules import S_LEVEL, A_LEVEL


# ============================================================
# 1. 市场阶段判断（决定抓取路径的核心）
# ============================================================

MARKET_REGIMES = {
    "supply_risk": {
        "label": "供给驱动",
        "triggers_zh": ["霍尔木兹", "封锁", "制裁", "OPEC", "减产", "增产", "停产",
                        "断供", "油轮", "管道", "炼油", "库存", "产量", "供应"],
        "triggers_en": ["hormuz", "blockade", "sanction", "opec", "cut", "output",
                        "supply", "disruption", "tanker", "pipeline", "refinery",
                        "inventory", "production", "embargo", "spar"],
    },
    "demand_risk": {
        "label": "需求驱动",
        "triggers_zh": ["需求", "消费", "衰退", "经济", "GDP", "PMI", "中国",
                        "印度", "进口", "炼厂", "开工率"],
        "triggers_en": ["demand", "consumption", "recession", "gdp", "pmi", "china",
                        "india", "import", "refinery", "utilization", "slowing"],
    },
    "policy_risk": {
        "label": "政策驱动",
        "triggers_zh": ["美联储", "降息", "加息", "利率", "关税", "特朗普",
                        "鲍威尔", "央行", "QE", "缩表", "财政", "行政令"],
        "triggers_en": ["fed", "rate cut", "rate hike", "tariff", "trump", "powell",
                        "central bank", "ecb", "boj", "policy", "executive order",
                        "fiscal", "deregulation", "sanctions policy"],
    },
    "war_risk": {
        "label": "战争驱动",
        "triggers_zh": ["战争", "冲突", "导弹", "袭击", "入侵", "停火", "军事",
                        "以色列", "伊朗", "乌克兰", "俄罗斯", "核", "胡塞",
                        "真主党", "哈马斯", "红海", "中东"],
        "triggers_en": ["war", "missile", "attack", "invasion", "ceasefire", "military",
                        "israel", "iran", "ukraine", "russia", "nuclear", "houthis",
                        "hezbollah", "hamas", "red sea", "middle east", "strike",
                        "escalation", "retaliation"],
    },
    "dollar_risk": {
        "label": "美元驱动",
        "triggers_zh": ["美元", "汇率", "日元", "干预", "贬值", "升值", "DXY",
                        "人民币", "欧元", "外汇"],
        "triggers_en": ["dollar", "dxy", "yen", "intervention", "devalue", "appreciate",
                        "forex", "usd", "currency", "exchange rate"],
    },
    "risk_sentiment": {
        "label": "风险情绪驱动",
        "triggers_zh": ["避险", "恐慌", "VIX", "崩盘", "暴跌", "熔断", "黑天鹅",
                        "闪崩", "风险", "股市", "加密", "比特币"],
        "triggers_en": ["risk off", "safe haven", "vix", "crash", "flash crash",
                        "black swan", "fear", "panic", "contagion", "crypto",
                        "bitcoin", "equity", "selloff", "flight to safety"],
    },
}

# 资产 → 默认市场阶段映射（当用户没给足够上下文时）
ASSET_DEFAULT_REGIME = {
    "oil": "supply_risk",
    "gold": "policy_risk",
    "fx": "policy_risk",
    "crypto": "risk_sentiment",
    "equity": "risk_sentiment",
    "macro": "policy_risk",
    "geopolitics": "war_risk",
}


# ============================================================
# 2. 资产识别（极简）
# ============================================================

ASSET_PATTERNS = {
    "oil": {
        "zh": ["油价", "原油", "石油", "布伦特", "WTI", "OPEC", "欧佩克", "能源",
               "汽油", "天然气", "LNG", "油轮", "炼油"],
        "en": ["oil", "crude", "brent", "wti", "opec", "petroleum", "gasoline",
               "lng", "natural gas", "refinery", "tanker", "barrel", "heating oil"],
    },
    "gold": {
        "zh": ["黄金", "金价", "贵金属", "白银", "银价", "避险"],
        "en": ["gold", "xau", "silver", "xag", "precious metal", "bullion"],
    },
    "fx": {
        "zh": ["外汇", "汇率", "美元", "欧元", "日元", "人民币", "英镑",
               "USD", "EUR", "JPY", "CNY", "DXY", "干预"],
        "en": ["forex", "fx", "dollar", "euro", "yen", "yuan", "pound",
               "dxy", "intervention", "currency"],
    },
    "crypto": {
        "zh": ["比特币", "BTC", "以太坊", "ETH", "加密", "币", "区块链"],
        "en": ["bitcoin", "btc", "ethereum", "eth", "crypto", "blockchain"],
    },
    "equity": {
        "zh": ["股市", "美股", "A股", "港股", "标普", "纳斯达克", "股指"],
        "en": ["stock", "equity", "s&p", "sp500", "nasdaq", "dow", "spx"],
    },
    "macro": {
        "zh": ["经济", "通胀", "CPI", "PCE", "非农", "GDP", "PMI", "衰退",
               "加息", "降息", "利率", "美联储", "鲍威尔"],
        "en": ["economy", "inflation", "cpi", "pce", "nonfarm", "gdp", "pmi",
               "recession", "rate", "federal reserve", "powell"],
    },
    "geopolitics": {
        "zh": ["战争", "冲突", "地缘", "制裁", "伊朗", "乌克兰", "以色列",
               "导弹", "霍尔木兹", "红海", "停火", "军事", "核"],
        "en": ["war", "conflict", "geopolitic", "sanction", "iran", "ukraine",
               "israel", "missile", "hormuz", "red sea", "ceasefire", "nuclear"],
    },
}


# ============================================================
# 3. 事件短语库（事件+主体+动作，可交易级别）
# ============================================================

# 格式: {资产: {市场阶段: [(事件短语, 权重)]}}
EVENT_PHRASES = {
    "oil": {
        "supply_risk": [
            ("Hormuz blockade", 10),
            ("Iran tanker seizure", 10),
            ("Saudi voluntary cut", 9),
            ("OPEC+ emergency meeting", 9),
            ("Red Sea tanker attack", 9),
            ("Russia sanction escalation", 8),
            ("SPR release announcement", 8),
            ("Libya force majeure", 7),
            ("pipeline sabotage", 7),
            ("refinery fire shutdown", 7),
        ],
        "demand_risk": [
            ("China demand downgrade", 8),
            ("US recession signal", 8),
            ("India crude import drop", 7),
            ("refinery margin collapse", 7),
            ("global PMI contraction", 7),
        ],
        "policy_risk": [
            ("Trump Iran sanctions snapback", 10),
            ("Trump SPR refill order", 8),
            ("secondary sanctions enforcement", 8),
            ("export license revocation", 7),
        ],
        "war_risk": [
            ("Iran missile strike Israel", 10),
            ("Israel attack on Iran oil", 10),
            ("Houthi Red Sea escalation", 9),
            ("ceasefire collapse", 8),
            ("US military Gulf deployment", 8),
        ],
        "dollar_risk": [
            ("DXY surge oil demand", 6),
            ("EM currency crisis oil", 6),
        ],
        "risk_sentiment": [
            ("global risk off oil selloff", 7),
            ("commodity fund liquidation", 6),
        ],
    },
    "gold": {
        "policy_risk": [
            ("Fed surprise rate cut", 10),
            ("Fed hawkish hold", 9),
            ("Powell dovish pivot speech", 9),
            ("ECB rate decision surprise", 8),
            ("inflation data miss", 8),
        ],
        "war_risk": [
            ("Iran nuclear escalation", 10),
            ("Israel Iran direct conflict", 10),
            ("Russia nuclear rhetoric", 9),
            ("ceasefire violation gold surge", 8),
        ],
        "dollar_risk": [
            ("DXY collapse gold rally", 9),
            ("US debt ceiling crisis", 8),
            ("dollar devaluation talk", 7),
        ],
        "risk_sentiment": [
            ("VIX spike gold demand", 8),
            ("banking crisis contagion", 8),
            ("stock market crash gold", 8),
        ],
        "supply_risk": [
            ("central bank gold buying surge", 8),
            ("China gold import data", 7),
        ],
    },
    "fx": {
        "policy_risk": [
            ("Fed rate decision surprise", 10),
            ("BOJ policy shift surprise", 9),
            ("Japan FX intervention", 10),
            ("ECB rate divergence", 8),
            ("Trump tariff announcement", 9),
        ],
        "dollar_risk": [
            ("USDJPY intervention level", 10),
            ("DXY breakout breakdown", 8),
            ("Treasury yield spike", 8),
        ],
        "war_risk": [
            ("geopolitical risk safe haven", 8),
            ("sanction currency impact", 7),
        ],
        "risk_sentiment": [
            ("risk off yen surge", 8),
            ("EM currency crisis", 7),
        ],
    },
    "crypto": {
        "policy_risk": [
            ("SEC ETF approval delay", 10),
            ("crypto regulation crackdown", 9),
            ("stablecoin legislation", 8),
        ],
        "risk_sentiment": [
            ("Bitcoin ETF inflow record", 9),
            ("crypto fund liquidation", 8),
            ("whale wallet movement", 7),
        ],
        "dollar_risk": [
            ("Fed liquidity injection", 8),
            ("M2 money supply surge", 7),
        ],
    },
    "equity": {
        "policy_risk": [
            ("Fed rate decision surprise", 10),
            ("Trump tariff escalation", 9),
            ("corporate tax cut passage", 8),
        ],
        "risk_sentiment": [
            ("VIX spike selloff", 9),
            ("AI earnings beat miss", 8),
            ("index circuit breaker", 9),
        ],
    },
    "macro": {
        "policy_risk": [
            ("Fed surprise rate cut", 10),
            ("Fed hawkish hold", 9),
            ("Trump tariff announcement", 9),
            ("fiscal stimulus package", 8),
        ],
        "demand_risk": [
            ("nonfarm payroll miss", 9),
            ("CPI inflation surprise", 9),
            ("PMI contraction signal", 8),
            ("recession indicator flash", 8),
        ],
        "war_risk": [
            ("geopolitical escalation supply chain", 8),
        ],
    },
    "geopolitics": {
        "war_risk": [
            ("Iran missile strike Israel", 10),
            ("Israel attack on Iran nuclear", 10),
            ("ceasefire collapse", 9),
            ("Russia nuclear escalation", 9),
            ("Houthi Red Sea attack", 8),
            ("US military deployment Gulf", 8),
            ("Ukraine counteroffensive launch", 8),
        ],
        "policy_risk": [
            ("NATO Article 5 invocation", 10),
            ("Trump sanctions announcement", 9),
            ("UN Security Council vote", 7),
        ],
    },
}


# ============================================================
# 4. 账号权威度排序（谁说的 > 说了什么）
# ============================================================

# 按权威度分层的账号池（从高到低）
AUTHORITY_TIERS = {
    # Tier 1: 终极决策者（一句话移动市场）
    "decision_makers": [
        "@realDonaldTrump", "@VladimirPutin", "@KSAmofaEN",
        "@RTErdogan", "@narendramodi", "@LulaOficial",
        "@Claudiashein", "@officialABAT", "@EmmanuelMacron",
    ],
    # Tier 2: 官方机构（央行/财政部/OPEC/军队）
    "official_institutions": [
        "@federalreserve", "@ecb", "@IDF", "@DefenceU",
        "@Conflicts", "@WhiteHouse", "@PentagonPressSec",
    ],
    # Tier 3: 通讯社（事实源头）
    "wire_services": [
        "@Reuters", "@Bloomberg", "@DeItaone", "@WSJ", "@CNBC",
    ],
    # Tier 4: 一线记者（最快爆料）
    "frontline_journalists": [
        "@JavierBlas", "@JKempEnergy", "@samdagher", "@RichardEngel",
        "@JackDetsch", "@SangerNYT", "@OilSheppard", "@ChristopherJM",
        "@AlexCrawfordSky", "@yarotrof", "@RALee85", "@IAPonomarenko",
        "@TankersTrackers", "@ClydeComods",
    ],
    # Tier 5: 专业分析师
    "analysts": [
        "@Rory_Johnston", "@anasalhajji", "@TomKloza", "@GasBuddyGuy",
        "@charliebilello", "@elerianm", "@LizAnnSonders", "@GoldmanSachs",
        "@JPMorgan",
    ],
}

# 资产 + 市场阶段 → 最相关账号（极速映射，不遍历大列表）
ASSET_REGIME_ACCOUNTS = {
    "oil": {
        "supply_risk": [
            "@JavierBlas", "@Reuters", "@KSAmofaEN", "@TankersTrackers", "@realDonaldTrump",
        ],
        "demand_risk": [
            "@JKempEnergy", "@Reuters", "@charliebilello", "@narendramodi", "@DeItaone",
        ],
        "policy_risk": [
            "@realDonaldTrump", "@Reuters", "@DeItaone", "@KSAmofaEN", "@JavierBlas",
        ],
        "war_risk": [
            "@IDF", "@Conflicts", "@Reuters", "@RichardEngel", "@samdagher",
        ],
        "dollar_risk": [
            "@DeItaone", "@Reuters", "@charliebilello", "@federalreserve", "@JavierBlas",
        ],
        "risk_sentiment": [
            "@DeItaone", "@Reuters", "@Bloomberg", "@Conflicts", "@charliebilello",
        ],
    },
    "gold": {
        "policy_risk": [
            "@federalreserve", "@DeItaone", "@Reuters", "@charliebilello", "@elerianm",
        ],
        "war_risk": [
            "@Conflicts", "@IDF", "@Reuters", "@RichardEngel", "@DeItaone",
        ],
        "dollar_risk": [
            "@DeItaone", "@Reuters", "@charliebilello", "@federalreserve", "@alaidi",
        ],
        "risk_sentiment": [
            "@DeItaone", "@Conflicts", "@Reuters", "@ZeroHedge", "@charliebilello",
        ],
        "supply_risk": [
            "@DeItaone", "@Reuters", "@GoldmanSachs", "@ZeroHedge", "@charliebilello",
        ],
    },
    "fx": {
        "policy_risk": [
            "@federalreserve", "@DeItaone", "@Reuters", "@charliebilello", "@realDonaldTrump",
        ],
        "dollar_risk": [
            "@DeItaone", "@Reuters", "@alaidi", "@federalreserve", "@realDonaldTrump",
        ],
        "war_risk": [
            "@Conflicts", "@Reuters", "@DeItaone", "@realDonaldTrump", "@RichardEngel",
        ],
        "risk_sentiment": [
            "@DeItaone", "@Conflicts", "@Reuters", "@charliebilello", "@ZeroHedge",
        ],
    },
    "crypto": {
        "policy_risk": [
            "@DeItaone", "@Reuters", "@CathieDWood", "@ZeroHedge", "@federalreserve",
        ],
        "risk_sentiment": [
            "@DeItaone", "@CathieDWood", "@Reuters", "@ZeroHedge", "@howardlindzon",
        ],
        "dollar_risk": [
            "@DeItaone", "@federalreserve", "@Reuters", "@charliebilello", "@ZeroHedge",
        ],
    },
    "equity": {
        "policy_risk": [
            "@federalreserve", "@DeItaone", "@realDonaldTrump", "@Reuters", "@charliebilello",
        ],
        "risk_sentiment": [
            "@DeItaone", "@Conflicts", "@Reuters", "@charliebilello", "@ZeroHedge",
        ],
    },
    "macro": {
        "policy_risk": [
            "@federalreserve", "@DeItaone", "@realDonaldTrump", "@Reuters", "@charliebilello",
        ],
        "demand_risk": [
            "@DeItaone", "@charliebilello", "@Reuters", "@ZeroHedge", "@Bloomberg",
        ],
        "war_risk": [
            "@Conflicts", "@Reuters", "@DeItaone", "@RichardEngel", "@realDonaldTrump",
        ],
    },
    "geopolitics": {
        "war_risk": [
            "@IDF", "@Conflicts", "@Reuters", "@RichardEngel", "@samdagher",
        ],
        "policy_risk": [
            "@realDonaldTrump", "@Reuters", "@DeItaone", "@JackDetsch", "@SangerNYT",
        ],
    },
}


# ============================================================
# 5. 极速决策器（核心）
# ============================================================

def decide(query: str) -> dict:
    """
    抓取前极速决策器

    输入: 用户一句市场问题
    输出: 极简抓取方案（Top5账号 + Top5事件短语 + 最多2条搜索任务）

    Returns:
        {
            "asset": str,
            "user_intent": str,
            "current_regime": str,
            "top_accounts": list[str],      # 最多5个
            "top_event_phrases": list[str],  # 最多5个
            "crawl_tasks": list[str],        # 最多2条X搜索语句
            "why_this_route": str,
            "urgency": str,
        }
    """
    q = query.lower()

    # --- Step 1: 识别资产 ---
    asset = _detect_asset(q)

    # --- Step 2: 识别用户意图 ---
    intent = _detect_intent(q)

    # --- Step 3: 判断市场阶段 ---
    regime = _detect_regime(q, asset)

    # --- Step 4: 判断紧急度 ---
    urgency = _detect_urgency(q)

    # --- Step 5: 选Top5账号 ---
    accounts = _pick_accounts(asset, regime)

    # --- Step 6: 选Top5事件短语 ---
    phrases = _pick_phrases(asset, regime)

    # --- Step 7: 生成最多2条搜索任务 ---
    crawl_tasks = _build_crawl_tasks(accounts, phrases)

    # --- Step 8: 生成路由理由 ---
    why = _build_why(asset, regime, phrases)

    return {
        "asset": asset,
        "user_intent": intent,
        "current_regime": regime,
        "top_accounts": accounts,
        "top_event_phrases": phrases,
        "crawl_tasks": crawl_tasks,
        "why_this_route": why,
        "urgency": urgency,
    }


def _detect_asset(q: str) -> str:
    """识别资产类别"""
    scores = {}
    for asset, patterns in ASSET_PATTERNS.items():
        count = sum(1 for w in patterns["zh"] + patterns["en"] if w.lower() in q)
        if count > 0:
            scores[asset] = count
    if scores:
        return max(scores, key=scores.get)
    return "macro"


def _detect_intent(q: str) -> str:
    """识别用户意图（极简）"""
    direction_words = ["涨", "跌", "会涨", "会跌", "涨吗", "跌吗", "怎么看",
                       "方向", "趋势", "up", "down", "rise", "fall", "bullish",
                       "bearish", "rally", "crash", "还能涨", "还能跌"]
    magnitude_words = ["多少", "幅度", "目标价", "空间", "点位", "how much",
                       "target", "level", "how far"]
    timing_words = ["什么时候", "何时", "今天", "明天", "下周", "when", "soon",
                    "today", "tonight"]
    risk_words = ["风险", "黑天鹅", "突发", "万一", "极端", "会不会", "可能",
                  "risk", "black swan", "what if", "tail risk", "surprise"]

    intents = []
    if any(w in q for w in direction_words):
        intents.append("direction")
    if any(w in q for w in magnitude_words):
        intents.append("magnitude")
    if any(w in q for w in timing_words):
        intents.append("timing")
    if any(w in q for w in risk_words):
        intents.append("event_risk")

    return " + ".join(intents) if intents else "direction"


def _detect_regime(q: str, asset: str) -> str:
    """判断当前市场阶段"""
    scores = {}
    for regime, info in MARKET_REGIMES.items():
        count = sum(1 for w in info["triggers_zh"] + info["triggers_en"] if w.lower() in q)
        if count > 0:
            scores[regime] = count

    if scores:
        return max(scores, key=scores.get)

    # 根据资产默认阶段
    return ASSET_DEFAULT_REGIME.get(asset, "policy_risk")


def _detect_urgency(q: str) -> str:
    """判断紧急度"""
    critical = ["突发", "刚刚", "breaking", "just in", "urgent", "现在", "马上",
                "happening", "right now", "alert"]
    high = ["今天", "今晚", "明天", "today", "tonight", "soon", "即将", "imminent"]

    for w in critical:
        if w in q:
            return "critical"
    for w in high:
        if w in q:
            return "high"
    return "normal"


def _pick_accounts(asset: str, regime: str) -> list:
    """选Top5账号"""
    pool = ASSET_REGIME_ACCOUNTS.get(asset, {}).get(regime, [])
    if not pool:
        # fallback到资产默认阶段
        default_regime = ASSET_DEFAULT_REGIME.get(asset, "policy_risk")
        pool = ASSET_REGIME_ACCOUNTS.get(asset, {}).get(default_regime, [])
    return pool[:5]


def _pick_phrases(asset: str, regime: str) -> list:
    """选Top5事件短语"""
    phrases = EVENT_PHRASES.get(asset, {}).get(regime, [])
    if not phrases:
        default_regime = ASSET_DEFAULT_REGIME.get(asset, "policy_risk")
        phrases = EVENT_PHRASES.get(asset, {}).get(default_regime, [])
    # 按权重排序取Top5
    sorted_p = sorted(phrases, key=lambda x: x[1], reverse=True)
    return [p[0] for p in sorted_p[:5]]


def _build_crawl_tasks(accounts: list, phrases: list) -> list:
    """
    生成最多2条X搜索语句

    格式: from:account1 OR from:account2 phrase1 OR phrase2
    """
    tasks = []

    # 任务1: 前2个账号 + 前2个短语
    acc_part = " OR ".join([f"from:{a}" for a in accounts[:2]])
    phr_part = " OR ".join(phrases[:2])
    tasks.append(f"{acc_part} {phr_part}")

    # 任务2: 后2个账号 + 后2个短语（如果还有）
    if len(accounts) > 2 and len(phrases) > 2:
        acc_part2 = " OR ".join([f"from:{a}" for a in accounts[2:4]])
        phr_part2 = " OR ".join(phrases[2:4])
        tasks.append(f"{acc_part2} {phr_part2}")

    return tasks[:2]


def _build_why(asset: str, regime: str, phrases: list) -> str:
    """生成路由理由（一句话）"""
    regime_label = MARKET_REGIMES.get(regime, {}).get("label", regime)
    asset_names = {
        "oil": "原油", "gold": "黄金", "fx": "外汇", "crypto": "加密货币",
        "equity": "股市", "macro": "宏观", "geopolitics": "地缘政治",
    }
    asset_cn = asset_names.get(asset, asset)
    top_phrase = phrases[0] if phrases else ""
    return f"当前{asset_cn}市场处于【{regime_label}】阶段，最关键变量：{top_phrase}"


# ============================================================
# 6. 极简输出
# ============================================================

def print_decision(result: dict):
    """极简打印决策结果"""
    print(f"  asset: {result['asset']}")
    print(f"  user_intent: {result['user_intent']}")
    print(f"  current_regime: {result['current_regime']}")
    print(f"  urgency: {result['urgency']}")
    print()
    print("  top_accounts:")
    for a in result['top_accounts']:
        print(f"    {a}")
    print()
    print("  top_event_phrases:")
    for p in result['top_event_phrases']:
        print(f"    {p}")
    print()
    print("  crawl_tasks:")
    for t in result['crawl_tasks']:
        print(f"    {t}")
    print()
    print(f"  why: {result['why_this_route']}")


# ============================================================
# 7. 测试
# ============================================================

if __name__ == "__main__":
    tests = [
        "油价会涨吗？",
        "黄金还能涨吗？",
        "日元要干预吗？",
        "BTC会不会拉升？",
        "美联储下周会不会降息？",
        "伊朗会不会封锁霍尔木兹海峡？",
        "特朗普关税对原油有什么影响？",
        "今天有什么突发事件影响市场？",
    ]

    print("抓取前极速决策器 - 测试")
    print("=" * 60)

    for q in tests:
        print(f"\n  输入: {q}")
        print("-" * 40)
        r = decide(q)
        print_decision(r)
        print()
