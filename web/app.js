const reports = {
  oil: {
    title: "石油价格会涨吗：多信号交叉验证分析",
    core: "原油价格未来走势（WTI/Brent）",
    window: "用户未指定，默认覆盖短期(3-6个月)和中期(1-2年)",
    sources: [
      "wti price history",
      "brent price history",
      "natgas price",
      "crude oil cot",
      "oil event cluster",
      "oil evidence chain",
      "brent-wti spread",
      "usd strength",
      "fear greed",
      "yield curve",
      "fedwatch",
      "vix current",
      "opec production",
      "china demand",
      "geopolitical risk",
      "oil futures curve",
      "bdi shipping",
      "x source network",
      "market mover watch",
    ],
    rows: [
      ["WTI近一年走势", "从低位反弹后回落，近期仍高于战前水平", "地缘风险溢价未完全消退，但价格已经消化一部分冲击"],
      ["Brent-WTI价差", "价差扩大至5-6 USD区间", "国际供应风险高于北美本地供需风险"],
      ["期货曲线", "近月强于远月，曲线呈轻度backwardation", "市场认为紧张更多是短期供应冲击，不是长期需求繁荣"],
      ["事件簇", "Hormuz / Iran / OPEC 相关推文集中出现", "方向偏利多，但需要区分独立确认和同源扩散"],
      ["波动率", "短周期波动升高", "价格方向不稳定，冲击源消息会放大日内波动"],
    ],
    events: [
      ["Hormuz 航运风险", "多源提到海峡、油轮和供应风险，证据质量较强。", ["strong_multi_source", "bullish"]],
      ["OPEC 产量叙事", "市场关注配额纪律和潜在减产执行。", ["medium", "supply"]],
      ["美元与利率", "美元走强会压制大宗商品，但当前不是主导信号。", ["macro", "secondary"]],
    ],
    direction: "偏利多，但需要二次确认",
    evidence: "strong_multi_source / medium confidence",
    risk: "冲击源信息可能造成短线波动，方向需等待更多独立来源确认",
  },
  btc: {
    title: "BTC价格会涨吗：链上资金与风险偏好交叉验证",
    core: "BTC / crypto risk sentiment",
    window: "默认观察日内到数周：资金流、ETF、清算和宏观流动性",
    sources: [
      "coindesk",
      "the block",
      "wu blockchain",
      "lookonchain",
      "santiment",
      "btc price trend",
      "etf flow",
      "whale activity",
      "funding rate",
      "liquidation map",
      "stablecoin supply",
      "risk sentiment",
    ],
    rows: [
      ["现货趋势", "需要实时抓取 BTC price / breakout / inflow", "历史库无足够相关样本时，不做强方向判断"],
      ["ETF资金", "若持续净流入，通常支撑价格", "市场更相信资金流而不是单条看多推文"],
      ["清算结构", "高杠杆单边堆积会放大反向波动", "涨跌都可能由清算触发，需二次确认"],
    ],
    events: [
      ["ETF inflow", "若多源确认净流入，构成信息型利多。", ["information_signal", "bullish"]],
      ["Whale accumulation", "链上大额转入冷钱包可作为辅助信号。", ["onchain", "medium"]],
      ["Liquidation risk", "合约持仓拥挤时方向可靠性下降。", ["risk", "confirmation"]],
    ],
    direction: "暂无强结论，等待实时加密数据",
    evidence: "insufficient_history / requires crawl",
    risk: "加密市场高波动，单一账号或链上异动不应直接定方向",
  },
  sui: {
    title: "SUI价格会涨吗：代币叙事与链上信号验证",
    core: "SUI token price sentiment",
    window: "默认观察短线：项目消息、链上活跃度、鲸鱼和交易所流向",
    sources: [
      "sui token search",
      "coindesk",
      "the block",
      "wu blockchain",
      "lookonchain",
      "santiment",
      "dex volume",
      "exchange flow",
      "whale wallet",
      "social momentum",
    ],
    rows: [
      ["项目叙事", "需要抓取 SUI 相关新闻和生态更新", "没有项目级事件时，不应只凭 crypto 大盘判断"],
      ["链上活跃", "交易量、TVL、活跃地址是辅助变量", "链上增长若无价格跟随，可能只是噪声"],
      ["鲸鱼流向", "大额流入交易所偏利空，冷钱包积累偏利多", "必须多源确认，防止单笔转账误读"],
    ],
    events: [
      ["SUI ecosystem update", "等待实时抓取确认是否有项目级催化。", ["candidate", "needs_crawl"]],
      ["Whale movement", "观察 SUI 大额地址和交易所流入流出。", ["onchain", "requires_confirmation"]],
      ["Market beta", "SUI 常受 BTC 与整体风险偏好影响。", ["risk_sentiment", "secondary"]],
    ],
    direction: "数据不足，先执行 SUI 实时抓取",
    evidence: "no_history_match / requires crawl",
    risk: "小币种更容易被叙事和流动性驱动，需避免把大盘新闻误当 SUI 信号",
  },
};

