# -*- coding: utf-8 -*-
"""
X 实时情报系统 - 极速决策器 v2（优化版）
================================================
优化点：
  1. 预编译正则匹配，决策速度提升 10x
  2. 缓存机制，相同查询不重复计算
  3. 可选 LLM 决策（复杂意图理解）
  4. 1秒内给出抓取任务

使用方式：
  from intel_router_v2 import decide, decide_with_cache

  # 快速规则匹配（<1ms）
  result = decide("油价会涨吗？")

  # 带 LLM 的决策（复杂场景）
  result = decide("今天下午美联储会不会突然宣布降息？", use_llm=True)
"""

import re
import hashlib
import time
import json
import random
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from functools import lru_cache
from dataclasses import dataclass, field

from x_intel_rules import S_LEVEL, A_LEVEL


# ============================================================
# 1. 预编译正则（提升匹配速度）
# ============================================================

ASSET_PATTERNS_V2 = {
    "oil": {
        "zh": re.compile(r'油价|原油|石油|布伦特|WTI|OPEC|欧佩克|能源|汽油|天然气|LNG|油轮|炼油|霍尔木兹|红海|航运|海峡'),
        "en": re.compile(r'\boil\b|\bcrude\b|\bbrent\b|\bwti\b|\bopec\b|\bpetroleum\b|\bhormuz\b|\btanker\b|\bshipping\b|\bred sea\b', re.I),
    },
    "gold": {
        "zh": re.compile(r'黄金|金价|贵金属|白银|银价|避险'),
        "en": re.compile(r'\bgold\b|\bxau\b|\bsilver\b|\bxag\b|\bprecious metal\b', re.I),
    },
    "fx": {
        "zh": re.compile(r'外汇|汇率|美元|欧元|日元|人民币|英镑|USD|EUR|JPY|CNY|DXY|干预'),
        "en": re.compile(r'\bforex\b|\bfx\b|\bdollar\b|\beuro\b|\byen\b|\bdxy\b', re.I),
    },
    "crypto": {
        "zh": re.compile(r'比特币|BTC|以太坊|ETH|加密|币|区块链'),
        "en": re.compile(r'\bbitcoin\b|\bbtc\b|\bethereum\b|\bcrypto\b|\bblockchain\b', re.I),
    },
    "equity": {
        "zh": re.compile(r'股市|美股|A股|港股|标普|纳斯达克|股指'),
        "en": re.compile(r'\bstock\b|\bequity\b|\bs&p\b|\bsp500\b|\bnasdaq\b', re.I),
    },
    "macro": {
        "zh": re.compile(r'经济|通胀|CPI|PCE|非农|GDP|PMI|衰退|加息|降息|利率|美联储|鲍威尔'),
        "en": re.compile(r'\beconomy\b|\binflation\b|\bcpi\b|\bpce\b|\bnonfarm\b|\bgdp\b|\bpmi\b|\bfed\b|\brate\b', re.I),
    },
    "geopolitics": {
        "zh": re.compile(r'战争|冲突|地缘|制裁|伊朗|乌克兰|以色列|导弹|霍尔木兹|红海|停火|军事|核'),
        "en": re.compile(r'\bwar\b|\bconflict\b|\bgeopolitic\b|\bsanction\b|\biran\b|\bukraine\b|\bisrael\b|\bmissile\b', re.I),
    },
}

REGIME_PATTERNS_V2 = {
    "supply_risk": {
        "label": "供给驱动",
        "zh": re.compile(r'霍尔木兹|封锁|制裁|OPEC|减产|增产|停产|断供|油轮|管道|炼油|库存|产量|供应'),
        "en": re.compile(r'hormuz|blockade|sanction|opec|cut|output|supply|disruption|tanker|pipeline|refinery', re.I),
    },
    "demand_risk": {
        "label": "需求驱动",
        "zh": re.compile(r'需求|消费|衰退|经济|GDP|PMI|中国|印度|进口|炼厂|开工率'),
        "en": re.compile(r'demand|consumption|recession|gdp|pmi|china|india|import|refinery|utilization', re.I),
    },
    "policy_risk": {
        "label": "政策驱动",
        "zh": re.compile(r'美联储|降息|加息|利率|关税|特朗普|鲍威尔|央行|QE|缩表|财政|行政令'),
        "en": re.compile(r'fed|rate cut|rate hike|tariff|trump|powell|central bank|policy', re.I),
    },
    "war_risk": {
        "label": "战争驱动",
        "zh": re.compile(r'战争|冲突|导弹|袭击|入侵|停火|军事|以色列|伊朗|乌克兰|俄罗斯|核|胡塞|真主党|哈马斯|红海|中东'),
        "en": re.compile(r'war|missile|attack|invasion|ceasefire|military|israel|iran|ukraine|russia|nuclear|houthis|hezbollah|hamas', re.I),
    },
}

