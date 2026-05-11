# DeepAlpha Architecture

本文档用于明确 DeepAlpha 当前和未来的 7 层系统结构。  
当前目标不是立刻大重构，而是先把层级边界、职责归属和后续新增模块位置说清楚。

本次架构说明不要求删除、移动、重命名任何文件，也不要求修改 `run.py`、`run_v2.py` 或 `scraper/` 底层爬虫。

## 总体数据流

```text
用户问题 / 监听任务
  -> 第一层：规则路由层
  -> 第二层：信息采集层
  -> 第三层：轻清洗层
  -> 第四层：事件聚合层
  -> 第五层：证据链生成层
  -> 第六层：信号判断层
  -> 第七层：报告生成层
```

层级边界原则：

- 事件聚合不替代清洗。
- 证据链生成不替代信号判断。
- 报告生成不负责抓取。
- 抓取层不负责利多/利空判断。
- 规则路由层不直接操作浏览器。
- 后续新增功能优先放在 `deepalpha_runtime/` 或独立模块中，再由入口或调度器编排。

## 第一层：规则路由层

职责：根据用户问题和资产类型，决定抓取哪些高价值账号、关键词和事件短语。

当前对应文件：

- `x_intel_rules.py`
- `intel_router.py`
- `intel_router_v2.py`

当前说明：

- `x_intel_rules.py` 是账号、关键词、领域分组和优先级规则的主要来源。
- `intel_router.py` 是兼容版规则路由器。
- `intel_router_v2.py` 是当前推荐主入口 `run_v2.py` 使用的新版快速规则路由器。

输出建议：

- `asset`
- `top_accounts`
- `top_event_phrases`
- `crawl_tasks`
- `current_regime`
- `urgency`
- `why_this_route`

边界：

- 不执行抓取。
- 不清洗推文。
- 不判断最终利多/利空。
- 不重复维护完整石油账号库，优先复用 `x_intel_rules.py`。

## 第二层：信息采集层

职责：调用 X/Twitter 抓取模块，执行账号抓取和关键词抓取。

当前对应文件：

- `crawler_runner.py`
- `scraper/twitter_scraper.py`
- `scraper/__main__.py`
- `scraper/tweet.py`
- `scraper/scroller.py`

当前说明：

- `crawler_runner.py` 是当前主链路里的抓取执行编排层，负责把规则路由层输出转换成账号抓取和搜索抓取任务。
- `scraper/twitter_scraper.py` 是底层 Selenium 抓取核心。
- `scraper/__main__.py` 是底层 scraper 的独立 CLI。
- `scraper/tweet.py` 负责从页面 DOM 中解析单条推文。
- `scraper/scroller.py` 负责滚动加载。

输出建议：

- 原始推文字典列表。
- 抓取错误列表。
- CSV 保存路径。
- 抓取统计信息。

边界：

- 不做复杂事件归并。
- 不做最终利多/利空判断。
- 不生成用户最终报告。
- 不应直接写入证据链逻辑。

## 第三层：轻清洗层

职责：对原始推文进行基础去重、明显垃圾过滤、无关内容过滤，避免低质量内容进入后续分析。

当前对应文件：

- `cleaner_v2.py`
- `data_cleaner.py`
- `filter_level1.py` 可作为旧版参考

当前说明：

- `cleaner_v2.py` 是当前推荐的轻量清洗方向，适合实时监听和后续事件聚合前处理。
- `data_cleaner.py` 是兼容保留的旧版清洗链路。
- `filter_level1.py` 可以作为早期规则过滤参考，但不建议作为当前主链路入口。

输出建议：

- 已规范字段的推文列表。
- 基础分数或标签，如来源分、时效分、噪音标记。
- 保留原始 `raw` 数据，方便后续证据链回溯。

边界：

- 轻清洗只降低噪音，不负责判断多条推文是否属于同一事件。
- 不输出最终石油利多/利空结论。
- 不生成用户报告。

## 第四层：事件聚合层

职责：把多条相似推文合并成一个事件对象，判断哪些信息是在说同一件事。

当前状态：已新增基础模块，可继续演进。

建议文件：

- `event_cluster.py`

当前说明：

- `event_cluster.py` 应输入已经经过基础清洗的推文列表。
- 它只负责聚合事件，不替代 `cleaner_v2.py` 或 `data_cleaner.py`。
- 它不负责最终利多/利空判断，不替代 `signal_judge.py`。
- 它应优先复用 `x_intel_rules.py` 中已有的石油关键词、实体、账号分级，而不是重新维护一套完整规则。

聚合依据：

- 时间窗口，默认可用 3 小时。
- 实体词重合。
- 关键词重合。
- 文本相似度。
- 来源是否不同。

输出建议：