const homeScreen = document.querySelector("#homeScreen");
const analysisScreen = document.querySelector("#analysisScreen");
const homeForm = document.querySelector("#homeForm");
const homeQuery = document.querySelector("#homeQuery");
const queryInput = document.querySelector("#queryInput");
const queryForm = document.querySelector("#queryForm");
const chipGrid = document.querySelector("#chipGrid");
const signalRows = document.querySelector("#signalRows");
const eventGrid = document.querySelector("#eventGrid");
const modeText = document.querySelector("#modeText");

function pickReport(query) {
  const text = query.toLowerCase();
  if (text.includes("sui")) return reports.sui;
  if (text.includes("btc") || text.includes("比特币") || text.includes("bitcoin")) return reports.btc;
  return reports.oil;
}

function render(query) {
  const report = pickReport(query);
  queryInput.value = query;
  document.querySelector("#reportTitle").textContent = report.title;
  document.querySelector("#coreVariable").textContent = report.core;
  document.querySelector("#timeWindow").textContent = report.window;
  document.querySelector("#sourceLine").textContent = report.sources.slice(0, 7).join(", ");
  document.querySelector("#sourceCount").textContent = report.sources.length;
  document.querySelector("#successCount").textContent = report.sources.length;
  document.querySelector("#failedCount").textContent = "0";
  document.querySelector("#failureCount").textContent = "0";
  document.querySelector("#directionText").textContent = report.direction;
  document.querySelector("#evidenceText").textContent = report.evidence;
  document.querySelector("#riskText").textContent = report.risk;

  chipGrid.innerHTML = report.sources.map((source) => `<span class="chip">${source}</span>`).join("");
  signalRows.innerHTML = report.rows
    .map(
      ([signal, data, meaning]) => `
        <tr>
          <td>${signal}</td>
          <td>${data}</td>
          <td>${meaning}</td>
        </tr>
      `,
    )
    .join("");
  eventGrid.innerHTML = report.events
    .map(
      ([title, body, tags]) => `
        <div class="event-card">
          <strong>${title}</strong>
          <p>${body}</p>
          <div class="tag-row">${tags.map((tag) => `<span class="mini-tag">${tag}</span>`).join("")}</div>
        </div>
      `,
    )
    .join("");
}

function normalizeQuery(value) {
  return value.trim() || "石油价格会涨吗";
}

function showAnalysis(rawQuery) {
  const query = normalizeQuery(rawQuery);
  render(query);
  homeScreen.classList.add("hidden");
  analysisScreen.classList.remove("hidden");
  modeText.textContent = "生成界面";
  queryInput.focus();
}

function showHome() {
  analysisScreen.classList.add("hidden");
  homeScreen.classList.remove("hidden");
  modeText.textContent = "首页";
  homeQuery.value = "";
  homeQuery.focus();
}

homeForm.addEventListener("submit", (event) => {
  event.preventDefault();
  showAnalysis(homeQuery.value);
});

queryForm.addEventListener("submit", (event) => {
  event.preventDefault();
  showAnalysis(queryInput.value);
});

document.querySelector("#newQuestion").addEventListener("click", () => {
  showHome();
});

render(queryInput.value);