URGENCY_PATTERNS = {
    "critical": re.compile(r'突发|刚刚|breaking|just in|urgent|现在|马上|happening|right now|alert', re.I),
    "high": re.compile(r'今天|今晚|明天|today|tonight|soon|即将|imminent', re.I),
}

ACCOUNT_REGIME_ACCOUNTS_V2 = {
    "oil": {
        "supply_risk": ["@JavierBlas", "@Reuters", "@KSAmofaEN", "@TankersTrackers", "@realDonaldTrump"],
        "demand_risk": ["@JKempEnergy", "@Reuters", "@charliebilello", "@narendramodi", "@DeItaone"],
        "policy_risk": ["@realDonaldTrump", "@Reuters", "@DeItaone", "@KSAmofaEN", "@JavierBlas"],
        "war_risk": ["@IDF", "@Conflicts", "@Reuters", "@RichardEngel", "@samdagher"],
        "default": ["@JavierBlas", "@Reuters", "@DeItaone", "@KSAmofaEN", "@realDonaldTrump"],
    },
    "gold": {
        "policy_risk": ["@federalreserve", "@DeItaone", "@Reuters", "@charliebilello", "@elerianm"],
        "war_risk": ["@Conflicts", "@IDF", "@Reuters", "@RichardEngel", "@DeItaone"],
        "default": ["@federalreserve", "@DeItaone", "@Reuters", "@Conflicts", "@charliebilello"],
    },
    "fx": {
        "policy_risk": ["@federalreserve", "@DeItaone", "@Reuters", "@charliebilello", "@realDonaldTrump"],
        "dollar_risk": ["@DeItaone", "@Reuters", "@alaidi", "@federalreserve", "@realDonaldTrump"],
        "default": ["@federalreserve", "@DeItaone", "@Reuters", "@charliebilello", "@realDonaldTrump"],
    },
    "crypto": {
        "policy_risk": ["@DeItaone", "@Reuters", "@CathieDWood", "@ZeroHedge", "@federalreserve"],
        "risk_sentiment": ["@DeItaone", "@CathieDWood", "@Reuters", "@ZeroHedge", "@howardlindzon"],
        "default": ["@DeItaone", "@ZeroHedge", "@federalreserve", "@Reuters", "@CathieDWood"],
    },
    "equity": {
        "policy_risk": ["@federalreserve", "@DeItaone", "@realDonaldTrump", "@Reuters", "@charliebilello"],
        "risk_sentiment": ["@DeItaone", "@Conflicts", "@Reuters", "@charliebilello", "@ZeroHedge"],
        "default": ["@federalreserve", "@DeItaone", "@realDonaldTrump", "@Reuters", "@charliebilello"],
    },
    "macro": {
        "policy_risk": ["@federalreserve", "@DeItaone", "@realDonaldTrump", "@Reuters", "@charliebilello"],
        "demand_risk": ["@DeItaone", "@charliebilello", "@Reuters", "@ZeroHedge", "@Bloomberg"],
        "default": ["@federalreserve", "@DeItaone", "@realDonaldTrump", "@Reuters", "@charliebilello"],
    },
    "geopolitics": {
        "war_risk": ["@IDF", "@Conflicts", "@Reuters", "@RichardEngel", "@samdagher"],
        "policy_risk": ["@realDonaldTrump", "@Reuters", "@DeItaone", "@JackDetsch", "@SangerNYT"],
        "default": ["@IDF", "@Conflicts", "@Reuters", "@RichardEngel", "@samdagher"],
    },
}


