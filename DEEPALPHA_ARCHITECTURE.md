# DeepAlpha Architecture 2.0

本文档定义 DeepAlpha 的下一阶段架构：一个只以 X/Twitter 为实时输入源的市场情报系统。

和 `Digital Oracle` 的定位不同：

```text
Digital Oracle = 读取交易数据，推断市场共识
DeepAlpha      = 读取 X 信息流，发现事件、叙事拐点和市场冲击源
```

DeepAlpha 不应被设计成“推文摘要器”，而应被设计成“会进化的信息源网络”。系统的核心能力不是抓更多推文，而是持续学习哪些账号、哪些事件、哪些叙事真正对市场有价值。

## 核心原则

1. 只用 X/Twitter 作为实时情报输入。
2. 单条推文不直接产生结论，事件簇和证据链才产生结论。
3. 账号不是固定名单，而是可发现、可试用、可晋级、可降级的动态资产。
4. 不同账号类型使用不同评分体系：信息源看可信度，市场冲击源看影响力。
5. 市场价格不作为实时输入，但可以作为事后验证标签，用于训练账号信誉。
6. 抓取预算先广撒浅扫，再命中深挖，而不是少数账号固定深抓。
7. 报告必须区分“事实可信度”“市场影响力”“方向判断”“是否需要二次确认”。

## 总体架构

```text
用户问题 / 监听任务
  -> 1. 意图识别与情景路由
  -> 2. 动态账号选择
  -> 3. 分层抓取执行
  -> 4. 推文标准化与轻清洗
  -> 5. 事件聚合
  -> 6. 证据链生成
  -> 7. 信号判断
  -> 8. 报告生成
  -> 9. 市场回顾验证
  -> 10. 账号信誉更新
  -> 回流到动态账号选择
```

闭环图：

```text
账号池
  -> 抓取
  -> 发现事件
  -> 生成信号
  -> 事后验证
  -> 更新账号画像
  -> 下一轮更聪明地选账号
```

## 1. 意图识别与情景路由

职责：理解用户问题对应的资产、场景、紧急度和抓取模式。

当前对应文件：

- `run_v2.py`
- `intel_router_v2.py`
- `oil_intent_classifier.py`
- `x_intel_rules.py`

输入：

```json
{
  "query": "油价会涨吗？",
  "mode": "user_query"
}
```

输出：

```json
{
  "asset": "oil",
  "scenario": "shipping_risk",
  "regime": "war_risk",
  "urgency": "normal",
  "crawl_mode": "normal",
  "why": "用户问题涉及原油和地缘/航运风险"
}
```

建议的 `crawl_mode`：

```text
fast     = 少量核心账号快速检查
normal   = 多账号浅扫 + 命中深挖
deep     = 大范围扫描 + 事件扩展
critical = 突发模式，优先市场冲击源和高信誉源
```

## 2. 动态账号选择

职责：根据资产、场景、账号画像和抓取预算，选择本轮要抓取的账号。

当前基础：

- `x_intel_rules.py` 提供初始种子账号。
- `intel_router_v2.py` 已有油价动态抽样雏形。
- `account_status.py` 已记录运行失败状态。

建议新增：

- `account_registry.py`：账号画像库。
- `account_discovery.py`：发现新账号。
- `account_reputation.py`：账号信誉评分和晋级降级。

账号来源：

```text
种子账号：x_intel_rules.py 中手动维护的 S/A/B/C 账号
高分账号：历史验证后表现好的账号
场景账号：当前场景相关账号，如航运、OPEC、战争、宏观
探索账号：系统新发现但未验证的账号
市场冲击源：特朗普、马斯克、鲍威尔、OPEC 官方等
```

账号状态：

```text
seed       = 手写种子账号
candidate  = 新发现候选账号
watch      = 小流量观察账号
core       = 高价值核心账号
specialist = 某资产/某场景专家
market_mover = 自身会影响市场的人或机构
muted      = 暂时降权
blocked    = 噪声或假消息源
```

账号画像示例：

