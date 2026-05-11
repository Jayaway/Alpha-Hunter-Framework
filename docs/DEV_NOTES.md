# DEV_NOTES

更新时间：2026-05-08

这份文档用于给 DeepAlpha 后续开发定主线。当前目标是让项目结构清楚：源码进入主线，运行产物保持可再生成并排除在版本库之外。

## 1. 当前主链路

当前推荐主入口是：

```bash
python run_v2.py "油价会涨吗？"
```

实时抓取时使用：

```bash
python run_v2.py "油价会涨吗？" --crawl
```

当前主链路：

```text
run_v2.py
  -> intel_router_v2.py
  -> x_intel_rules.py
  -> crawler_runner.py
  -> scraper/twitter_scraper.py
  -> 抓取的信息/*.csv
  -> graph_engine.py
  -> cleaner_v2.py 或 data_cleaner.py
  -> signal_judge.py
```

说明：

- `run_v2.py` 是当前推荐 CLI。
- `intel_router_v2.py` 做新版快速决策。
- `x_intel_rules.py` 是账号、关键词、领域规则来源。
- `crawler_runner.py` 是主链路抓取执行器。
- `scraper/` 是底层 Selenium 爬虫，本轮不改。
- `cleaner_v2.py` 通过 `--new-cleaner` 使用。
- `data_cleaner.py` 继续作为兼容清洗器。
- `signal_judge.py` 是统一信号判断层。

## 2. 可选链路

### 兼容入口

`run.py` 保留为兼容入口：

```bash
python run.py "油价会涨吗？"
python run.py "油价会涨吗？" --crawl
```

它主要用于对照和兜底，不作为后续新功能优先接入点。

### 历史库分析

不传 `--crawl` 时，`run_v2.py` 会优先走历史库分析：

```text
run_v2.py
  -> intel_router_v2.py
  -> intel_analyzer.py
  -> graph_engine.load_tweets_from_csv_dir()
  -> signal_judge.py
```

历史库默认目录：

```text
./抓取的信息/
```

### 独立底层爬虫

底层 scraper 可独立使用：

```bash
python -m scraper --query="oil OPEC" -t 20
python -m scraper -u Reuters -t 20
```

这条链路用于单独验证抓取能力，不是 DeepAlpha 推荐分析入口。

### 图谱链路

```text
graph_engine.py
  -> graph_data/关系图谱.json
  -> graph_viewer.py
```

图谱是主链路的输出辅助，不应反向承担抓取或清洗职责。

## 3. 实验文件

以下文件当前保留，但暂时不作为主链路：

| 文件 | 当前定位 | 注意事项 |
| --- | --- | --- |
| `main_v2.py` | 优化版 API/统一入口实验 | 不作为推荐 CLI；后续如要启用，需要先修已知接线问题。 |
| `hybrid_crawler.py` | HTTP/curl_cffi + Playwright 抓取实验 | 暂不替换 `crawler_runner.py`；不要默认接入主流程。 |
| `account_pool.py` | 多账号、健康度、频控实验 | 暂不接入主抓取链路。 |
| `filter.py` | 早期 CSV 统计脚本 | 不属于当前主流程。 |
| `filter_level1.py` | 早期第一级过滤脚本 | 可参考规则，但不接主流程。 |
| `obsidian_graph.py` | Obsidian 图谱输出方案 | 当前主图谱使用 `graph_engine.py`。 |
| `simple_use.py` | 示例脚本 | 保留演示用。 |
| `hybrid_example.py` | 混合架构示例 | 保留演示用，不代表主链路。 |
| `test_v2.py` | 测试脚本 | 可用于验证核心模块。 |
| `test_optimized.py` | 测试脚本 | 可用于验证 `run_v2.py` 命令。 |
| `use_it.py` | 使用演示 | 不属于主链路。 |
| `QUICK_START_GUIDE.py` | 打印式说明脚本 | 文档性质。 |
| `OPTIMIZATION_SUMMARY.py` | 优化总结 | 文档性质。 |

实验文件不删除，是为了保留上下文和后续迁移可能。但新增功能时不要默认从这些文件开始，除非任务明确是“接入实验版抓取/账号池”。

## 4. 后续定时监听模块位置

后续新增“定时情报监听模块”时，建议做成新的编排层，而不是改底层爬虫。

推荐新增：

```text
intel_monitor.py
```

推荐链路：

```text
intel_monitor.py
  -> 读取监听配置
  -> intel_router_v2.py
  -> x_intel_rules.py
  -> crawler_runner.py
  -> crawler_runner.save_results()
  -> cleaner_v2.py
  -> signal_judge.py
  -> graph_engine.py
  -> graph_data/monitor_state.json
```

模块边界建议：

- 监听模块负责：调度、状态、去重、调用现有能力、输出告警候选。
- `intel_router_v2.py` 负责：根据问题/主题生成抓取方向。
- `x_intel_rules.py` 负责：账号、关键词、优先级规则。
- `crawler_runner.py` 负责：执行真实抓取。
- `cleaner_v2.py` 负责：实时清洗。
- `signal_judge.py` 负责：信号判断。
- `graph_engine.py` 负责：图谱更新。

已有的 `scheduled_crawler.py` 可以作为低频刷新脚本继续保留，也可以作为未来监听调度器的参考。但不建议把所有监听逻辑直接塞进它；更清晰的方式是让它只做调度，或新增 `intel_monitor.py` 作为专门模块。

## 5. 当前不要做的事

- 不删除 Python 文件。
- 不改 `scraper/` 底层爬虫。
- 不把 `main_v2.py` 设为推荐入口。
- 不把 `hybrid_crawler.py` 替换进当前主抓取链路。
- 不把 `account_pool.py` 默认接入当前抓取链路。
- 不在监听模块中重复实现抓取、清洗、信号判断。

## 6. 判断标准

后续新增代码时，优先问这几个问题：

1. 新代码是否接在 `run_v2.py` 主线之后？
2. 是否复用了 `x_intel_rules.py`，而不是另写账号/关键词规则？
3. 是否复用了 `crawler_runner.py`，而不是绕过当前稳定抓取执行器？
4. 是否复用了 `cleaner_v2.py` / `signal_judge.py`？
5. 是否保持 `run.py` 兼容入口不受影响？
6. 是否没有改动 `scraper/` 底层爬虫？

如果答案基本是“是”，说明方向与当前主线一致。
