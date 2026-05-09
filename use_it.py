#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键使用指南 - 最简单的方式
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("  🎉  X 实时情报系统 - 一键使用")
print("=" * 60)

print("""
📌 选择使用方式：
------------------
1️⃣  方案一：只使用新版决策器（立即使用，最简单）
2️⃣  方案二：决策器 + 清洗器（推荐）
3️⃣  方案三：完整新版系统（需要 cookie）

输入 1、2 或 3 选择，或者 q 退出
""")

choice = input("\n请选择 (1/2/3/q): ").strip().lower()

if choice == "1":
    print("\n" + "=" * 60)
    print("  方案一：只使用新版决策器")
    print("=" * 60)

    from intel_router_v2 import decide, decide_and_print

    print("\n💡 这是最简单的方式，100x 更快！")
    print("\n代码示例:")
    print("""
    from intel_router_v2 import decide
    decision = decide("油价会涨吗？")
    print(f"推荐账号: {decision.top_accounts}")
    """)

    test_query = input("\n请输入您的问题 (直接回车用示例): ").strip()
    if not test_query:
        test_query = "油价会涨吗？"

    print(f"\n⏳  正在分析: {test_query}")
    start = time.time()
    decision = decide(test_query)
    elapsed = (time.time() - start) * 1000

    print(f"\n✅ 完成！耗时: {elapsed:.2f} ms\n")
    decide_and_print(test_query)

elif choice == "2":
    print("\n" + "=" * 60)
    print("  方案二：决策器 + 清洗器")
    print("=" * 60)

    from intel_router_v2 import decide
    from cleaner_v2 import clean_tweets

    print("\n💡 这个方案包含:")
    print("   - 极速决策器（100x 更快）")
    print("   - 精简清洗器（O(n)复杂度）")

    test_query = input("\n请输入您的问题 (直接回车用示例): ").strip()
    if not test_query:
        test_query = "美联储会不会降息？"

    print(f"\n⏳  正在分析: {test_query}")
    start = time.time()
    decision = decide(test_query)
    elapsed_decide = (time.time() - start) * 1000

    # 模拟一些推文用于清洗
    sample_tweets = [
        {
            "username": "@Reuters",
            "content": "BREAKING: Fed may cut rates in June if inflation cools",
            "likes": 4000,
            "is_verified": True,
        },
        {
            "username": "@DeItaone",
            "content": "Just in: Powell signals willingness to cut rates",
            "likes": 2500,
            "is_verified": True,
        },
        {
            "username": "@RandomUser",
            "content": "FED TO CUT RATES 1000% NOW!!! 🚀🚀🚀",
            "likes": 5,
            "is_verified": False,
        },
    ]

    print(f"\n🧹  正在清洗 {len(sample_tweets)} 条推文...")
    start = time.time()
    cleaned = clean_tweets(sample_tweets, verbose=False)
    elapsed_clean = (time.time() - start) * 1000

    print("\n" + "=" * 60)
    print("  📊 结果")
    print("=" * 60)

    print(f"\n决策器: {elapsed_decide:.2f} ms")
    print(f"清洗器: {elapsed_clean:.2f} ms")

    print(f"\n资产: {decision.asset}")
    print(f"阶段: {decision.regime_label}")
    print(f"推荐账号: {', '.join(decision.top_accounts[:3])}")

    print(f"\n清洗结果: {len(cleaned)} 条")
    actionable = [t for t in cleaned if t.verdict == "actionable"]
    noteworthy = [t for t in cleaned if t.verdict == "noteworthy"]

    print(f"  🟢 actionable: {len(actionable)}")
    print(f"  🟡 noteworthy: {len(noteworthy)}")

    if cleaned:
        print("\n" + "=" * 60)
        print("  📰 最佳结果:")
        print("=" * 60)
        top = cleaned[0]
        print(f"\n作者: @{top.username}")
        print(f"评分: {top.final_score}")
        print(f"裁决: {top.verdict}")
        print(f"内容: {top.content}")

elif choice == "3":
    print("\n" + "=" * 60)
    print("  方案三：完整新版系统")
    print("=" * 60)

    print("\n⚠️  注意:")
    print("   完整使用需要有效的 X cookie")
    print("   混合抓取引擎需要进一步完善 API 逆向")
    print("\n💡  建议:")
    print("   先使用方案一或方案二")

    # 测试系统初始化
    try:
        from main_v2 import XIntelSystem
        from account_pool import AccountPoolManager

        print("\n✅ 系统模块导入成功")

        pool = AccountPoolManager()
        stats = pool.get_pool_stats()
        print(f"账号池统计: {stats}")

        if stats['total'] == 0:
            print("\n💡 提示:")
            print("   您需要在 ./cookies/ 目录下放入有效的 cookie 文件")
            print("   可以先使用方案一或方案二")

    except Exception as e:
        print(f"\n❌ 系统初始化失败: {e}")

elif choice == "q" or choice == "quit":
    print("\n👋 再见！")
    sys.exit(0)

else:
    print("\n❌ 无效选择")
    print("请选择 1、2、3 或 q")

print("\n" + "=" * 60)
print("  📖  更多信息")
print("=" * 60)
print("""
快速参考文件:
  - test_v2.py: 完整核心模块测试
  - hybrid_example.py: 渐进式使用示例
  - QUICK_START_GUIDE.py: 完整指南

核心优化文件:
  - intel_router_v2.py: 极速决策器
  - cleaner_v2.py: 精简清洗器

完整优化:
  - account_pool.py: 账号池管理
  - hybrid_crawler.py: 混合抓取引擎
  - main_v2.py: 统一入口

	更多说明请参考项目文档。
	""")