```json
{
  "handle": "@JavierBlas",
  "source_role": "reporter",
  "status": "core",
  "asset_scores": {
    "oil": 0.94,
    "gas": 0.86
  },
  "evidence": {
    "total_signals": 128,
    "validated": 73,
    "failed": 18,
    "neutral": 29,
    "overridden": 8,
    "avg_lead_time_minutes": 42,
    "duplicate_rate": 0.18
  }
}
```

市场冲击源画像示例：

```json
{
  "handle": "@realDonaldTrump",
  "source_role": "market_mover",
  "asset_impact": {
    "oil": {
      "impact_score": 0.91,
      "direction_reliability": 0.48,
      "volatility_lift": 0.86,
      "reversal_rate": 0.62
    }
  }
}
```

关键区别：

```text
记者/通讯社：问他说的事实准不准
分析师/交易员：问他的解释框架有没有用
官方机构：问其权威性和政策相关性
市场冲击源：问他说完市场会不会动，而不是问他准不准
搬运号：问它能不能帮系统发现线索
```

## 3. 分层抓取执行

职责：在有限抓取预算内最大化新鲜、可信、非重复的信息。

当前对应文件：

- `crawler_runner.py`
- `scraper/twitter_scraper.py`
- `scraper/tweet.py`
- `scraper/scroller.py`

当前问题：

```text
底层账号很多，但每轮只选少数账号深抓。
这会导致信息面窄，且容易错过当天真正有价值的新源头。
```

建议改为三段式：

```text
第一段：广撒浅扫
  20-80 个账号，每人抓 3-5 条

第二段：命中深挖
  对命中高价值关键词或高相关事件的账号追加 20-50 条

第三段：事件扩展
  围绕事件关键词、引用账号、被提及账号继续搜索
```

抓取预算示例：

```text
fast:
  核心账号 10 个 x 5 条
  搜索任务 1-2 个 x 20 条

normal:
  浅扫账号 30 个 x 5 条
  命中账号追加 5-8 个 x 20 条
  搜索任务 2-4 个 x 30 条

deep:
  浅扫账号 50 个 x 5 条
  命中账号追加 10 个 x 30 条
  事件搜索 5-8 个 x 30 条

critical:
  市场冲击源和核心账号优先
  缩短任务间隔
  增加关键词搜索和事件复查
```

输出：

```json
{
  "crawl_plan": {
    "mode": "normal",
    "shallow_accounts": [],
    "deep_accounts": [],
    "search_tasks": [],
    "budget": {
      "max_accounts": 30,
      "max_tweets": 500
    }
  },
  "crawl_results": {
    "all_tweets": [],
    "errors": [],
    "account_runtime_status": {}
  }
}
```

## 4. 推文标准化与轻清洗

职责：把原始推文转成统一结构，去掉明显垃圾和重复内容。

当前对应文件：

- `cleaner_v2.py`
- `data_cleaner.py`
- `filter_level1.py`

标准推文对象：

```json
{
  "tweet_id": "204914415232",
  "asset": "oil",
  "handle": "@Reuters",
  "timestamp": "2026-05-08T10:15:00+00:00",
  "collected_at": "2026-05-08T10:16:12+00:00",
  "content": "Iran warns that disruption near Hormuz could affect oil tanker traffic.",
  "tweet_link": "https://x.com/Reuters/status/204914415232",
  "likes": 1200,
  "retweets": 350,
  "mentions": ["@OPECSecretariat"],
  "tags": ["oil", "Hormuz"],
  "source_role": "reporter",
  "raw": {}
}
```

轻清洗只做三件事：

```text
规范字段
基础去重
明显无关/垃圾过滤
```

不要在清洗层做最终利多利空判断。

## 5. 事件聚合

职责：把多条推文合并成同一个事件，避免单条推文反复影响判断。

当前对应文件：

- `event_cluster.py`

事件聚合依据：

```text
时间窗口
实体重合
关键词重合
文本相似度
来源独立性
引用/转述关系
```

事件对象：

