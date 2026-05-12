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

function byId(id) {
  return document.getElementById(id);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function normalizeQuery(value) {
  return value.trim() || "石油价格会涨吗";
}

function setLoading(query) {
  queryInput.value = query;
  byId("reportTitle").textContent = `${query}：DeepAlpha 正在分析`;
  byId("coreVariable").textContent = "正在理解问题";
  byId("timeWindow").textContent = "正在匹配历史库和关系图谱";
  byId("sourceLine").textContent = "DeepAlpha local intelligence";
  byId("sourceCount").textContent = "0";
  byId("successCount").textContent = "0";
  byId("failedCount").textContent = "0";
  byId("failureCount").textContent = "0";
  byId("directionText").textContent = "生成中";
  byId("evidenceText").textContent = "等待分析结果";
  byId("riskText").textContent = "等待分析结果";
  byId("leadText").textContent = "正在调用本地 DeepAlpha 服务，请稍候。";
  chipGrid.innerHTML = "";
  signalRows.innerHTML = "";
  eventGrid.innerHTML = "";
  modeText.textContent = "连接本地服务";
}

function setError(query, message) {
  byId("reportTitle").textContent = `${query}：服务未连接`;
  byId("leadText").textContent = message;
  byId("directionText").textContent = "无法生成";
  byId("evidenceText").textContent = "请通过 python3 -m deepalpha_web.server 启动";
  byId("riskText").textContent = "直接用 file:// 打开只能看静态页面，不能调用项目主流程。";
  signalRows.innerHTML = `
    <tr>
      <td>启动方式</td>
      <td>python3 -m deepalpha_web.server</td>
      <td>然后打开 http://127.0.0.1:8090</td>
    </tr>
  `;
  eventGrid.innerHTML = "";
  modeText.textContent = "离线";
}

async function fetchAnalysis(query) {
  if (location.protocol === "file:") {
    throw new Error("当前是 file:// 页面。请启动 deepalpha_web.server 后从 http://127.0.0.1:8090 打开。");
  }
  const response = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  const data = await response.json();
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || "分析接口调用失败");
  }
  return data;
}

function renderAnalysis(data) {
  const plan = data.plan || {};
  const stats = data.stats || {};
  const report = data.report || {};
  const signals = plan.signals || [];
  const rows = report.rows || [];
  const events = report.events || [];

  queryInput.value = data.query || "";
  byId("reportTitle").textContent = report.title || `${data.query}：DeepAlpha 情报分析`;
  byId("coreVariable").textContent = plan.core_variable || "-";
  byId("timeWindow").textContent = plan.time_window || "-";
  byId("sourceLine").textContent = (plan.sources || []).join(", ") || "local history";
  byId("sourceCount").textContent = String(signals.length);
  byId("successCount").textContent = String(signals.filter((item) => item.status !== "error").length);
  byId("failedCount").textContent = String(signals.filter((item) => item.status === "error").length);
  byId("failureCount").textContent = String(signals.filter((item) => item.status === "error").length);
  byId("leadText").textContent = report.lead || "";
  byId("directionText").textContent = report.direction || "无明确方向";
  byId("evidenceText").textContent = report.evidence || "-";
  byId("riskText").textContent = report.risk || "-";
  modeText.textContent = `历史库 ${stats.total || 0} 条 / 相关 ${stats.relevant || 0} 条`;

  chipGrid.innerHTML = signals
    .map((signal) => `<span class="chip">${escapeHtml(signal.label || signal.provider || "signal")}</span>`)
    .join("");

  signalRows.innerHTML = rows
    .map(
      ([signal, value, meaning]) => `
        <tr>
          <td>${escapeHtml(signal)}</td>
          <td>${escapeHtml(value)}</td>
          <td>${escapeHtml(meaning)}</td>
        </tr>
      `,
    )
    .join("");

  eventGrid.innerHTML = events
    .map(
      (event) => `
        <div class="event-card">
          <strong>${escapeHtml(event.title)}</strong>
          <p>${escapeHtml(event.body)}</p>
          <div class="tag-row">${(event.tags || []).map((tag) => `<span class="mini-tag">${escapeHtml(tag)}</span>`).join("")}</div>
        </div>
      `,
    )
    .join("");
}

async function showAnalysis(rawQuery) {
  const query = normalizeQuery(rawQuery);
  homeScreen.classList.add("hidden");
  analysisScreen.classList.remove("hidden");
  setLoading(query);
  queryInput.focus();

  try {
    const data = await fetchAnalysis(query);
    renderAnalysis(data);
  } catch (error) {
    setError(query, error.message);
  }
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
