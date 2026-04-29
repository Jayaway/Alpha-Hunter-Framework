# X (Twitter) 实时情报抓取系统

基于 Selenium 的 X (Twitter) 爬虫 + 交易员级极速决策器 + 6层数据清洗引擎，支持 Cookie 登录，无需 API。

## 系统架构

```
用户自然语言提问
       ↓
  ┌─────────────────┐
  │  极速决策器       │  intel_router.py
  │  5账号+5短语+2任务 │  → 最短抓取路径
  └────────┬────────┘
           ↓
  ┌─────────────────┐
  │  爬虫执行器       │  crawler_runner.py
  │  调用现有scraper  │  → 原始推文
  └────────┬────────┘
           ↓
  ┌─────────────────┐
  │  6层数据清洗引擎   │  data_cleaner.py
  │  去重→可信度→时效  │  → 高价值情报
  │  →噪音→二手→交叉   │
  └────────┬────────┘
           ↓
  ┌─────────────────┐
  │  信号判断器       │  signal_judge.py
  │  方向/幅度/可信度  │  → 交易信号
  └─────────────────┘
```

## 功能特性

- Cookie 登录，无需账号密码
- 支持 Safari、Chrome、Firefox 三种浏览器
- 支持搜索、用户主页、话题、书签等抓取模式
- 结果保存为 CSV 文件
- **交易员级极速决策器**：用户一句话 → Top5账号 + Top5事件短语 + 2条搜索任务
- **6大市场阶段判断**：供给驱动 / 需求驱动 / 政策驱动 / 战争驱动 / 美元驱动 / 风险情绪驱动
- **6层数据清洗引擎**：去重 → 来源可信度 → 时效 → 情绪噪音 → 二手转述 → 多源交叉验证
- **信号判断器**：12种方向信号 + 5级影响等级 + 多源聚合判断
- **一键端到端运行**：`python3 run.py "油价会涨吗？"`
- **185+ 高价值账号分级监控**（S/A/B/C 四级优先级）
- **智能抓取频率**（S级5分钟 / A级15分钟 / B级1小时 / C级4小时）

## 安装

### 1. 克隆项目

```bash
git clone https://gitee.com/meda0719/selenium-x-scraper.git
cd selenium-x-scraper
```

### 2. 创建虚拟环境并安装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. 启用 Safari WebDriver（仅 Safari 需要）

```bash
safaridriver --enable
```

### 4. 准备 Cookie 登录文件

> ⚠️ **安全提示**：Cookie 等同于你的登录凭证，切勿分享给他人。建议使用小号，不要用主号。

**步骤：**