- `event_id`
- `event_title`
- `related_tweets`
- `first_seen_time`
- `last_seen_time`
- `sources`
- `source_count`
- `main_keywords`

边界：

- 不负责基础清洗。
- 不负责证据链完整性判断。
- 不负责利多/利空判断。
- 不负责生成最终报告。

## 第五层：证据链生成层

职责：围绕每个事件整理“谁说的、什么时候说的、来源可信度、多源确认、是否存在矛盾信息”。

当前状态：待新增模块。

建议文件：

- `evidence_chain.py`

未来输入：

- 第四层输出的事件对象。
- 事件内的 `related_tweets`。
- 来源账号分级信息。
- 清洗层生成的来源分、时效分、噪音标记。

未来输出建议：

- `event_id`
- `primary_sources`
- `secondary_sources`
- `source_credibility_summary`
- `first_reporter`
- `confirmation_count`
- `conflicting_claims`
- `evidence_score`
- `timeline`

边界：

- 证据链只整理证据质量，不直接输出石油利多/利空。
- 证据链不替代 `signal_judge.py`。
- 证据链不负责抓取。
- 证据链不生成最终用户报告，只给报告层提供材料。

## 第六层：信号判断层

职责：判断事件对石油是利多、利空还是中性，并给出影响等级和置信度。

当前对应文件：

- `signal_judge.py`

当前说明：

- `signal_judge.py` 当前可对推文列表做方向、影响等级、置信度判断。
- 后续可以扩展为对“事件对象 + 证据链”做判断，而不是只对单条推文或推文列表做判断。

输入建议：

- 清洗后的推文。
- 或事件聚合层输出的事件对象。
- 或证据链生成层输出的证据链对象。

输出建议：

- `market_direction`
- `market_direction_label`
- `impact_level`
- `aggregate_confidence`
- `key_signals`
- `reasoning_summary`

边界：

- 不负责抓取。
- 不负责事件聚合。
- 不负责证据链材料整理。
- 不直接生成完整用户报告。

## 第七层：报告生成层

职责：把事件、证据链、信号判断整合成用户可读的石油风险预警报告。

当前对应文件：

- `run.py`
- `run_v2.py`
- `intel_analyzer.py`

后续建议新增：

- `oil_report_generator.py`

当前说明：

- `run.py` 和 `run_v2.py` 当前承担了一部分报告输出职责，包括终端总结和可选 JSON 输出。
- `intel_analyzer.py` 当前负责历史情报汇总报告。
- 后续如果报告复杂度上升，应把报告生成独立为 `oil_report_generator.py`，避免入口文件继续变厚。

未来输入：

- 事件对象。
- 证据链对象。
- 信号判断结果。
- 历史上下文。

未来输出建议：

- 石油风险摘要。
- 高优先级事件列表。
- 多源确认情况。
- 利多/利空/中性结论。
- 影响等级。
- 置信度。
- 关键来源与原文摘录。
- 建议继续监听的账号或关键词。

边界：

- 报告生成不负责抓取。
- 报告生成不负责基础清洗。
- 报告生成不负责事件聚合。
- 报告生成不负责证据链计算本身。

## 当前主线与未来演进

当前推荐主线仍然是：

```text
run_v2.py
  -> intel_router_v2.py
  -> crawler_runner.py
  -> scraper/twitter_scraper.py
  -> cleaner_v2.py 或 data_cleaner.py
  -> signal_judge.py
  -> 报告输出
```

未来石油监听和报告链路建议演进为：

```text
deepalpha_runtime/monitor.py 或未来调度器
  -> intel_router_v2.py / x_intel_rules.py
  -> crawler_runner.py
  -> cleaner_v2.py
  -> event_cluster.py
  -> evidence_chain.py
  -> signal_judge.py
  -> oil_report_generator.py
```

新增功能放置建议：

- 运行时编排、监听、状态管理：优先放 `deepalpha_runtime/`。
- 可复用分析模块：放项目根目录独立模块，如 `event_cluster.py`、`evidence_chain.py`、`oil_report_generator.py`。
- 不要直接把新逻辑塞进 `scraper/`。
- 不要为了接新模块而立即大规模重构 `run.py` 或 `run_v2.py`。

## 已知边界提醒

- `main_v2.py`、`hybrid_crawler.py`、`account_pool.py` 当前仍应视为实验/备选模块，不是当前主链路。
- `event_cluster.py` 是事件聚合层，不是清洗层，也不是信号判断层。
- `evidence_chain.py` 尚未新增，未来应专注证据质量，不做方向判断。
- `oil_report_generator.py` 尚未新增，未来应专注报告表达，不做抓取。
- `run.py` 作为兼容入口保留。
- `run_v2.py` 是当前推荐入口。
