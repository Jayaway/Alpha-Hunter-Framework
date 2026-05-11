# -*- coding: utf-8 -*-
"""
X 实时情报系统 - 优化版主入口
================================================
整合所有优化后的组件，提供统一的 API：

新架构：
  1. hybrid_crawler.py     - 混合抓取引擎（异步HTTP + Playwright）
  2. account_pool.py       - 账号池管理 + 健康度监控
  3. cleaner_v2.py         - 精简清洗（3层核心）
  4. intel_router_v2.py    - 极速决策器 + LLM集成
  5. signal_judge.py       - 信号判断器
  6. ai_model.py          - AI 分析接口

使用方式：
  from deepalpha.main_v2 import XIntelSystem

  system = XIntelSystem()
  result = system.query("油价会涨吗？")
  print(result.summary())
"""

import os
import json
import time
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
import threading

from deepalpha.intel_router_v2 import IntelRouter, Decision
from deepalpha.hybrid_crawler import HybridCrawlerEngine, IdentityPoolManager, CrawlTask, Tweet
from deepalpha.cleaner_v2 import clean_tweets, CleanedTweet, quick_filter
from deepalpha.signal_judge import judge_all_signals, judge_signal
from deepalpha.ai_model import AIModel


# ============================================================
# 1. 结果模型
# ============================================================

@dataclass
class QueryResult:
    """查询结果"""
    query: str
    decision: Decision
    tweets_count: int
    cleaned_tweets: List[CleanedTweet]
    signal_judgment: dict
    execution_time: float

    actionable_count: int = 0
    noteworthy_count: int = 0

    def summary(self) -> str:
        """生成摘要"""
        lines = [
            "=" * 60,
            f"  X 实时情报查询报告",
            "=" * 60,
            f"  查询: {self.query}",
            f"  耗时: {self.execution_time:.2f} 秒",
            f"  资产: {self.decision.asset}",
            f"  阶段: {self.decision.regime_label}",
            f"  紧急度: {self.decision.urgency}",
            "",
            f"  抓取推文: {self.tweets_count} 条",
            f"  可行动情报: {self.actionable_count} 条",
            f"  值得关注: {self.noteworthy_count} 条",
            "",
            f"  推荐账号: {', '.join(self.decision.top_accounts[:3])}",
            f"  抓取任务: {self.decision.crawl_tasks}",
            "",
        ]

        if self.actionable_count > 0:
            lines.append("  🟢 高价值情报:")
            for t in self.cleaned_tweets[:3]:
                if t.verdict == "actionable":
                    lines.append(f"    • @{t.username}: {t.content[:50]}...")

        if self.signal_judgment.get("market_direction"):
            direction = self.signal_judgment["market_direction_label"] or ""
            confidence = self.signal_judgment["aggregate_confidence"]
            lines.append(f"\n  市场方向: {direction} (置信度: {confidence})")

        lines.append("=" * 60)
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """转字典"""
        return {
            "query": self.query,
            "decision": self.decision.to_dict(),
            "stats": {
                "tweets_count": self.tweets_count,
                "actionable_count": self.actionable_count,
                "noteworthy_count": self.noteworthy_count,
                "execution_time": self.execution_time,
            },
            "signal": self.signal_judgment,
            "top_tweets": [
                {
                    "username": t.username,
                    "content": t.content,
                    "score": t.final_score,
                    "verdict": t.verdict,
                    "direction": t.direction,
                }
                for t in self.cleaned_tweets[:10]
            ],
        }


# ============================================================
# 2. 核心系统
# ============================================================

