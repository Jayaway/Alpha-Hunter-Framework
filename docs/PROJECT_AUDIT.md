# PROJECT_AUDIT

审计时间：2026-05-08  
范围：扫描项目根目录、`scraper/`、本地数据目录、测试/示例脚本、缓存与环境目录。  
原则：本次只做结构体检与记录，不删除文件，不修改业务代码。

## 1. 当前项目结构说明

当前项目是一个以 X/Twitter 抓取为数据源的本地情报分析系统。项目里同时存在“原始 Selenium 爬虫仓库文件”和后续新增的“实时情报系统”文件，因此结构呈现出多代实现并存的状态。

主要目录与文件类别：

| 路径 | 类型 | 说明 |
| --- | --- | --- |
| `scraper/` | 原始/底层抓取包 | Selenium X/Twitter 爬虫核心，支持 `python -m scraper` 独立运行，也被 `crawler_runner.py` 调用。 |
| `run.py` | 当前稳定聚合入口 | 原版主流程入口：决策 -> 可选抓取 -> 保存 CSV -> 图谱 -> 清洗 -> 信号判断 -> 报告。 |
| `run_v2.py` | 当前 README 推荐入口 | 优化版 CLI 入口：用 `intel_router_v2.py` 做决策，可选 `cleaner_v2.py`，抓取仍走 `crawler_runner.py`/Selenium。 |
| `main_v2.py` | 优化版 API/实验入口 | 试图整合 `hybrid_crawler.py`、`account_pool.py`、`cleaner_v2.py` 等；更像实验性统一 API，不是 README 的首要 CLI。 |
| `x_intel_rules.py` | 规则配置 | 账号池、关键词规则、分组、抓取频率建议等核心规则。 |
| `抓取的信息/` | 本地 CSV 数据 | 历史抓取结果，目前有 3 个 CSV。 |
| `graph_data/` | 图谱与调度状态 | `关系图谱.json` 和 `scheduler_state.json`。 |
| `obsidian_vault/` | Obsidian 输出产物 | 图谱 Markdown 产物，约 288 个文件。 |
| `test_obsidian_vault/` | 测试图谱产物 | `obsidian_graph.py` 自测/示例输出，约 24 个文件。 |
| `cookies/` | 多账号 Cookie 示例/配置 | `account_pool.py`、`hybrid_crawler.py` 相关。 |
| `venv/` | 本地虚拟环境 | 依赖环境，不属于业务代码。 |
| `__pycache__/`、`scraper/__pycache__/` | Python 缓存 | 可再生成产物，不属于源码。 |
| `.idea/`、`.DS_Store` | IDE/系统文件 | 本地环境产物。 |

Git 状态提示：

- 当前 Git 跟踪文件很少，主要是原始 scraper、README、requirements、notebook、cookie 示例等。
- 大量实时情报系统文件处于未跟踪状态，如 `run.py`、`run_v2.py`、`crawler_runner.py`、`intel_router*.py`、`cleaner*.py`、`signal_judge.py`、`graph_engine.py` 等。
- `.gitignore` 已忽略 `venv/`、`__pycache__/`、`*.csv`、`抓取的信息/`、`cookies/browser/x_cookie.json`，但 `.idea/` 当前未启用忽略。

## 2. 当前真正的主入口文件

### 推荐/当前入口

| 文件 | 判断 | 说明 |
| --- | --- | --- |
| `run_v2.py` | 当前 README 推荐入口 | README 的“方式一：使用优化版（推荐）”指向此文件。它实际承担 CLI 入口，默认使用 `intel_router_v2.py`，抓取仍复用 `crawler_runner.py` 和 `scraper.twitter_scraper.Twitter_Scraper`。 |
| `run.py` | 稳定兼容入口 | README 的“原版完全可用”指向此文件。它是当前更完整、更保守的主链路入口，默认使用 `intel_router.py` 和 `data_cleaner.py`。 |

### 底层抓取入口

| 文件 | 判断 | 说明 |
| --- | --- | --- |
| `scraper/__main__.py` | 底层爬虫 CLI | 支持 `python -m scraper` 或类似包入口方式，直接抓账号、话题、搜索、列表、收藏，并调用 `Twitter_Scraper.save_to_csv()`。 |
| `scraper/twitter_scraper.py` | 底层抓取核心 | Selenium 浏览器初始化、Cookie 登录、页面跳转、滚动、推文解析、CSV 保存。 |

### 实验/次级入口

