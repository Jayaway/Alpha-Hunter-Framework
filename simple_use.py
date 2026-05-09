#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最简单的使用示例
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("  X 实时情报系统 - 使用示例")
print("=" * 60)

print("\n📌  最简单的使用方式:")
print("=" * 60)
print("\n1️⃣  只用新版决策器 (最快):")
print("--------------------------")

from intel_router_v2 import decide

query = "油价会涨吗？"
print(f"\n问题: {query}")

start = time.time()
decision = decide(query)
elapsed = (time.time() - start) * 1000

print(f"✅ 决策完成！耗时: {elapsed:.2f} ms\n")
print(f"资产: {decision.asset}")
print(f"阶段: {decision.regime_label}")
print(f"推荐账号: {', '.join(decision.top_accounts)}")
print(f"抓取任务: {decision.crawl_tasks}")

print("\n" + "=" * 60)
print("\n2️⃣  决策器 + 清洗器 (推荐):")
print("--------------------------")

from cleaner_v2 import clean_tweets

# 模拟一些推文
tweets = [
    {
        "username": "@Reuters",
        "content": "BREAKING: OPEC+ agrees to cut production",
        "likes": 5000,
        "is_verified": True,
    },
    {
        "username": "@JavierBlas",
        "content": "Saudi Arabia announces voluntary cut",
        "likes": 3000,
        "is_verified": True,
    },
]

print(f"\n清洗 {len(tweets)} 条推文...")
start = time.time()
cleaned = clean_tweets(tweets, verbose=True)
elapsed = (time.time() - start) * 1000

print(f"\n✅ 清洗完成！耗时: {elapsed:.2f} ms")
print(f"\n结果: {len(cleaned)} 条推文")

print("\n" + "=" * 60)
print("\n💡  如何在您的代码中使用:")
print("=" * 60)
print("""
只需替换这一行:

# 旧版
# from intel_router import decide

# 新版 (100x 更快)
from intel_router_v2 import decide

其他代码完全不变！
""")

print("\n" + "=" * 60)
print("\n📁  所有文件:")
print("=" * 60)
files = [
    ("use_it.py", "本文件（运行看看！）"),
    ("test_v2.py", "核心模块测试"),
    ("hybrid_example.py", "渐进式使用示例"),
    ("QUICK_START_GUIDE.py", "完整指南"),
    ("intel_router_v2.py", "✅ 极速决策器（推荐先用！）"),
    ("cleaner_v2.py", "✅ 精简清洗器（推荐先用！）"),
    ("account_pool.py", "⏳ 账号池管理"),
    ("hybrid_crawler.py", "⏳ 混合抓取引擎"),
    ("main_v2.py", "📦 统一入口"),
]
for file, desc in files:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), file)
    if os.path.exists(path):
        status = "✅" if file in ["intel_router_v2.py", "cleaner_v2.py"] else ""
        print(f"{status} {file:<30} - {desc}")

print("\n" + "=" * 60)
print("\n🎯  下一步建议:")
print("=" * 60)
print("""
✅ 今天就能用的:
   1. 打开您的现有代码
   2. 找到 import intel_router 的地方
   3. 替换为 intel_router_v2
   4. 保存运行！

⏳ 后续优化:
   - 同样可以替换 data_cleaner 为 cleaner_v2
   - 等准备好后再切换完整新架构
""")

print("\n" + "=" * 60)
print("\n💡  想看看其他测试？运行:")
print("=" * 60)
print("""
python test_v2.py          # 完整核心模块测试
python hybrid_example.py  # 渐进式使用示例
python QUICK_START_GUIDE.py  # 完整指南
""")
