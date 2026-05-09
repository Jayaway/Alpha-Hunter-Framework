#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X 实时情报系统（优化版）- 快速测试
直接运行：python test_optimized.py
"""

import subprocess
import sys

print("=" * 60)
print("  🎉 X 实时情报系统（优化版）- 快速测试")
print("=" * 60)

tests = [
    ("决策器测试（仅决策）", 'python run_v2.py "油价会涨吗？" --dry-run'),
    ("决策器 + 新清洗器（可选）", 'python run_v2.py "美联储会不会降息？" --dry-run --new-cleaner'),
]

for i, (desc, cmd) in enumerate(tests, 1):
    print(f"\n{i}. {desc}")
    print("-" * 60)
    try:
        subprocess.run(cmd, shell=True, cwd="/Users/vv/Desktop/Alpha 改版")
    except KeyboardInterrupt:
        print("\n跳过...")
        continue

print("\n" + "=" * 60)
print("  ✅ 测试完成！")
print("=" * 60)
print("\n快速开始：")
print("  1. 使用优化版（推荐）:")
print("     python run_v2.py \"你的问题\" --dry-run")
print("     python run_v2.py \"你的问题\" --crawl")
print("\n  2. 开启新版清洗器（可选）:")
print("     python run_v2.py \"你的问题\" --crawl --new-cleaner")
print("\n  3. 使用旧版（完全兼容）:")
print("     python run.py \"你的问题\"")