| 文件 | 判断 | 说明 |
| --- | --- | --- |
| `main_v2.py` | 优化版 API/实验入口 | 文件头写明“优化版主入口”，但 README 主要推荐 `run_v2.py`。代码里存在明显未接完整的问题，建议暂时视作实验链路。 |
| `scheduled_crawler.py` | 低频刷新入口 | 已有“定时刷新历史情报库”的雏形，内部调用 `run.py query --crawl`。可作为后续定时监听模块的参考或上层调度器。 |

## 3. 功能相关文件映射

### X/Twitter 抓取

核心：

- `scraper/twitter_scraper.py`：Selenium 抓取核心，负责浏览器、Cookie 登录、页面导航、滚动、解析推文、CSV 保存。
- `scraper/__main__.py`：底层抓取 CLI。
- `scraper/tweet.py`：从 X 页面 DOM 中解析单条推文。
- `scraper/scroller.py`：滚动加载控制。
- `scraper/progress.py`：抓取进度输出。
- `crawler_runner.py`：把决策器输出转换为账号/搜索任务，并复用一个 `Twitter_Scraper` 会话执行多任务。

实验/优化：

- `hybrid_crawler.py`：HTTP/curl_cffi + Playwright 的混合抓取尝试，当前未被 `run_v2.py` 使用，只被 `main_v2.py`、示例和文档引用。
- `account_pool.py`：账号池、健康度、频率限制模型，当前未接入 `run.py`/`run_v2.py` 主链路。

### 账号/关键词规则

核心：

- `x_intel_rules.py`：S/A/B/C 账号分级、领域分组、关键词规则、频率建议、优先级计算。
- `intel_router.py`：原版决策器，内部也有资产、阶段、事件短语和账号选择逻辑，并引用 `x_intel_rules.py`。
- `intel_router_v2.py`：优化版决策器，预编译正则、缓存、账号选择，引用 `x_intel_rules.py`。

相关/辅助：

- `account_pool.py`：账号可用性、健康度和身份池规则。
- `filter_level1.py`：旧式第一级过滤规则，含地缘实体、动作、商品关键词矩阵。

### 数据清洗

核心：

- `data_cleaner.py`：原版 6 层清洗流水线，`run.py` 默认使用，`run_v2.py` 在未启用 `--new-cleaner` 时也使用。
- `cleaner_v2.py`：新版 3 层清洗器，`run_v2.py --new-cleaner` 和 `main_v2.py` 使用。

疑似旧版/辅助：

- `filter.py`：极短脚本，读取一个固定 CSV 并打印账号统计，像早期一次性分析脚本。
- `filter_level1.py`：独立第一级过滤脚本，输出到 `filter_output/`，未接入当前 `run.py`/`run_v2.py`。

### 信号判断

核心：

- `signal_judge.py`：方向、影响等级、置信度判断器，被 `run.py`、`run_v2.py`、`main_v2.py`、`intel_analyzer.py` 使用。

### 报告输出

核心：

- `run.py`：终端最终报告；通过 `--output` 保存 JSON 报告。
- `run_v2.py`：终端最终报告；通过 `--output` 保存 JSON 报告。
- `intel_analyzer.py`：历史情报汇总与终端报告输出。
- `graph_engine.py`：生成独立关系图谱 JSON。
- `graph_viewer.py`：本地图谱查看器 HTTP 服务与前端页面。

相关/旧版：

- `obsidian_graph.py`：生成 Obsidian Markdown 图谱。
- `main_v2.py`：`QueryResult.summary()` 和 `export_report()`，但 CLI 导出路径存在明显未接完整的问题。

### 本地数据保存

核心：

- `crawler_runner.py::save_results()`：将聚合抓取结果保存到 `./抓取的信息/{timestamp}_intel_{count}.csv`。
- `scraper/twitter_scraper.py::save_to_csv()`：底层 scraper 直接保存 `./抓取的信息/{timestamp}_tweets_1-{count}.csv`，并尝试生成图谱。
- `graph_engine.py`：读取 `./抓取的信息/*.csv`，输出 `./graph_data/关系图谱.json`。
- `scheduled_crawler.py`：维护 `./graph_data/scheduler_state.json` 和 `./graph_data/scheduler.lock`。

产物目录：

- `抓取的信息/`：CSV 历史库。
- `graph_data/`：独立图谱 JSON 和调度状态。
- `obsidian_vault/`：Obsidian Markdown 图谱产物。
- `test_obsidian_vault/`：测试图谱产物。

## 4. 当前运行流程

### A. 推荐优化版流程：`python run_v2.py "问题" --crawl --new-cleaner`