1. 注册一个 X 小号（建议小号，不要用主号）
2. 在 Chrome 中安装 [Cookie-Editor](https://cookie-editor.cgagnier.ca/) 扩展
3. 打开 X.com 并登录
4. 点击浏览器右上角的 Cookie-Editor 扩展图标
5. 点击 **Export** → 选择 **JSON** 格式
6. 将导出的内容保存为 `x_cookie.json`，放到项目根目录
7. 验证格式是否正确：文件应以 `[` 开头，包含 `"domain": ".x.com"` 字段

项目已提供 `x_cookie.example.json` 作为格式参考。

**Cookie 过期怎么办？** 重新执行上述步骤导出即可，通常几天到几周需要更换一次。

## 使用方法

### 基本用法

```bash
python3 -m scraper --query="关键词" -t 数量
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `-q, --query` | 搜索查询，支持高级搜索语法 |
| `-u, --username` | 抓取指定用户的推文 |
| `-ht, --hashtag` | 按话题标签抓取 |
| `-l, --list` | 按列表 ID 抓取 |
| `-t, --tweets` | 抓取数量（默认 50） |
| `--latest` | 最新推文（默认） |
| `--top` | 热门推文 |
| `--headlessState yes` | 无头模式运行 |
| `-b, --browser` | 浏览器选择：`safari`/`chrome`/`firefox`（默认 safari） |
| `--cookie-file` | Cookie 文件路径 |

## 使用示例

```bash
# 搜索推文
python3 -m scraper --query="nvidia since:2024-01-18 until:2024-01-19" -t 10 --top

# 抓取用户推文
python3 -m scraper -u elonmusk -t 100

# 按话题抓取（最新）
python3 -m scraper -ht python -t 100 --latest

# 按话题抓取（热门）
python3 -m scraper -ht python -t 100 --top

# 使用 Chrome 浏览器
python3 -m scraper --query="keyword" -t 10 -b chrome

# 无头模式
python3 -m scraper --query="keyword" -t 10 --headlessState yes
```

## 高级搜索语法

```bash
# 包含提及
python3 -m scraper --query="(@elonmusk)" -t 100

# 按时间和回复数筛选
python3 -m scraper --query="(@elonmusk) min_replies:1000 until:2023-08-31 since:2020-01-01" -t 100
```

更多高级搜索语法参考 [Twitter 高级搜索](https://twitter.com/search-advanced)

## 输出结果

爬取结果保存在 `./tweets/` 目录下，原始数据在 `./抓取的信息/` 目录下：

| 字段 | 说明 |
|------|------|
| Name | 用户名 |
| Handle | 账号（如 @xxx） |
| Timestamp | 发布时间 |
| Verified | 是否认证 |
| Content | 推文内容 |
| Comments/Retweets/Likes | 互动数 |
| Tags | 话题标签 |
| Mentions | @提及 |
| Profile Image | 头像链接 |
| Tweet Link | 推文链接 |
| Tweet ID | 推文 ID |

## 情报过滤系统

项目包含三层架构：极速决策 → 数据清洗 → 账号规则。

### 第一层：极速决策器（`intel_router.py`）

用户输入一句市场问题，AI 自动识别资产类别、市场阶段、用户意图，输出最短抓取路径。

```bash
python3 intel_router.py
```

**核心原则：快、准、少、能执行**

| 输入 | 输出 |
|------|------|
| 最多 Top5 账号 | 谁说的比说了什么更重要 |
| 最多 Top5 事件短语 | 事件+主体+动作（如 `Hormuz blockade`） |
| 最多 2 条搜索任务 | 可直接喂给 scraper 执行 |

**市场阶段判断：**

| 阶段 | 触发场景 | 抓取重点 |
|------|----------|----------|
| 供给驱动 | OPEC、制裁、油轮、管道 | 能源记者 + OPEC官方 |
| 需求驱动 | 衰退、GDP、中国需求 | 宏观数据源 |
| 政策驱动 | 美联储、关税、利率 | 央行 + 财经通讯社 |
| 战争驱动 | 导弹、袭击、停火 | 战地记者 + 军方账号 |
| 美元驱动 | 汇率、干预、DXY | 央行 + 外汇分析师 |
| 风险情绪驱动 | VIX、崩盘、避险 | 综合新闻源 |

**示例：**

```python
from intel_router import decide

r = decide("油价会涨吗？")
# r["asset"]             → "oil"
# r["current_regime"]    → "supply_risk"
# r["top_accounts"]      → ["@JavierBlas", "@Reuters", "@KSAmofaEN", "@TankersTrackers", "@realDonaldTrump"]
# r["top_event_phrases"] → ["Hormuz blockade", "Iran tanker seizure", "Saudi voluntary cut", ...]
# r["crawl_tasks"]       → ["from:@JavierBlas OR from:@Reuters Hormuz blockade OR Iran tanker seizure", ...]
```

### 第二层：6层数据清洗引擎（`data_cleaner.py`）

对抓取后的原始推文进行逐层清洗，从海量噪音中提取高价值情报。

```bash
python3 data_cleaner.py
```

| 层 | 功能 | 示例 |
|----|------|------|
| ① 去重 | SimHash + 链接 + 时间聚类 | Reuters发一条，100人转发 → 保留源头 |
| ② 来源可信度 | 官方=10, 通讯社=9, 记者=8, 匿名=1 | @IDF 10分 vs @anon123 1分 |
| ③ 时效 | 识别旧闻翻炒 | "last year 2024" → 降权 |
| ④ 情绪噪音 | 全大写/感叹号/夸张价格/垃圾 | "OIL TO $500!!!" → 丢弃 |
| ⑤ 二手转述 | 标记未证实内容 | "Hearing that..." → 标记⚠️ |
| ⑥ 交叉验证 | 多源确认加分 | Reuters+Bloomberg+WSJ同时报 → 可信度暴涨 |

**最终裁决：**

| 裁决 | 分数 | 说明 |
|------|------|------|
| 🟢 actionable | ≥7分 | 可行动情报，直接交易参考 |
| 🟡 noteworthy | 5-7分 | 值得关注 |
| 🟠 low_value | 3-5分 | 低价值 |
| 🔴 discard | <3分 | 丢弃 |

```python
from data_cleaner import clean_pipeline, Tweet

cleaned = clean_pipeline(raw_tweets, verbose=True)
for t in cleaned:
    if t._final_verdict == "actionable":
        print(f"[{t._final_score}分] @{t.username}: {t.content[:80]}")
```

### 第三层：账号池预筛选（`x_intel_rules.py`）

静态规则层，提供账号分级、领域分组、关键词规则、抓取频率配置。

```bash
python3 x_intel_rules.py
```

| 级别 | 数量 | 抓取频率 | 说明 |
|------|------|----------|------|
| S级 | 18 个 | 每 5 分钟 | 领导人、核心数据源、突发记者 |
| A级 | 39 个 | 每 15 分钟 | 原油交易/地缘前线/宏观机构 |
| B级 | 71 个 | 每 1 小时 | 深度分析/补充记者/次要领导人 |
| C级 | 58 个 | 每 4 小时 | 教育/观点/娱乐性账号 |

### 第四层：信号判断器（`signal_judge.py`）

清洗后的推文 → 价格方向 / 幅度 / 可信度 / 影响等级判断。

```bash
python3 signal_judge.py
```

**12种方向信号：**

| 资产 | 利多信号 | 利空信号 |
|------|----------|----------|
| 原油 | bullish_oil（减产、制裁、封锁、供应中断） | bearish_oil（增产、需求下降、SPR释放） |
| 黄金 | bullish_gold（降息、战争、避险） | bearish_gold（加息、强美元、和平） |
| 外汇 | bullish/bearish_dollar, bullish/bearish_fx_emerging | — |
| 加密 | bullish_crypto（ETF批准、机构买入） | bearish_crypto（SEC拒绝、监管打击） |
| 股市 | bullish_equity（降息、盈利超预期） | bearish_equity（衰退、关税、崩盘） |

**5级影响等级：**

| 等级 | 触发条件 | 价格影响 |
|------|----------|----------|
| 5 | 极端关键词（Hormuz、nuclear、Article 5）+ 高互动 | 可能移动价格3%+ |
| 4 | 高影响词（BREAKING、confirmed） + 高互动 | 可能移动价格1-3% |
| 3 | 多信号叠加 + 中等互动 | 可能移动价格0.5-1% |
| 2 | 单信号 + 低互动 | 影响有限 |
| 1 | 无明确信号 | 忽略 |

```python
from signal_judge import judge_all_signals, print_signal_report

judgment = judge_all_signals(cleaned_tweets, asset="oil")
print_signal_report(judgment)
# judgment["market_direction"]      → "bullish_oil"
# judgment["market_direction_label"] → "利多原油"
# judgment["aggregate_confidence"]  → 0.56
# judgment["avg_impact"]            → 3.4
```

## 一键运行（`run.py`）

端到端流水线：用户一句话 → 决策 → 抓取 → 清洗 → 信号判断 → 报告。

```bash
# 只看决策，不抓取
python3 run.py "油价会涨吗？" --dry-run

# 完整流水线
python3 run.py "油价会涨吗？"

# 完整流水线 + 输出JSON报告
python3 run.py "黄金还能涨吗？" --output report.json

# 跳过清洗/信号判断
python3 run.py "美联储下周降息？" --no-clean --no-judge

# 指定浏览器和无头模式
python3 run.py "BTC会不会拉升？" -b chrome --headless
```

### 原始规则过滤（`filter_level1.py`）

对原始抓取数据进行物理除杂（蓝V权重、互动异常、关键词矩阵、内容质量）。

```bash
python filter_level1.py
```

### TODO

- [ ] 语义清洗：向量化去重 + NER实体识别
- [ ] 情感分类：用X数据微调RoBERTa模型
- [ ] 极速决策器接入LLM：动态更新市场阶段判断

## 项目结构

```
selenium-x-scraper/
├── run.py                   # 一键端到端入口
├── intel_router.py          # 极速决策器（意图识别 + 情报路由）
├── crawler_runner.py        # 爬虫执行器（调用现有scraper）
├── data_cleaner.py          # 6层数据清洗引擎
├── signal_judge.py          # 信号判断器（方向/幅度/可信度）
├── x_intel_rules.py         # 账号池规则（分级/分组/关键词/频率）
├── filter_level1.py         # 原始规则过滤
├── filter.py                # 过滤工具
├── scraper/                 # 爬虫核心模块
│   ├── __init__.py
│   ├── __main__.py          # 入口
│   ├── twitter_scraper.py   # Selenium 抓取引擎
│   ├── tweet.py             # 推文数据模型
│   ├── scroller.py          # 页面滚动控制
│   └── progress.py          # 进度条
├── main.ipynb               # 分析笔记本
├── requirements.txt         # 依赖
├── x_cookie.json            # Cookie 文件（需自行准备）
├── tweets/                  # 爬取结果输出
└── filter_output/           # 过滤结果输出
```

## 浏览器支持

| 浏览器 | 说明 |
|--------|------|
| Safari | 默认，需要手动启用 `safaridriver --enable` |
| Chrome | 需要安装 ChromeDriver |
| Firefox | 需要安装 GeckoDriver |

## 注意事项

- Cookie 会过期，过期后需重新导出
- 建议小号测试，避免主号被封
- 不要过于频繁大量抓取
- 虚拟环境使用前需先激活：`source venv/bin/activate`

## 故障排除

**ModuleNotFoundError**
```bash
source venv/bin/activate
```

**Cookie 登录失败**
- 重新导出 Cookie 文件
- 确保 Cookie 未过期
- 检查是否已安装 WebDriver