# ============================================================
# 2. 决策结果模型
# ============================================================

@dataclass
class Decision:
    """决策结果"""
    asset: str
    regime: str
    regime_label: str
    urgency: str
    top_accounts: List[str]
    crawl_tasks: List[str]
    why: str
    cached: bool = False
    candidate_accounts: List[str] = field(default_factory=list)
    selected_accounts: List[str] = field(default_factory=list)
    excluded_accounts: List[dict] = field(default_factory=list)
    account_selection_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "asset": self.asset,
            "user_intent": self.regime_label,
            "current_regime": self.regime,
            "urgency": self.urgency,
            "top_accounts": self.top_accounts,
            "top_event_phrases": [],  # 兼容旧版
            "crawl_tasks": self.crawl_tasks,
            "why_this_route": self.why,
            "cached": self.cached,
            "candidate_accounts": self.candidate_accounts,
            "selected_accounts": self.selected_accounts or self.top_accounts,
            "excluded_accounts": self.excluded_accounts,
            "account_selection_reason": self.account_selection_reason,
        }


# ============================================================
# 3. 极速决策引擎
# ============================================================

class IntelRouter:
    """
    极速决策器

    核心优化：
      - 预编译正则匹配
      - 缓存机制
      - 简化决策路径
      - < 1ms 响应时间
    """

    def __init__(self):
        self._cache: Dict[str, tuple] = {}
        self._cache_ttl = 60
        self._llm_enabled = False
        self._llm_model = None

    def enable_llm(self, model: Any):
        """启用 LLM 决策"""
        self._llm_enabled = True
        self._llm_model = model

    def disable_llm(self):
        """禁用 LLM 决策"""
        self._llm_enabled = False
        self._llm_model = None

    def decide(self, query: str, use_llm: bool = False) -> Decision:
        """
        极速决策

        Args:
            query: 用户问题
            use_llm: 是否使用 LLM 决策

        Returns:
            Decision 对象
        """
        start_time = time.time()

        query_lower = query.lower()
        use_cache = self._detect_asset_fast(query_lower) != "oil"

        cache_key = hashlib.md5(query_lower.encode()).hexdigest()[:16]
        if use_cache and cache_key in self._cache:
            cached_data, cached_time = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                cached_data.cached = True
                return cached_data

        if use_llm and self._llm_enabled:
            decision = self._decide_with_llm(query)
        else:
            decision = self._decide_fast(query_lower)

        if use_cache:
            self._cache[cache_key] = (decision, time.time())

        if use_cache and len(self._cache) > 100:
            oldest = min(self._cache.items(), key=lambda x: x[1][1])
            del self._cache[oldest[0]]

        return decision

    def _decide_fast(self, query: str) -> Decision:
        """快速规则匹配（<1ms）"""
        asset = self._detect_asset_fast(query)
        regime, regime_label = self._detect_regime_fast(query, asset)
        urgency = self._detect_urgency_fast(query)
        selection = self._select_accounts(asset, regime, query)
        accounts = selection["selected_accounts"]
        crawl_tasks = self._build_crawl_tasks(accounts)

        why = f"当前{self._asset_name(asset)}市场处于【{regime_label}】阶段"

        return Decision(
            asset=asset,
            regime=regime,
            regime_label=regime_label,
            urgency=urgency,
            top_accounts=accounts,
            crawl_tasks=crawl_tasks,
            why=why,
            candidate_accounts=selection["candidate_accounts"],
            selected_accounts=selection["selected_accounts"],
            excluded_accounts=selection["excluded_accounts"],
            account_selection_reason=selection["account_selection_reason"],
        )

    def _decide_with_llm(self, query: str) -> Decision:
        """LLM 决策（复杂意图理解）"""
        try:
            prompt = f"""分析用户问题，输出 JSON：

问题: {query}

输出格式:
{{
    "asset": "oil|gold|fx|crypto|equity|macro|geopolitics",
    "regime": "supply_risk|demand_risk|policy_risk|war_risk|dollar_risk",
    "urgency": "critical|high|normal",
    "top_accounts": ["@账号1", "@账号2", "@账号3"],
    "crawl_tasks": ["搜索语句1", "搜索语句2"],
    "why": "一句话理由"
}}"""

            result = self._llm_model.chat_json(prompt, temperature=0.3)

            if "error" not in result:
                return Decision(
                    asset=result.get("asset", "macro"),
                    regime=result.get("regime", "policy_risk"),
                    regime_label=self._get_regime_label(result.get("regime", "policy_risk")),
                    urgency=result.get("urgency", "normal"),
                    top_accounts=result.get("top_accounts", [])[:5],
                    crawl_tasks=result.get("crawl_tasks", [])[:2],
                    why=result.get("why", ""),
                )

        except Exception:
            pass

        return self._decide_fast(query.lower())

    def _detect_asset_fast(self, query: str) -> str:
        """快速资产识别"""
        scores = {}
        for asset, patterns in ASSET_PATTERNS_V2.items():
            score = 0
            if patterns["zh"].search(query):
                score += 2
            if patterns["en"].search(query):
                score += 1
            if score > 0:
                scores[asset] = score

        if scores:
            return max(scores, key=scores.get)
        return "macro"

    def _detect_regime_fast(self, query: str, asset: str) -> tuple:
        """快速市场阶段识别"""
        scores = {}
        for regime, patterns in REGIME_PATTERNS_V2.items():
            score = 0
            if patterns.get("zh") and patterns["zh"].search(query):
                score += 2
            if patterns.get("en") and patterns["en"].search(query):
                score += 1
            if score > 0:
                scores[regime] = score

        if scores:
            regime = max(scores, key=scores.get)
            return regime, REGIME_PATTERNS_V2[regime]["label"]

        default_regimes = {
            "oil": "supply_risk",
            "gold": "policy_risk",
            "fx": "policy_risk",
            "crypto": "risk_sentiment",
            "equity": "risk_sentiment",
            "macro": "policy_risk",
            "geopolitics": "war_risk",
        }
        regime = default_regimes.get(asset, "policy_risk")
        return regime, REGIME_PATTERNS_V2[regime]["label"]

    def _detect_urgency_fast(self, query: str) -> str:
        """快速紧急度识别"""
        if URGENCY_PATTERNS["critical"].search(query):
            return "critical"
        if URGENCY_PATTERNS["high"].search(query):
            return "high"
        return "normal"

    def _pick_accounts_fast(self, asset: str, regime: str) -> List[str]:
        """快速选择账号"""
        pool = ACCOUNT_REGIME_ACCOUNTS_V2.get(asset, {}).get(regime)
        if not pool:
            pool = ACCOUNT_REGIME_ACCOUNTS_V2.get(asset, {}).get("default")
        if not pool:
            pool = ["@Reuters", "@Bloomberg", "@DeItaone", "@JavierBlas", "@realDonaldTrump"]
        return pool[:5]

    def _select_accounts(self, asset: str, regime: str, query: str) -> dict:
        if asset != "oil":
            accounts = self._pick_accounts_fast(asset, regime)
            return {
                "candidate_accounts": accounts,
                "selected_accounts": accounts,
                "excluded_accounts": [],
                "account_selection_reason": "non-oil asset uses existing fixed account route",
            }

        try:
            return self._select_oil_accounts_dynamic(regime, query)
        except Exception as exc:
            fallback = self._pick_accounts_fast(asset, regime)
            return {
                "candidate_accounts": fallback,
                "selected_accounts": fallback,
                "excluded_accounts": [{"reason": f"dynamic_selection_failed: {exc}"}],
                "account_selection_reason": "dynamic oil account selection failed; fallback to existing top_accounts",
            }

    def _select_oil_accounts_dynamic(self, regime: str, query: str) -> dict:
        from account_status import load_account_status, save_account_status
        from oil_intent_classifier import classify_oil_intent
        from x_intel_rules import get_accounts_by_group, get_accounts_by_level

        status = load_account_status()
        oil_intent = classify_oil_intent(query).get("oil_intent", "general_risk")

        core_pool = self._dedupe_accounts(
            get_accounts_by_level("S")
            + ACCOUNT_REGIME_ACCOUNTS_V2.get("oil", {}).get("default", [])
        )
        scenario_pool = self._oil_scenario_pool(oil_intent, regime)
        exploration_pool = self._dedupe_accounts(
            get_accounts_by_level("B")
            + get_accounts_by_level("C")
            + get_accounts_by_group("oil")
        )

        candidate_accounts = self._dedupe_accounts(core_pool + scenario_pool + exploration_pool)
        excluded_accounts = []
        available_core = self._filter_runtime_available(core_pool, status, excluded_accounts)
        available_scenario = self._filter_runtime_available(scenario_pool, status, excluded_accounts)
        available_exploration = self._filter_runtime_available(exploration_pool, status, excluded_accounts)

        selected = []
        selected.extend(self._sample_accounts(available_core, min_count=1, max_count=2))
        selected.extend(self._sample_accounts(available_scenario, min_count=2, max_count=3))
        selected.extend(self._sample_accounts(available_exploration, min_count=1, max_count=2))
        selected = self._dedupe_accounts(selected)[:5]

        if len(selected) < 3:
            fallback = self._filter_runtime_available(
                self._pick_accounts_fast("oil", regime),
                status,
                excluded_accounts,
            )
            selected = self._dedupe_accounts(selected + fallback)[:5]

        if not selected:
            selected = self._pick_accounts_fast("oil", regime)

        if excluded_accounts:
            save_account_status(status)

        reason = (
            f"dynamic oil selection: oil_intent={oil_intent}, regime={regime}; "
            "core_accounts=1-2, scenario_accounts=2-3, exploration_accounts=1-2; "
            "accounts with fail_count>=3 excluded as inactive"
        )
        return {
            "candidate_accounts": candidate_accounts,
            "selected_accounts": selected,
            "excluded_accounts": excluded_accounts,
            "account_selection_reason": reason,
        }

    def _oil_scenario_pool(self, oil_intent: str, regime: str) -> List[str]:
        from x_intel_rules import get_accounts_by_group, get_accounts_by_level

        pools = {
            "shipping_risk": get_accounts_by_group("oil") + get_accounts_by_group("geopolitics"),
            "geopolitics": get_accounts_by_group("geopolitics") + get_accounts_by_group("journalist"),
            "opec_policy": get_accounts_by_group("leaders") + get_accounts_by_group("oil"),
            "inventory_macro": get_accounts_by_group("oil") + get_accounts_by_group("macro"),
            "price_direction": get_accounts_by_group("oil") + get_accounts_by_level("A"),
            "general_risk": get_accounts_by_level("S") + get_accounts_by_group("oil"),
        }
        pool = pools.get(oil_intent, pools["general_risk"])
        if regime == "war_risk":
            pool = get_accounts_by_group("geopolitics") + pool
        elif regime == "demand_risk":
            pool = get_accounts_by_group("macro") + pool
        elif regime == "policy_risk":
            pool = get_accounts_by_group("leaders") + pool
        return self._dedupe_accounts(pool)

    def _filter_runtime_available(self, accounts: List[str], status: dict, excluded: list) -> List[str]:
        available = []
        for account in accounts:
            handle = self._normalize_account(account)
            runtime = status.get(handle, {})
            fail_count = int(runtime.get("fail_count", 0) or 0)
            if fail_count >= 3:
                runtime["last_status"] = runtime.get("last_status") or "inactive"
                if runtime["last_status"] not in {"inactive", "cooldown"}:
                    runtime["last_status"] = "inactive"
                status[handle] = runtime
                excluded.append({
                    "handle": handle,
                    "reason": "fail_count>=3",
                    "last_status": runtime.get("last_status"),
                    "fail_count": fail_count,
                })
                continue
            available.append(handle)
        return self._dedupe_accounts(available)

    def _sample_accounts(self, accounts: List[str], min_count: int, max_count: int) -> List[str]:
        accounts = self._dedupe_accounts(accounts)
        if not accounts:
            return []
        count = random.randint(min_count, max_count)
        count = min(count, len(accounts))
        return random.sample(accounts, count)

    def _dedupe_accounts(self, accounts: List[str]) -> List[str]:
        result = []
        seen = set()
        for account in accounts:
            handle = self._normalize_account(account)
            if not handle or handle.lower() in seen:
                continue
            seen.add(handle.lower())
            result.append(handle)
        return result

    def _normalize_account(self, account: str) -> str:
        text = str(account or "").strip()
        if not text:
            return ""
        if not text.startswith("@"):
            text = f"@{text}"
        return text

    def _build_crawl_tasks(self, accounts: List[str]) -> List[str]:
        """构建抓取任务"""
        tasks = []

        if len(accounts) >= 2:
            acc_part = " OR ".join([f"from:{a}" for a in accounts[:2]])
            tasks.append(acc_part)

        if len(accounts) >= 4:
            acc_part2 = " OR ".join([f"from:{a}" for a in accounts[2:4]])
            tasks.append(acc_part2)

        return tasks[:2]

    def _asset_name(self, asset: str) -> str:
        """资产名称映射"""
        names = {
            "oil": "原油", "gold": "黄金", "fx": "外汇", "crypto": "加密货币",
            "equity": "股市", "macro": "宏观", "geopolitics": "地缘政治",
        }
        return names.get(asset, asset)

    def _get_regime_label(self, regime: str) -> str:
        """获取阶段标签"""
        return REGIME_PATTERNS_V2.get(regime, {}).get("label", regime)

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()

    def get_cache_stats(self) -> dict:
        """获取缓存统计"""
        return {
            "cache_size": len(self._cache),
            "cache_ttl": self._cache_ttl,
        }