1. `run_v2.py` 解析 CLI 参数。
2. `_make_decision()` 调用 `intel_router_v2.decide()`。
3. 决策器根据资产/市场阶段选择 `top_accounts` 和 `crawl_tasks`。
4. `crawler_runner.run_all_tasks()` 把决策转换成：
   - 账号抓取任务：最多 5 个账号，每个默认 20 条。
   - 搜索抓取任务：最多 2 条查询，每条默认 30 条。
5. `crawler_runner.py` 创建一次 `scraper.twitter_scraper.Twitter_Scraper`，用 Cookie 登录，复用同一浏览器会话执行所有任务。
6. `crawler_runner.save_results()` 保存 CSV 到 `抓取的信息/`。
7. `graph_engine.generate_graph_data()` 读取历史 CSV 或本次推文，生成 `graph_data/关系图谱.json`。
8. `_clean_tweets()`：
   - 如果启用 `--new-cleaner`，使用 `cleaner_v2.clean_tweets()`。
   - 否则使用 `data_cleaner.clean_pipeline()`。
9. `_judge_signals()` 调用 `signal_judge.judge_all_signals()`。
10. 打印最终报告；如传入 `--output`，保存 JSON 报告。

### B. 稳定原版流程：`python run.py "问题" --crawl`

1. `run.py` 解析 CLI 参数。
2. 默认调用 `intel_router.decide()`，可选 `ai_model.ai_decide()`。
3. 若未传 `--crawl`，调用 `intel_analyzer.analyze_history()` 读取历史 CSV 汇总。
4. 若传 `--crawl`，走 `crawler_runner.run_all_tasks()`。
5. 保存 CSV，生成图谱。
6. 默认用 `data_cleaner.clean_pipeline()` 清洗。
7. 调用 `signal_judge.judge_all_signals()` 输出信号判断。
8. 打印或保存报告。

### C. 底层 scraper 流程：`python -m scraper --username Reuters --tweets 20`

1. `scraper/__main__.py` 解析账号/话题/搜索等参数。
2. 创建 `Twitter_Scraper`。
3. `login()` 使用 Cookie 或账号密码登录。
4. `scrape_tweets()` 导航目标页面并滚动解析。
5. `save_to_csv()` 保存 CSV，并尝试调用 `graph_engine.generate_graph_data()`。

### D. 历史分析流程：不传 `--crawl`

1. `run.py`/`run_v2.py` 判断是市场问题后，不启动浏览器。
2. `intel_analyzer.py` 读取 `抓取的信息/*.csv`。
3. 根据资产词、查询词和决策器事件短语筛选相关推文。
4. 调用 `signal_judge.py` 聚合判断。
5. 打印历史情报汇总。

## 5. 核心文件列表

建议作为当前最小可信核心链路保留：

| 文件 | 角色 | 是否核心 |
| --- | --- | --- |
| `run_v2.py` | 当前推荐 CLI 入口 | 是 |
| `run.py` | 兼容/稳定 CLI 入口 | 是 |
| `crawler_runner.py` | 决策到 Selenium 抓取任务的桥 | 是 |
| `scraper/__main__.py` | 底层 scraper CLI | 是 |
| `scraper/twitter_scraper.py` | 底层 Selenium 抓取核心 | 是 |
| `scraper/tweet.py` | 推文 DOM 解析 | 是 |
| `scraper/scroller.py` | 页面滚动 | 是 |
| `scraper/progress.py` | 抓取进度 | 是 |
| `intel_router_v2.py` | 优化版规则决策器 | 是 |
| `intel_router.py` | 原版规则决策器 | 是，保留兼容 |
| `x_intel_rules.py` | 账号池/关键词规则 | 是 |
| `cleaner_v2.py` | 新版清洗器 | 是 |
| `data_cleaner.py` | 原版清洗器 | 是，保留兼容 |
| `signal_judge.py` | 信号判断 | 是 |
| `intel_analyzer.py` | 历史 CSV 汇总分析 | 是 |
| `graph_engine.py` | 独立图谱 JSON 生成 | 是 |
| `graph_viewer.py` | 本地图谱查看器 | 是 |
| `ai_model.py` | 可选 AI 决策/清洗/问答 | 可选核心 |
| `requirements.txt` | 依赖声明 | 是 |
| `README.md` | 当前使用说明 | 是 |

## 6. 可疑冗余文件列表

以下仅为“可疑冗余/旧版本/临时/测试”判断，不建议现在删除；后续可以逐个确认是否仍有使用价值。

### 明确测试/示例/说明脚本

