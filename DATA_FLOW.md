# DeepAlpha Data Flow

本文档说明 DeepAlpha 7 层系统中每一层的输入和输出数据结构。  
本文件只定义数据约定，不要求改动代码。

## 总体流向

```text
用户问题 / 监听任务
  -> 规则路由
  -> 信息采集
  -> 轻清洗
  -> 事件聚合
  -> 证据链生成
  -> 信号判断
  -> 报告生成
```

## 核心对象

### tweet 对象

`tweet` 是采集层和清洗层之间的基础数据单元。字段可逐步补齐，但建议统一为：

```json
{
  "tweet_id": "204914415232",
  "asset": "oil",
  "handle": "@Reuters",
  "name": "Reuters",
  "timestamp": "2026-05-08T10:15:00+00:00",
  "collected_at": "2026-05-08T10:16:12+00:00",
  "content": "Iran warns that disruption near Hormuz could affect oil tanker traffic.",
  "tweet_link": "https://x.com/Reuters/status/204914415232",
  "likes": 1200,
  "retweets": 350,
  "replies": 80,
  "verified": true,
  "tags": ["oil", "Hormuz"],
  "mentions": ["@OPECSecretariat"],
  "raw": {}
}
```

推荐字段说明：

| 字段 | 说明 |
| --- | --- |
| `tweet_id` | 推文唯一 ID；没有时可用内容 hash 临时生成。 |
| `asset` | 资产类型，如 `oil`。 |
| `handle` | 来源账号，如 `@Reuters`。 |
| `name` | 来源显示名。 |
| `timestamp` | 推文发布时间。 |
| `collected_at` | 本地抓取时间。 |
| `content` | 推文正文。 |
| `tweet_link` | 推文链接。 |
| `likes` / `retweets` / `replies` | 互动指标。 |
| `verified` | 是否认证账号。 |
| `tags` / `mentions` | 话题和提及。 |
| `raw` | 原始抓取数据，便于回溯。 |

### event 对象

`event` 是事件聚合层输出的数据单元，表示多条推文在讨论同一件事。

```json
{
  "event_id": "8582f75a376952c5",
  "event_title": "Hormuz / tanker / crude supply",
  "related_tweets": [
    {
      "tweet_id": "204914415232",
      "handle": "@Reuters",
      "timestamp": "2026-05-08T10:15:00+00:00",
      "content": "Iran warns that disruption near Hormuz could affect oil tanker traffic."
    }
  ],
  "first_seen_time": "2026-05-08T10:15:00+00:00",
  "last_seen_time": "2026-05-08T10:42:00+00:00",
  "sources": ["@Reuters", "@JavierBlas", "@TankersTrackers"],
  "source_count": 3,
  "main_keywords": ["Hormuz", "tanker", "crude", "supply"]
}
```

推荐字段说明：

| 字段 | 说明 |
| --- | --- |
| `event_id` | 事件 ID。 |
| `event_title` | 事件标题，通常由主关键词生成。 |
| `related_tweets` | 归入该事件的推文列表。 |
| `first_seen_time` | 事件最早出现时间。 |
| `last_seen_time` | 事件最近更新时间。 |
| `sources` | 涉及来源账号。 |
| `source_count` | 不同来源数量。 |
| `main_keywords` | 事件核心关键词。 |

### evidence_chain 对象

`evidence_chain` 是证据链生成层输出的数据单元，围绕一个事件整理来源质量和多源确认情况。

```json
{
  "event_id": "8582f75a376952c5",
  "event_title": "Hormuz / tanker / crude supply",
  "first_seen_time": "2026-05-08T10:15:00+00:00",
  "last_seen_time": "2026-05-08T10:42:00+00:00",
  "source_count": 3,
  "source_types": ["通讯社", "记者", "分析师"],
  "multi_source_status": "strong_multi_source",
  "evidence_count": 3,
  "average_credibility": 9.33,
  "evidence": [
    {
      "source_account": "@Reuters",
      "source_type": "通讯社",
      "published_time": "2026-05-08T10:15:00+00:00",
      "collected_time": "2026-05-08T10:16:12+00:00",
      "summary": "Iran warns that disruption near Hormuz could affect oil tanker traffic.",
      "url": "https://x.com/Reuters/status/204914415232",
      "credibility_score": 10
    }
  ]
}
```

推荐字段说明：

| 字段 | 说明 |
| --- | --- |
| `event_id` | 对应事件 ID。 |
| `event_title` | 对应事件标题。 |
| `source_count` | 不同来源数量。 |
| `source_types` | 来源类型集合。 |
| `multi_source_status` | `single_source` / `initial_multi_source` / `strong_multi_source`。 |
| `evidence_count` | 证据条数。 |
| `average_credibility` | 平均可信度分数。 |
| `evidence` | 每条证据详情。 |