class XIntelSystem:
    """
    X 实时情报系统（优化版）

    核心流程：
      1. 极速决策（<1ms）
      2. 混合抓取（异步并发）
      3. 精简清洗（3层核心）
      4. 信号判断（方向 + 影响）
      5. 可选 AI 分析

    性能目标：
      - 决策时间 < 1ms
      - 抓取时间 < 5秒
      - 清洗时间 < 100ms
      - 总时间 < 10秒
    """

    def __init__(
        self,
        cookie_file: str = "cookies/browser/x_cookie.json",
        use_llm: bool = False,
        llm_backend: str = "auto",
    ):
        self.cookie_file = cookie_file

        self.router = IntelRouter()

        self.ai_model = None
        if use_llm:
            self.ai_model = AIModel(backend=llm_backend)
            self.router.enable_llm(self.ai_model)

        self.crawler_engine = HybridCrawlerEngine()

        self.pool_manager = IdentityPoolManager()

        self._stats = {
            "queries": 0,
            "total_tweets": 0,
            "cache_hits": 0,
            "avg_execution_time": 0,
        }

        self._lock = threading.Lock()

    def query(
        self,
        query: str,
        max_tweets: int = 50,
        use_cache: bool = True,
        use_llm: bool = False,
        verbose: bool = True,
    ) -> QueryResult:
        """
        核心查询接口

        Args:
            query: 用户问题
            max_tweets: 最大抓取数量
            use_cache: 是否使用缓存
            use_llm: 是否使用 LLM 决策
            verbose: 是否打印详情

        Returns:
            QueryResult 对象
        """
        start_time = time.time()

        if verbose:
            print(f"\n{'=' * 60}")
            print(f"  X 实时情报系统 - 查询")
            print(f"{'=' * 60}")
            print(f"  查询: {query}")

        decision = self.router.decide(query, use_llm=use_llm)

        if verbose:
            print(f"  决策耗时: {(time.time() - start_time) * 1000:.1f} ms")
            print(f"  资产: {decision.asset}, 阶段: {decision.regime_label}")

        tweets = self._crawl(decision, max_tweets, use_cache, verbose)

        cleaned = clean_tweets([t.raw_data for t in tweets], verbose=False)

        actionable = [t for t in cleaned if t.verdict == "actionable"]
        noteworthy = [t for t in cleaned if t.verdict == "noteworthy"]

        signal = judge_all_signals(
            [
                {
                    "handle": t.username,
                    "content": t.content,
                    "likes": t.likes,
                    "verified": t.is_verified,
                }
                for t in cleaned[:20]
            ],
            asset=decision.asset,
        )

        execution_time = time.time() - start_time

        with self._lock:
            self._stats["queries"] += 1
            self._stats["total_tweets"] += len(tweets)
            self._stats["avg_execution_time"] = (
                self._stats["avg_execution_time"] * (self._stats["queries"] - 1) + execution_time
            ) / self._stats["queries"]

        result = QueryResult(
            query=query,
            decision=decision,
            tweets_count=len(tweets),
            cleaned_tweets=cleaned,
            signal_judgment=signal,
            execution_time=execution_time,
            actionable_count=len(actionable),
            noteworthy_count=len(noteworthy),
        )

        if verbose:
            print(f"\n{result.summary()}")

        return result

    def _crawl(
        self,
        decision: Decision,
        max_tweets: int,
        use_cache: bool,
        verbose: bool,
    ) -> List[Tweet]:
        """抓取推文"""
        tasks = []

        for username in decision.top_accounts[:5]:
            task = CrawlTask(
                task_id=f"profile_{username}",
                target_type="profile",
                target=username.lstrip("@"),
                limit=max(10, max_tweets // 5),
                priority=1 if decision.urgency == "critical" else 3,
            )
            tasks.append(task)

        for crawl_task in decision.crawl_tasks[:2]:
            task = CrawlTask(
                task_id=f"search_{crawl_task[:20]}",
                target_type="search",
                target=crawl_task,
                limit=max(20, max_tweets // 2),
                priority=2,
            )
            tasks.append(task)

        if verbose:
            print(f"\n  执行 {len(tasks)} 个抓取任务...")

        results = self.crawler_engine.crawl_batch(tasks)

        all_tweets = []
        for task_id, tweets in results.items():
            all_tweets.extend(tweets)

        if verbose:
            stats = self.crawler_engine.get_stats()
            print(f"  抓取完成: {len(all_tweets)} 条 (缓存命中: {stats['cache_hits']})")

        return all_tweets

    def quick_query(
        self,
        query: str,
        target: str,
        as_type: str = "profile",
    ) -> List[CleanedTweet]:
        """
        快速查询（跳过决策）

        适用于已知目标账号/关键词的场景
        """
        start_time = time.time()

        from deepalpha.hybrid_crawler import quick_crawl
        tweets = quick_crawl(target, limit=30, as_type=as_type)

        raw_data = [t.raw_data for t in tweets]
        cleaned = clean_tweets(raw_data, verbose=False)

        if verbose:
            print(f"\n  快速查询: {target}")
            print(f"  耗时: {time.time() - start_time:.2f}s")
            print(f"  获取: {len(cleaned)} 条")

        return cleaned

    def monitor_accounts(
        self,
        accounts: List[str],
        interval: int = 300,
    ) -> List[CleanedTweet]:
        """
        监控指定账号

        Args:
            accounts: 账号列表
            interval: 抓取间隔（秒）

        Returns:
            最新高价值推文
        """
        all_tweets = []

        for account in accounts:
            try:
                tweets = quick_crawl(account, limit=20, as_type="profile")
                all_tweets.extend(tweets)
            except Exception as e:
                print(f"  ⚠️ 监控 @{account} 失败: {e}")

        cleaned = clean_tweets(
            [t.raw_data for t in all_tweets],
            verbose=False,
        )

        return [t for t in cleaned if t.verdict in ["actionable", "noteworthy"]]

    def get_stats(self) -> dict:
        """获取系统统计"""
        return {
            **self._stats,
            "crawler_stats": self.crawler_engine.get_stats(),
            "pool_stats": self.pool_manager.get_pool_stats(),
            "cache_stats": self.router.get_cache_stats(),
        }

    def export_report(self, result: QueryResult, output_file: str = None):
        """导出报告"""
        if output_file is None:
            output_file = f"./reports/{datetime.now().strftime('%Y%m%d_%H%M%S')}_report.json"

        os.makedirs(os.path.dirname(output_file) or "./", exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2, default=str)

        print(f"  ✓ 报告已导出: {output_file}")


# ============================================================
# 3. 简化的使用接口
# ============================================================

_system: Optional[XIntelSystem] = None


def get_system(use_llm: bool = False) -> XIntelSystem:
    """获取全局系统实例"""
    global _system
    if _system is None:
        _system = XIntelSystem(use_llm=use_llm)
    return _system


def query(query: str, **kwargs) -> QueryResult:
    """
    快捷查询接口

    用法：
      result = query("油价会涨吗？")
      result = query("美联储会不会降息？", use_llm=True)
      result = query("伊朗会封锁霍尔木兹吗？", max_tweets=100)
    """
    system = get_system(use_llm=kwargs.get("use_llm", False))
    return system.query(query, **kwargs)


def quick_query(target: str, as_type: str = "profile") -> List[CleanedTweet]:
    """
    快速查询

    用法：
      tweets = quick_query("Reuters")
      tweets = quick_query("oil attack", as_type="search")
    """
    system = get_system()
    return system.quick_query("", target, as_type)


def monitor(accounts: List[str], interval: int = 300) -> List[CleanedTweet]:
    """
    监控账号

    用法：
      alerts = monitor(["@Reuters", "@JavierBlas", "@IDF"])
    """
    system = get_system()
    return system.monitor_accounts(accounts, interval)


# ============================================================
# 4. CLI 入口
# ============================================================

def main():
    """命令行入口"""
    import sys

    print("=" * 60)
    print("  X 实时情报系统 v2（优化版）")
    print("=" * 60)

    if len(sys.argv) > 1:
        query_text = " ".join(sys.argv[1:])
        use_llm = "--llm" in sys.argv
        max_tweets = 50

        if "--max" in sys.argv:
            idx = sys.argv.index("--max")
            max_tweets = int(sys.argv[idx + 1])

        result = query(query_text, use_llm=use_llm, max_tweets=max_tweets)

        if "--export" in sys.argv:
            export_path = "./reports/latest_report.json"
            result.system.export_report(result, export_path)
    else:
        print("\n  用法:")
        print("    python main_v2.py \"油价会涨吗？\"")
        print("    python main_v2.py \"美联储会不会降息？\" --llm")
        print("    python main_v2.py \"伊朗会封锁霍尔木兹吗？\" --max 100")
        print("\n  参数:")
        print("    --llm   使用 LLM 决策")
        print("    --max N 设置最大抓取数量")
        print("    --export 导出报告")


if __name__ == "__main__":
    main()