| 文件 | 判断依据 |
| --- | --- |
| `test_v2.py` | 文件名和内容都是核心模块测试。 |
| `test_optimized.py` | 批量执行 `run_v2.py` 命令的测试脚本。 |
| `simple_use.py` | 使用示例，含模拟推文。 |
| `hybrid_example.py` | 渐进式使用示例，含模拟数据。 |
| `use_it.py` | 交互式演示/使用引导。 |
| `QUICK_START_GUIDE.py` | 用 Python 打印快速开始说明，不是业务模块。 |
| `OPTIMIZATION_SUMMARY.py` | 优化总结/说明性质，非运行链路。 |

### 疑似旧版本/并行实验版本

| 文件 | 判断依据 |
| --- | --- |
| `main_v2.py` | 优化版 API/实验入口，但不在 README 推荐 CLI 主路径中；存在明显未接完整的问题。 |
| `hybrid_crawler.py` | 新混合抓取引擎，目前未被 `run.py`/`run_v2.py` 使用；HTTP GraphQL URL 和解析逻辑更像实验实现。 |
| `account_pool.py` | 账号池健康度模块，当前未接入主运行链路。 |
| `filter.py` | 读取固定旧 CSV 路径的临时统计脚本，当前路径可能不存在。 |
| `filter_level1.py` | 独立过滤脚本，未接入主运行链路；可能是早期清洗方案。 |
| `obsidian_graph.py` | 旧图谱输出方案，当前主链路使用 `graph_engine.py` + `graph_viewer.py`。 |
| `scheduled_crawler.py` | 已有低频定时刷新雏形，但当前不是主入口；可作为后续定时监听模块基础。 |

### 本地数据/产物/缓存

| 路径 | 判断依据 |
| --- | --- |
| `抓取的信息/*.csv` | 历史抓取数据，是运行产物；不要当源码。 |
| `graph_data/关系图谱.json` | 图谱生成产物。 |
| `graph_data/scheduler_state.json` | 调度状态产物。 |
| `obsidian_vault/` | Obsidian 图谱输出产物。 |
| `test_obsidian_vault/` | 测试图谱输出产物。 |
| `tweets/` | 当前为空目录。 |
| `__pycache__/`、`scraper/__pycache__/` | Python 缓存。 |
| `.DS_Store`、`scraper/.DS_Store` | macOS 系统文件。 |
| `.idea/` | IDE 配置，本地环境文件。 |
| `venv/` | 本地虚拟环境。 |

### 敏感/本地配置

| 文件 | 判断依据 |
| --- | --- |
| `cookies/browser/x_cookie.json` | 登录凭证，已在 `.gitignore` 中；不要提交或公开。 |
| `cookies/account_1.json` | 多账号 Cookie 配置，疑似也含凭证，应按敏感文件处理。 |
| `cookies/browser/x_cookie 示例.json` | Cookie 格式示例，可保留。 |

## 7. 明显问题记录

只记录，不修改：

1. `main_v2.py` 里 `quick_query()` 使用了未定义变量 `verbose`。
2. `main_v2.py` 里 `monitor_accounts()` 调用 `quick_crawl()`，但函数作用域内未导入。
3. `main_v2.py` CLI `--export` 分支使用 `result.system.export_report(...)`，但 `QueryResult` 未定义 `system` 属性。
4. `hybrid_crawler.py` 文档说有 Selenium 兜底，但实际 `HybridCrawlerEngine._crawl_with_fallback()` 只看到 HTTP 与 Playwright，未看到 Selenium 兜底执行分支。
5. `hybrid_crawler.py` 的 `CurlSession(impersonate=...)` 参数来自 User-Agent 字符串拆分，可能不是 curl_cffi 支持的 impersonate 名称。
6. `run.py` 和 `run_v2.py` 有大量重复逻辑，属于可接受的版本并存，但后续维护容易出现行为分叉。
7. `scraper/__main__.py` 顶部强依赖 `dotenv`，导入失败会直接退出；如果 `.env` 非必需，这会影响底层 scraper 独立运行。
8. `.idea/` 和 `.DS_Store` 当前出现在工作区中；`.gitignore` 里 `.idea/` 仍是注释状态。
9. 当前很多核心业务文件未被 Git 跟踪；如果这是正式项目，后续提交策略需要单独整理。

## 8. 建议保留的最小核心链路

在“不新增功能、不大重构”的前提下，建议先把当前可运行链路收敛为：