单条证据建议字段：

| 字段 | 说明 |
| --- | --- |
| `source_account` | 来源账号。 |
| `source_type` | 官方 / 通讯社 / 记者 / 分析师 / 普通账号。 |
| `published_time` | 发布时间。 |
| `collected_time` | 抓取时间。 |
| `summary` | 原文摘要。 |
| `url` | 原文链接。 |
| `credibility_score` | 来源可信度分数。 |

### signal_judgment 对象

`signal_judgment` 是信号判断层输出的数据单元，描述事件对石油方向和影响的判断。

```json
{
  "event_id": "8582f75a376952c5",
  "market_direction": "bullish_oil",
  "market_direction_label": "利多原油",
  "impact_level": 4,
  "aggregate_confidence": 0.82,
  "confidence_parts": {
    "source_credibility": 0.93,
    "multi_source": 1.0,
    "recency": 0.95,
    "keyword_strength": 0.75
  },
  "key_signals": ["Hormuz blockade", "tanker attack", "supply disruption"],
  "reasoning_summary": "多来源提到 Hormuz 航运和油轮风险，可能增加供应中断溢价。"
}
```

推荐字段说明：

| 字段 | 说明 |
| --- | --- |
| `event_id` | 对应事件 ID。 |
| `market_direction` | `bullish_oil` / `bearish_oil` / `neutral`。 |
| `market_direction_label` | 中文方向说明。 |
| `impact_level` | 影响等级，建议 1-5。 |
| `aggregate_confidence` | 聚合置信度，0-1。 |
| `confidence_parts` | 置信度组成。 |
| `key_signals` | 命中的方向关键词或信号。 |
| `reasoning_summary` | 简短判断依据。 |

### final_report 对象

`final_report` 是报告生成层输出的数据单元，可渲染为 Markdown、JSON 或前端页面。

```json
{
  "report_id": "oil_2026-05-08_24h",
  "asset": "oil",
  "time_range": {
    "since": "2026-05-07T10:00:00+00:00",
    "until": "2026-05-08T10:00:00+00:00"
  },
  "generated_at": "2026-05-08T10:05:00+00:00",
  "headline": "原油风险偏利多，主要来自 Hormuz 航运风险和供应中断担忧。",
  "core_events": [],
  "bullish_factors": [],
  "bearish_factors": [],
  "evidence_chains": [],
  "signal_judgments": [],
  "overall_judgment": "当前规则信号偏向利多原油。",
  "overall_confidence": 0.78,
  "risk_notes": [
    "本报告基于规则和公开信息生成，不构成交易建议。",
    "单一来源事件需要等待更多来源确认。"
  ],
  "markdown": "# 石油风险预警报告\n..."
}
```

推荐字段说明：

| 字段 | 说明 |
| --- | --- |
| `report_id` | 报告 ID。 |
| `asset` | 资产，如 `oil`。 |
| `time_range` | 报告覆盖时间范围。 |
| `generated_at` | 报告生成时间。 |
| `headline` | 一句话摘要。 |
| `core_events` | 核心事件列表。 |
| `bullish_factors` | 利多因素。 |
| `bearish_factors` | 利空因素。 |
| `evidence_chains` | 证据链列表。 |
| `signal_judgments` | 信号判断列表。 |
| `overall_judgment` | 综合判断。 |
| `overall_confidence` | 综合置信度。 |
| `risk_notes` | 风险提示。 |
| `markdown` | 可选 Markdown 渲染结果。 |

## 七层输入输出

## 第一层：规则路由层

输入：

```json
{
  "query": "油价会涨吗？",
  "asset": "oil",
  "mode": "user_query"
}
```

输出：

```json
{
  "asset": "oil",
  "user_intent": "供给驱动",
  "current_regime": "supply_risk",
  "urgency": "normal",
  "top_accounts": ["@JavierBlas", "@Reuters", "@KSAmofaEN"],
  "top_event_phrases": ["OPEC cut", "Iran Hormuz"],
  "crawl_tasks": ["from:@JavierBlas OR from:@Reuters", "\"Iran Hormuz\" oil"],
  "why_this_route": "当前原油市场处于供给驱动阶段。"
}
```

## 第二层：信息采集层

输入：

```json
{
  "top_accounts": ["@JavierBlas", "@Reuters"],
  "crawl_tasks": ["\"Iran Hormuz\" oil"],
  "cookie_file": "x_cookie.json",
  "browser": "chrome",
  "headless": false
}
```

输出：

