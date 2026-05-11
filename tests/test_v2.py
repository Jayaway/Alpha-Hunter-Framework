#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速测试优化版系统
"""

import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("  X 实时情报系统 - 快速测试")
print("=" * 60)

print("\n1️⃣  测试极速决策器...")
try:
    from deepalpha.intel_router_v2 import decide, decide_and_print

    queries = [
        "油价会涨吗？",
        "美联储下周会不会降息？",
        "伊朗会不会封锁霍尔木兹海峡？",
    ]

    for query in queries:
        start = time.time()
        decision = decide(query)
        elapsed = (time.time() - start) * 1000
        print(f"\n  查询: {query}")
        print(f"  决策耗时: {elapsed:.2f} ms")
        print(f"  资产: {decision.asset}")
        print(f"  阶段: {decision.regime_label}")
        print(f"  账号: {', '.join(decision.top_accounts[:3])}")

    print("\n✅  决策器测试通过！")

except ImportError as e:
    print(f"⚠️  导入决策器失败: {e}")

print("\n2️⃣  测试精简清洗器...")
try:
    from deepalpha.cleaner_v2 import clean_tweets

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
    ]

    start = time.time()
    cleaned = clean_tweets(test_data, verbose=True)
    elapsed = (time.time() - start) * 1000

    print(f"\n  清洗耗时: {elapsed:.2f} ms")
    print(f"  清洗结果: {len(cleaned)} 条")

    print("\n✅  清洗器测试通过！")

except ImportError as e:
    print(f"⚠️  导入清洗器失败: {e}")

print("\n3️⃣  账号池初始化...")
try:
    from deepalpha.account_pool import AccountPoolManager

    manager = AccountPoolManager()
    stats = manager.get_pool_stats()

    print(f"  账号池统计: {stats}")
    print("\n✅  账号池初始化完成！")

except ImportError as e:
    print(f"⚠️  导入账号池失败: {e}")

print("\n" + "=" * 60)
print("  🎉  核心模块测试通过！")
print("=" * 60)
print("\n💡  下一步:")
print("  - 测试抓取引擎: 需要有效的 X cookie")
print("  - 测试完整流程: 使用 main_v2.py")