```json
{
  "event_id": "8582f75a376952c5",
  "event_title": "Hormuz tanker disruption risk",
  "asset": "oil",
  "related_tweets": [],
  "first_seen_time": "2026-05-08T10:15:00+00:00",
  "last_seen_time": "2026-05-08T10:42:00+00:00",
  "sources": ["@Reuters", "@JavierBlas", "@TankersTrackers"],
  "independent_source_count": 3,
  "echo_source_count": 12,
  "main_keywords": ["Hormuz", "tanker", "crude", "supply"]
}
```

## 6. 证据链生成

职责：判断这个事件是不是可信，是否多源确认，是否存在同源污染或矛盾信息。

当前对应文件：

- `evidence_chain.py`

证据链必须回答：

```text
谁最早说？
谁是原始来源？
哪些账号是独立确认？
哪些账号只是搬运或转述？
有没有反向说法？
来源平均可信度如何？
这个事件是否足够进入信号判断？
```

证据链对象：

```json
{
  "event_id": "8582f75a376952c5",
  "primary_sources": ["@Reuters"],
  "secondary_sources": ["@JavierBlas", "@TankersTrackers"],
  "original_source": "@Reuters",
  "independent_sources": 3,
  "echo_sources": 12,
  "conflicting_claims": [],
  "multi_source_status": "strong_multi_source",
  "evidence_score": 0.87,
  "evidence_quality": "strong"
}
```

同源污染规则：

```text
20 个账号转同一个未经证实的源头，不算 20 个证据。
只能算 1 个原始源头 + 19 个传播源。
```

## 7. 信号判断

职责：基于事件和证据链，判断市场方向、影响等级、置信度和是否需要确认。

当前对应文件：

- `signal_judge.py`

信号分两类：

```text
information_signal = 信息验证信号，来自记者、官方、数据源、专业账号
impact_signal      = 市场冲击信号，来自特朗普、马斯克、央行、OPEC 等市场冲击源
```

信息型信号示例：

```json
{
  "signal_type": "information_signal",
  "event_id": "8582f75a376952c5",
  "asset": "oil",
  "direction": "bullish",
  "impact_level": 4,
  "confidence": 0.82,
  "reason": "多来源确认 Hormuz 航运风险，可能增加供应中断溢价"
}
```

冲击型信号示例：

```json
{
  "signal_type": "impact_signal",
  "handle": "@realDonaldTrump",
  "asset": "oil",
  "trigger": "tariff / Iran / OPEC",
  "expected_effect": "volatility_up",
  "direction": "uncertain",
  "reversal_risk": "high",
  "requires_confirmation": true
}
```

不要把市场冲击源当普通可信账号处理。

## 8. 报告生成

职责：把事件、证据链、信号判断组织成用户能读懂的情报报告。

当前对应文件：

- `report_formatter.py`
- `oil_report_generator.py`
- `run_v2.py`

报告结构建议：

```text
一句话判断
核心事件
证据质量
市场方向
冲击源提醒
矛盾信息
需要继续观察的点
风险说明
```

报告不应只说“利多/利空”，而应说明：

```text
为什么这不是噪声
哪些证据独立
哪些证据只是扩散
是否存在冲击源
方向是否稳定
是否需要市场二次确认
```

## 9. 市场回顾验证

职责：事后检查系统生成的信号是否被市场验证，用于更新账号评分。

注意：市场价格不进入实时判断，只进入事后验证。

建议新增：

- `signal_archive.py`：保存每次事件信号。
- `market_verifier.py`：事后拉取价格并验证结果。
- `account_reputation.py`：根据验证结果更新账号画像。

信号归档对象：

```json
{
  "signal_id": "oil_20260508_001",
  "event_id": "8582f75a376952c5",
  "asset": "oil",
  "direction": "bullish",
  "confidence": 0.82,
  "source_handles": ["@Reuters", "@JavierBlas"],
  "created_at": "2026-05-08T10:20:00+00:00",
  "price_at_signal": 82.1
}
```

验证窗口：

```text
1h
6h
24h
3d
```

验证结果：

```json
{
  "signal_id": "oil_20260508_001",
  "price_after_1h": 82.8,
  "price_after_6h": 84.0,
  "price_after_24h": 83.5,
  "return_6h": 0.023,
  "result": "validated",
  "notes": "6h 内方向正确且超过噪声阈值"
}
```