```text
run_v2.py
  -> intel_router_v2.py
  -> x_intel_rules.py
  -> crawler_runner.py
  -> scraper/twitter_scraper.py
  -> scraper/tweet.py
  -> scraper/scroller.py
  -> scraper/progress.py
  -> 抓取的信息/*.csv
  -> graph_engine.py
  -> cleaner_v2.py 或 data_cleaner.py
  -> signal_judge.py
  -> 终端报告 / --output JSON
```

兼容链路保留：

```text
run.py
  -> intel_router.py
  -> crawler_runner.py
  -> data_cleaner.py
  -> signal_judge.py
```

历史分析链路保留：

```text
run_v2.py 或 run.py（不传 --crawl）
  -> intel_analyzer.py
  -> graph_engine.load_tweets_from_csv_dir()
  -> signal_judge.py
```

图谱查看链路保留：

```text
graph_engine.py
  -> graph_data/关系图谱.json
  -> graph_viewer.py
```

暂时不要把 `main_v2.py` / `hybrid_crawler.py` / `account_pool.py` 作为主链路，除非后续专门做一次“优化版抓取引擎接入”。

## 9. 后续“定时情报监听模块”建议接入点

建议不要直接接在 `scraper/twitter_scraper.py` 后面。更稳的接法是接在“决策器之后、抓取执行器之前/之后”的编排层，复用现有核心能力。

### 推荐接入位置

1. 监听任务生成：接在 `intel_router_v2.py` / `x_intel_rules.py` 后面。
   - 使用账号等级、资产、市场阶段、关键词规则生成监听计划。
   - 不要在监听模块里重复维护账号/关键词规则。

2. 抓取执行：接到 `crawler_runner.py`。
   - 复用 `build_tasks()`、`run_all_tasks()`、`save_results()`。
   - 定时模块只负责任务节奏、状态、去重，不直接操作 Selenium 细节。

3. 数据落盘后处理：接在 `crawler_runner.save_results()` 后面。
   - 先保存原始数据到 `抓取的信息/`。
   - 再调用 `cleaner_v2.clean_tweets()` 或 `data_cleaner.clean_pipeline()`。
   - 再调用 `signal_judge.judge_all_signals()`。

4. 历史库与图谱：接到 `graph_engine.py`。
   - 每轮监听后更新 `graph_data/关系图谱.json`。
   - 状态文件继续放在 `graph_data/`，类似 `scheduler_state.json`。

5. 报告/告警输出：接在 `signal_judge.py` 之后。
   - 只有出现 actionable/noteworthy 或高影响信号时输出报告。
   - 初期可只输出终端/JSON，不急着做复杂通知。

### 可复用现有文件

- `scheduled_crawler.py`：已有低频刷新脚本，可作为“调度壳”的起点。
- `graph_data/scheduler_state.json`：已有状态文件思路，可扩展为记录上次运行、下次运行、最近 tweet_id、失败次数。
- `x_intel_rules.py`：监听账号与关键词的规则源。
- `crawler_runner.py`：实际抓取执行器。
- `cleaner_v2.py`：实时监听场景更适合默认使用它。
- `signal_judge.py`：监听后的信号判断。

### 建议的监听模块最小形态

后续如果新增模块，建议只新增一个编排文件，例如：

```text
intel_monitor.py
  -> 读取 watchlist / query 列表
  -> 调用 intel_router_v2.decide()
  -> 调用 crawler_runner.run_all_tasks()
  -> 调用 crawler_runner.save_results()
  -> 调用 cleaner_v2.clean_tweets()
  -> 调用 signal_judge.judge_all_signals()
  -> 记录 graph_data/monitor_state.json
```

如果沿用现有命名，也可以扩展 `scheduled_crawler.py`，但建议先把它定位为“调度器”，不要把清洗、信号、图谱逻辑都写进去。

## 10. 总结

当前项目的主线已经能分辨出来：

- 最可信的当前入口是 `run_v2.py` 和 `run.py`。
- 真正执行 X/Twitter 抓取的是 `crawler_runner.py` + `scraper/`。
- 规则中心是 `x_intel_rules.py`，决策器有 `intel_router.py` 与 `intel_router_v2.py` 两代。
- 清洗器有 `data_cleaner.py` 与 `cleaner_v2.py` 两代。
- 信号判断集中在 `signal_judge.py`。
- 报告与本地数据主要通过 `run*.py`、`crawler_runner.py`、`graph_engine.py` 完成。

建议下一步先不要删除文件，而是先在文档和 README 中明确“推荐主链路”。等主链路稳定后，再分批归档测试脚本、示例脚本、实验模块和本地产物。
