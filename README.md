# DeepAlpha

DeepAlpha 是当前文件夹内继续开发的新版 X/Twitter 情报分析项目。原始版本已经单独备份在 GitHub / Gitee，本目录作为新版项目主线继续演进。

当前阶段做“主线收敛”：源码、网页、文档和测试保留在仓库内；抓取 CSV、报告、图谱 JSON、日志、虚拟环境和缓存都视为本地运行产物，不再作为源码维护。

## 当前推荐入口

推荐使用：

```bash
python run_v2.py "油价会涨吗？"
```

完整实时抓取流程：

```bash
python run_v2.py "油价会涨吗？" --crawl
```

使用新版精简清洗器：

```bash
python run_v2.py "油价会涨吗？" --crawl --new-cleaner
```

只看决策和抓取计划，不启动抓取：

```bash
python run_v2.py "黄金走势？" --crawl --dry-run
```

交互模式：

```bash
python run_v2.py
```

## 兼容入口

`run.py` 作为兼容入口保留，用于继续支持原有主流程：

```bash
python run.py "油价会涨吗？"
python run.py "比特币会涨吗？" --crawl
```

兼容入口仍然有价值：它走更保守的原版决策和清洗链路，适合在 `run_v2.py` 行为不确定时对照验证。

## 暂不作为主链路的文件

以下文件保留，但暂时不作为 DeepAlpha 当前主链路：

| 文件 | 当前定位 |
| --- | --- |
| `main_v2.py` | 优化版统一 API/实验入口，暂不作为推荐 CLI。 |
| `hybrid_crawler.py` | HTTP/curl_cffi + Playwright 混合抓取实验实现，暂不接入主抓取链路。 |
| `account_pool.py` | 账号池和健康度管理实验模块，暂不接入主抓取链路。 |

当前主链路仍然复用稳定的 Selenium 抓取执行方式：

```text
run_v2.py
  -> intel_router_v2.py
  -> crawler_runner.py
  -> scraper/twitter_scraper.py
```

## 当前主链路

推荐实时抓取链路：

```text
用户问题
  -> run_v2.py
  -> intel_router_v2.py
  -> x_intel_rules.py
  -> crawler_runner.py
  -> scraper/twitter_scraper.py
  -> 抓取的信息/*.csv
  -> graph_engine.py
  -> cleaner_v2.py 或 data_cleaner.py
  -> signal_judge.py
  -> 终端报告 / --output JSON
```

默认说明：

- `run_v2.py` 是当前推荐主入口。
- `intel_router_v2.py` 负责新版快速规则决策。
- `crawler_runner.py` 负责把决策转换为账号抓取和搜索抓取任务。
- `scraper/` 是底层 Selenium 爬虫，本轮不改。
- `cleaner_v2.py` 通过 `--new-cleaner` 启用；未启用时仍使用 `data_cleaner.py` 兼容清洗。
- `signal_judge.py` 负责方向、影响等级和置信度判断。

## 历史库分析

不传 `--crawl` 时，系统优先分析本地历史 CSV，不启动浏览器：

```bash
python run_v2.py "油价会涨吗？"
```

大致链路：

```text
run_v2.py
  -> intel_router_v2.py
  -> intel_analyzer.py
  -> graph_engine.load_tweets_from_csv_dir()
  -> signal_judge.py
```

历史数据默认读取：

```text
./抓取的信息/
```

## 图谱查看

从历史 CSV 生成独立图谱 JSON：

```bash
python -m deepalpha.graph_engine
```

启动本地图谱查看器：

```bash
python graph_viewer.py --port 8080
```

启动本地网页版：

```bash
python -m deepalpha_web.server
```

在查询后打开图谱：

```bash
python run_v2.py "油价会涨吗？" --view-graph
```

图谱输出默认位置：

```text
./graph_data/关系图谱.json
```

## 定时刷新与后续监听

当前已有一个低频刷新脚本：

```bash
python -m deepalpha.scheduled_crawler --once --jitter-minutes 25 --headless
```

它目前更适合作为“定时刷新历史库”的调度壳，而不是完整监听模块。后续新增“定时情报监听模块”时，建议接在 `intel_router_v2.py` / `x_intel_rules.py` 之后，复用 `crawler_runner.py` 执行抓取，并在 `crawler_runner.save_results()` 后接清洗和信号判断。

推荐未来位置：

```text
intel_monitor.py
  -> intel_router_v2.py
  -> x_intel_rules.py
  -> crawler_runner.py
  -> cleaner_v2.py
  -> signal_judge.py
  -> graph_data/monitor_state.json
```