结果分类：

```text
validated  = 方向正确且超过噪声阈值
failed     = 方向明显错误
neutral    = 市场无明显反应
delayed    = 短期未验证，但较长窗口验证
overridden = 方向可能正确，但被更大宏观事件覆盖
```

## 10. 账号信誉更新

职责：把市场验证结果回流到账号画像，让下一轮选账号更聪明。

评分维度：

```text
accuracy_score    = 历史方向准确率
timeliness_score  = 是否比其他账号更早
impact_score      = 其信号后市场反应幅度
originality_score = 是否一手来源
independence_score = 是否独立于其他账号
noise_penalty     = 无效推文和同源搬运惩罚
reversal_penalty  = 冲击后经常反转的惩罚
```

最终账号价值：

```text
account_value =
  source_role_weight
  + asset_specific_score
  + recent_validated_signals
  + timeliness_score
  + originality_score
  + discovery_value
  - noise_penalty
  - duplicate_penalty
  - false_alarm_penalty
```

下一轮抓取时，`intel_router_v2.py` 不应只从固定账号池随机抽样，而应融合：

```text
40% 高信誉核心账号
30% 当前场景专家账号
20% 轮转补盲账号
10% 新候选探索账号
```

## 建议模块划分

```text
deepalpha_runtime/
  account_registry.py      # 账号画像读写
  account_discovery.py     # 新账号发现
  account_reputation.py    # 信誉评分、晋级降级
  signal_archive.py        # 信号归档
  market_verifier.py       # 市场回顾验证
  crawl_budget.py          # 抓取预算分配
  monitor.py               # 定时监听编排
```

现有主链路保持：

```text
run_v2.py
  -> intel_router_v2.py
  -> crawler_runner.py
  -> cleaner_v2.py
  -> event_cluster.py
  -> evidence_chain.py
  -> signal_judge.py
  -> report_formatter.py
```

新学习闭环接在报告之后：

```text
report generated
  -> signal_archive.py
  -> market_verifier.py
  -> account_reputation.py
  -> account_registry.py
  -> intel_router_v2.py
```

## 推荐迭代路线

### Phase 1: 抓取预算优化

- 让 `intel_router_v2.py` 输出更多候选账号，而不是截断为 5 个。
- 让 `crawler_runner.py` 支持浅扫和深挖两段任务。
- 引入 `crawl_mode` 和 per-account `limit`。

### Phase 2: 账号画像库

- 新增 `account_registry.py`。
- 把 `x_intel_rules.py` 的 S/A/B/C 账号导入为 seed 账号。
- 记录每个账号的资产、角色、状态、最近抓取、最近命中。

### Phase 3: 事件和证据链主线化

- 让 `event_cluster.py` 成为清洗后的必经层。
- 让 `evidence_chain.py` 输出独立来源、同源污染、矛盾信息。
- `signal_judge.py` 改为优先判断事件，而不是单条推文。

### Phase 4: 市场回顾验证

- 新增 `signal_archive.py` 保存每次信号。
- 新增 `market_verifier.py` 记录 1h/6h/24h/3d 后市场结果。
- 暂时可用 CSV/JSON 保存，后续迁移 SQLite。

### Phase 5: 账号自进化

- 新增 `account_reputation.py`。
- 通过验证结果更新账号分数。
- 让 `intel_router_v2.py` 根据账号分数、场景和探索比例动态选账号。

## DeepAlpha 的最终形态

DeepAlpha 的目标不是比谁抓得多，而是比谁更会判断信息源。

最终系统应该做到：

```text
知道哪些账号可靠
知道哪些账号能制造市场冲击
知道哪些账号只是搬运
知道哪些事件是多源确认
知道哪些信号过去被市场验证
知道什么时候该浅扫，什么时候该深挖
知道什么时候该输出方向，什么时候该输出高波动提醒
```

一句话：

```text
Digital Oracle 读取价格里的共识。
DeepAlpha 读取信息流里的拐点。
```