```json
{
  "total_tweets": 42,
  "all_tweets": [
    {
      "tweet_id": "204914415232",
      "handle": "@Reuters",
      "timestamp": "2026-05-08T10:15:00+00:00",
      "content": "Iran warns that disruption near Hormuz could affect oil tanker traffic.",
      "tweet_link": "https://x.com/Reuters/status/204914415232"
    }
  ],
  "errors": [],
  "saved_path": "抓取的信息/2026-05-08_10-16-12_intel_42.csv"
}
```

## 第三层：轻清洗层

输入：

```json
{
  "tweets": [
    {
      "tweet_id": "204914415232",
      "handle": "@Reuters",
      "content": "Iran warns that disruption near Hormuz could affect oil tanker traffic.",
      "timestamp": "2026-05-08T10:15:00+00:00"
    }
  ]
}
```

输出：

```json
{
  "cleaned_tweets": [
    {
      "tweet_id": "204914415232",
      "asset": "oil",
      "handle": "@Reuters",
      "timestamp": "2026-05-08T10:15:00+00:00",
      "collected_at": "2026-05-08T10:16:12+00:00",
      "content": "Iran warns that disruption near Hormuz could affect oil tanker traffic.",
      "source_score": 9.0,
      "timeliness_score": 0.9,
      "noise_score": 0.0,
      "verdict": "actionable",
      "final_score": 8.2,
      "raw": {}
    }
  ]
}
```

## 第四层：事件聚合层

输入：

```json
{
  "cleaned_tweets": [
    {
      "tweet_id": "204914415232",
      "handle": "@Reuters",
      "timestamp": "2026-05-08T10:15:00+00:00",
      "content": "Iran warns that disruption near Hormuz could affect oil tanker traffic."
    }
  ],
  "window_hours": 3
}
```

输出：

```json
{
  "events": [
    {
      "event_id": "8582f75a376952c5",
      "event_title": "Hormuz / tanker / crude supply",
      "related_tweets": [],
      "first_seen_time": "2026-05-08T10:15:00+00:00",
      "last_seen_time": "2026-05-08T10:42:00+00:00",
      "sources": ["@Reuters", "@JavierBlas"],
      "source_count": 2,
      "main_keywords": ["Hormuz", "tanker", "crude", "supply"]
    }
  ]
}
```

## 第五层：证据链生成层

输入：

```json
{
  "events": [
    {
      "event_id": "8582f75a376952c5",
      "event_title": "Hormuz / tanker / crude supply",
      "related_tweets": []
    }
  ]
}
```

输出：

```json
{
  "evidence_chains": [
    {
      "event_id": "8582f75a376952c5",
      "event_title": "Hormuz / tanker / crude supply",
      "source_count": 3,
      "source_types": ["通讯社", "记者", "分析师"],
      "multi_source_status": "strong_multi_source",
      "average_credibility": 9.33,
      "evidence": []
    }
  ]
}
```

## 第六层：信号判断层

输入：

```json
{
  "evidence_chain": {
    "event_id": "8582f75a376952c5",
    "event_title": "Hormuz / tanker / crude supply",
    "average_credibility": 9.33,
    "multi_source_status": "strong_multi_source",
    "evidence": []
  }
}
```

输出：

```json
{
  "signal_judgment": {
    "event_id": "8582f75a376952c5",
    "market_direction": "bullish_oil",
    "market_direction_label": "利多原油",
    "impact_level": 4,
    "aggregate_confidence": 0.82,
    "key_signals": ["Hormuz blockade", "tanker attack"],
    "reasoning_summary": "航运风险可能增加供应中断溢价。"
  }
}
```

## 第七层：报告生成层

输入：

```json
{
  "events": [],
  "evidence_chains": [],
  "signal_judgments": [],
  "asset": "oil",
  "hours": 24
}
```

输出：

```json
{
  "final_report": {
    "report_id": "oil_2026-05-08_24h",
    "asset": "oil",
    "headline": "原油风险偏利多，主要来自 Hormuz 航运风险。",
    "core_events": [],
    "bullish_factors": [],
    "bearish_factors": [],
    "overall_judgment": "当前规则信号偏向利多原油。",
    "overall_confidence": 0.78,
    "risk_notes": [],
    "markdown": "# 石油风险预警报告\n..."
  }
}
```

## 兼容说明

当前代码中不同模块的字段名可能仍有历史差异，例如：

- `tweet_id` / `Tweet ID` / `id`
- `handle` / `Handle` / `username`
- `content` / `Content` / `text`
- `tweet_link` / `Tweet Link` / `url`

后续模块应尽量在边界处做一次 normalize，再使用本文档推荐字段。这样可以避免把历史字段差异扩散到事件、证据链和报告层。