也可以扩展 `scheduled_crawler.py`，但建议让它保持“调度器”职责，不把清洗、信号、图谱逻辑全部塞进去。

## 底层 scraper 独立用法

底层爬虫仍可独立运行：

```bash
python -m scraper --query="关键词" -t 20
python -m scraper -u Reuters -t 20
python -m scraper --query="oil OPEC" -t 20 -b chrome
```

常用参数：

| 参数 | 说明 |
| --- | --- |
| `-q, --query` | 搜索查询。 |
| `-u, --username` | 抓取指定账号。 |
| `-ht, --hashtag` | 按话题标签抓取。 |
| `-l, --list` | 按列表 ID 抓取。 |
| `-t, --tweets` | 抓取数量，默认 50。 |
| `--latest` | 最新推文，默认使用。 |
| `--top` | 热门推文。 |
| `--headlessState yes` | 无头模式运行。 |
| `-b, --browser` | 浏览器选择：`chrome`、`firefox`、`safari`。 |
| `--cookie-file` | Cookie 文件路径。 |

## 安装与准备

创建虚拟环境：

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

准备 Cookie：

1. 使用测试用 X 账号登录浏览器。
2. 通过 Cookie-Editor 等工具导出 JSON Cookie。
3. 保存为项目根目录的 `cookies/browser/x_cookie.json`。
4. 可参考 `cookies/browser/x_cookie 示例.json` 的格式。

注意：

- `cookies/browser/x_cookie.json` 是登录凭证，不要提交或公开。
- `cookies/*.json` 也可能包含账号凭证，应按敏感文件处理。
- Cookie 过期后需要重新导出。

## 主要文件说明

| 文件/目录 | 当前定位 |
| --- | --- |
| `run_v2.py` | 当前推荐主入口。 |
| `run.py` | 兼容入口。 |
| `crawler_runner.py` | 决策到 Selenium 抓取任务的执行桥。 |
| `scraper/` | 底层 Selenium X/Twitter 爬虫。 |
| `intel_router_v2.py` | 新版快速决策器。 |
| `intel_router.py` | 原版决策器，兼容保留。 |
| `x_intel_rules.py` | 账号池、关键词、分组规则。 |
| `cleaner_v2.py` | 新版精简清洗器。 |
| `data_cleaner.py` | 原版清洗器，兼容保留。 |
| `signal_judge.py` | 信号判断器。 |
| `intel_analyzer.py` | 历史情报分析。 |
| `graph_engine.py` | 独立图谱 JSON 生成。 |
| `graph_viewer.py` | 本地图谱查看器。 |
| `web/` | DeepAlpha 网页、Slides、Docs 和嵌入式关系图谱入口。 |
| `deepalpha_web/` | 本地网页服务与 JSON API。 |
| `scheduled_crawler.py` | 低频刷新历史库脚本，未来监听模块参考。 |
| `main_v2.py` | 实验入口，暂不作为主链路。 |
| `hybrid_crawler.py` | 实验抓取引擎，暂不作为主链路。 |
| `account_pool.py` | 实验账号池模块，暂不作为主链路。 |
| `PROJECT_AUDIT.md` | 项目结构审计文档。 |
| `DEV_NOTES.md` | 当前开发主线说明。 |

## 本地产物

| 路径 | 说明 |
| --- | --- |
| `抓取的信息/` | 抓取 CSV 历史库。 |
| `graph_data/` | 图谱 JSON 和调度状态。 |
| `reports/` | JSON / Markdown 报告输出。 |
| `logs/` | 运行日志。 |
| `obsidian_vault/` | Obsidian 图谱输出产物。 |
| `test_obsidian_vault/` | 测试图谱输出产物。 |
| `__pycache__/` | Python 缓存。 |
| `venv/` | 本地虚拟环境。 |

这些目录会由运行命令自动生成，并已加入 `.gitignore`。

## 测试/示例脚本

这些脚本可以保留用于验证和演示，但不属于当前主链路：

```bash
python test_v2.py
python test_optimized.py
python simple_use.py
python hybrid_example.py
python use_it.py
```

## 开发约定

- 当前推荐入口只认 `run_v2.py`。
- `run.py` 只作为兼容入口保留。
- 暂时不要把 `main_v2.py`、`hybrid_crawler.py`、`account_pool.py` 接进主流程。
- 不直接改 `scraper/` 底层爬虫，除非专门处理抓取问题。
- 新增定时监听优先做编排层，不重复写抓取、清洗和信号判断逻辑。

更多结构细节见：

- `PROJECT_AUDIT.md`
- `DEV_NOTES.md`