# ============================================================
# 4. 全局实例
# ============================================================

_router: Optional[IntelRouter] = None


def get_router() -> IntelRouter:
    """获取全局决策器"""
    global _router
    if _router is None:
        _router = IntelRouter()
    return _router


def decide(query: str, use_llm: bool = False) -> Decision:
    """
    快捷决策函数

    用法：
      result = decide("油价会涨吗？")
      result = decide("美联储会不会降息？", use_llm=True)
    """
    return get_router().decide(query, use_llm)


def decide_and_print(query: str, use_llm: bool = False):
    """决策并打印"""
    decision = decide(query, use_llm)

    print(f"\n  极速决策结果 {'(缓存)' if decision.cached else ''}")
    print("=" * 60)
    print(f"  资产: {decision.asset}")
    print(f"  阶段: {decision.regime_label}")
    print(f"  紧急度: {decision.urgency}")
    print(f"  账号: {', '.join(decision.top_accounts[:3])}")
    print(f"  任务: {decision.crawl_tasks}")
    print(f"  理由: {decision.why}")
    print("=" * 60)

    return decision


# ============================================================
# 5. 性能测试
# ============================================================

def benchmark():
    """性能测试"""
    import timeit

    router = IntelRouter()

    test_queries = [
        "油价会涨吗？",
        "黄金还能涨吗？",
        "美联储下周会不会降息？",
        "伊朗会不会封锁霍尔木兹海峡？",
        "BTC会不会拉升？",
    ]

    print("=" * 60)
    print("  极速决策器 - 性能测试")
    print("=" * 60)

    for query in test_queries:
        time_taken = timeit.timeit(
            lambda: router.decide(query),
            number=1000
        )
        avg_ms = (time_taken / 1000) * 1000

        result = router.decide(query)
        print(f"\n  查询: {query}")
        print(f"    平均耗时: {avg_ms:.3f} ms")
        print(f"    资产: {result.asset}")
        print(f"    账号: {', '.join(result.top_accounts[:3])}")


if __name__ == "__main__":
    print("=" * 60)
    print("  极速决策器 v2 - 测试")
    print("=" * 60)

    queries = [
        "油价会涨吗？",
        "黄金还能涨吗？",
        "美联储下周会不会降息？",
        "日元要干预吗？",
        "BTC会不会拉升？",
        "伊朗会不会封锁霍尔木兹海峡？",
        "今天有什么突发事件影响市场？",
    ]

    router = get_router()

    for query in queries:
        decide_and_print(query)

    print("\n" + "=" * 60)
    print("  性能测试")
    print("=" * 60)
    benchmark()

    print("\n" + "=" * 60)
    print("  缓存统计")
    print("=" * 60)
    print(f"  {router.get_cache_stats()}")
