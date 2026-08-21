/* ════════════════════════════════════════════════════════════════
   AxiomDesk · 前端逻辑（原生 JS · 无构建）
   设计系统 + ECharts 图表 + 全视图渲染。红=涨 绿=跌（A股习惯）。
   ════════════════════════════════════════════════════════════════ */
(() => {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const API = "/api";

  /* ───────── 工具 ───────── */
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const isNum = (x) => x != null && !isNaN(+x);
  const fmt = (x, d = 2) => (!isNum(x) ? "—" : Number(x).toFixed(d));
  const pct = (x, d = 1) => (!isNum(x) ? "—" : `${x >= 0 ? "+" : ""}${(x * 100).toFixed(d)}%`);
  const money = (x, u = "亿") => (!isNum(x) ? "—" : `${fmt(x, 0)} ${u}`);
  const cls = (x) => (x > 0 ? "up" : x < 0 ? "down" : "muted");
  const sign = (x) => (x > 0 ? "up" : x < 0 ? "down" : "muted");
  const verdictClass = (v) => ({ "强烈买入": "strong-buy", "买入": "buy", "关注": "watch", "谨慎": "caution", "回避": "avoid" }[v] || "watch");
  const scoreColor = (s) => (s >= 8 ? "#21c08a" : s >= 6 ? "#6fcf97" : s >= 4 ? "#f5a623" : s >= 2 ? "#ef9b4d" : "#f0495e");
  const scoreBg = (s) => `background:${scoreColor(s)}`;
  const actionClass = (a) => ({ strong_buy: "bull", buy: "bull", hold: "warn", reduce: "warn", sell: "bear" }[a] || "neu");

  function toast(msg, err = false) {
    const t = $("#toast");
    t.textContent = msg; t.hidden = false; t.classList.toggle("err", err);
    clearTimeout(t._t); t._t = setTimeout(() => (t.hidden = true), 2800);
  }
  function el(tag, attrs = {}, children = []) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") e.className = v;
      else if (k === "html") e.innerHTML = v;
      else if (k === "text") e.textContent = v;
      else if (k.startsWith("on") && typeof v === "function") e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v);
    }
    (Array.isArray(children) ? children : [children]).forEach((c) => { if (c != null) e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return e;
  }

  /* ───────── 主题 ───────── */
  function applyTheme(dark) {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("ax-theme", dark ? "dark" : "light");
  }
  function initTheme() {
    const saved = localStorage.getItem("ax-theme");
    applyTheme(saved ? saved === "dark" : true);
  }
  function toggleTheme() {
    const dark = !document.documentElement.classList.contains("dark");
    applyTheme(dark);
    rerenderActive(); // 图表需按新配色重建
  }

  /* ───────── ECharts 配色与注册表 ───────── */
  const charts = new Map(); // el -> instance
  function chartPalette() {
    const dark = document.documentElement.classList.contains("dark");
    return {
      dark,
      text: dark ? "#c7d0e0" : "#1f2430",
      sub: dark ? "#7b879c" : "#6b7488",
      axis: dark ? "rgba(255,255,255,.10)" : "rgba(0,0,0,.10)",
      split: dark ? "rgba(255,255,255,.05)" : "rgba(0,0,0,.05)",
      bull: dark ? "#f0495e" : "#e0314a",
      bear: dark ? "#21c08a" : "#15935f",
      accent: "#7c5cff",
      accent2: "#3b82f6",
      amber: "#f5a623",
      surface: dark ? "#12151c" : "#ffffff",
    };
  }
  function mountChart(elx, build) {
    if (!window.echarts) return null;
    let inst = charts.get(elx);
    if (!inst) { inst = echarts.init(elx, null, { renderer: "canvas" }); charts.set(elx, inst); }
    inst.setOption(build(chartPalette()), true);
    return inst;
  }
  function clearCharts() { charts.forEach((i) => i.dispose()); charts.clear(); }
  function resizeCharts() { charts.forEach((i) => i.resize()); }
  window.addEventListener("resize", resizeCharts);

  /* ───────── 区块/卡片/表格 构造助手 ───────── */
  const sectionTitle = (text, hint = "", icon = "") =>
    `<div class="section-title"><span class="st-bar"></span>${icon ? `<svg class="ico st-ico"><use href="#${icon}"/></svg>` : ""}<span class="st-text">${esc(text)}</span>${hint ? `<span class="st-hint">${esc(hint)}</span>` : ""}</div>`;
  const card = (body, cls2 = "") => `<div class="card ${cls2}">${body}</div>`;
  const stat = (label, value, sub = "", delta = "") =>
    `<div class="stat"><div class="stat-label">${esc(label)}</div><div class="stat-value ${cls(value)}">${esc(value)}${delta ? `<span class="stat-delta ${cls(delta)}">${pct(delta)}</span>` : ""}</div>${sub ? `<div class="stat-sub">${esc(sub)}</div>` : ""}</div>`;
  const th = (t, opts = {}) => `<th class="${opts.num ? "num" : ""} ${opts.sortable ? "sortable" : ""}" ${opts.key ? `data-key="${opts.key}"` : ""}>${esc(t)}${opts.sortable ? '<span class="arr">⇅</span>' : ""}</th>`;
  const td = (t, cls2 = "") => `<td class="${cls2}">${t}</td>`;
  function table(headers, rowsHtml, cls2 = "") {
    return `<div class="table-wrap scroll"><table class="tbl">${headers}<tbody>${rowsHtml}</tbody></table></div>`;
  }
  function scoreChip(s) { return `<span class="score-chip" style="${scoreBg(s)}">${fmt(s, 1)}</span>`; }

  /* 策略芯片（选股页） */
  function strategyChip(name, count, active, onClick = "") {
    return `<button class="strategy-chip ${active ? "active" : ""}" data-sc="${esc(name)}" ${onClick ? `onclick="${onClick}"` : ""}>
      <span>${esc(name)}</span><span class="count">${count}</span></button>`;
  }

  /* 迷你 K 线 / 折线 sparkline（SVG，无 ECharts 开销） */
  function sparklineSvg(values, color) {
    if (!values || values.length < 2) return `<span class="sub">—</span>`;
    const w = 70, h = 24, min = Math.min(...values), max = Math.max(...values), range = max - min || 1;
    const pts = values.map((v, i) => `${(i / (values.length - 1)) * w},${h - ((v - min) / range) * h}`).join(" ");
    return `<svg class="sparkline" viewBox="0 0 ${w} ${h}"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  }
  function candleSparkSvg(candles, bull, bear) {
    if (!candles || candles.length < 2) return `<span class="sub">—</span>`;
    const w = 80, h = 30, n = candles.length;
    const highs = candles.map((c) => c.high), lows = candles.map((c) => c.low);
    const min = Math.min(...lows), max = Math.max(...highs), range = max - min || 1;
    const x = (i) => (i / (n - 1)) * w;
    const y = (v) => h - ((v - min) / range) * h;
    let body = "";
    candles.forEach((c, i) => {
      const up = c.close >= c.open;
      const col = up ? bull : bear;
      body += `<line x1="${x(i)}" y1="${y(c.low)}" x2="${x(i)}" y2="${y(c.high)}" stroke="${col}" stroke-width="1"/>`;
      const topY = Math.min(y(c.open), y(c.close)); const hBody = Math.max(1, Math.abs(y(c.close) - y(c.open)));
      body += `<rect x="${x(i) - 1.5}" y="${topY}" width="3" height="${hBody}" fill="${col}"/>`;
    });
    return `<svg class="mini-k" viewBox="0 0 ${w} ${h}">${body}</svg>`;
  }

  /* 从 K 线算简单支撑/压力位 */
  function computeKeyLevels(k) {
    if (!k || k.length < 20) return null;
    const last = k[k.length - 1];
    const closes = k.map((c) => c.close);
    const pivot = (Math.max(...closes.slice(-20)) + Math.min(...closes.slice(-20))) / 2;
    const atr = (() => { let s = 0; for (let i = k.length - 14; i < k.length; i++) s += Math.max(k[i].high - k[i].low, Math.abs(k[i].high - k[i - 1].close), Math.abs(k[i].low - k[i - 1].close)); return s / 14; })();
    const r1 = last.close + atr, r2 = last.close + atr * 2;
    const s1 = last.close - atr, s2 = last.close - atr * 2;
    return { close: last.close, r1, r2, s1, s2, pivot, atr };
  }

  /* ───────── 通用 mini-markdown（用于研报）───────── */
  /* ───────── 数据源诚实徽标 + 统一占位 ───────── */
  // 合成/离线判定：兼容后端返回的英文（demo/live/…）与中文（合成/演示/近似…）source 文案。
  // 注意：demo 个股 provider 返回「内置真实个股(近似基本面)」「合成演示数据(非真实行情)」，
  // 必须判定为合成，否则会误标成「实时」。
  const SYNTH_RE = /demo|offline|synthetic|mock|simulat|^none$|unknown|合成|演示|离线|模拟|近似|内置|测试|回退/i;
  function isSynth(src) {
    return SYNTH_RE.test(String(src || ""));
  }
  function sourceBadge(src) {
    if (!src) return "";
    if (isSynth(src)) return `<span class="src-badge synth">合成数据 · 离线演示</span>`;
    // 裸 token（live/real/online）无信息量，渲染为「实时数据」；具体来源（如「腾讯财经实时行情」）原样展示
    const label = /^(live|real|online|actual)$/i.test(String(src)) ? "实时数据" : `实时 · ${esc(src)}`;
    return `<span class="src-badge live">${label}</span>`;
  }
  function markSource(sectionId, source) {
    const head = $(`#${sectionId} .report-head .rh-right`);
    if (!head) return;
    const old = head.querySelector(".src-badge");
    if (old) old.remove();
    // 以「逐请求 source」为权威：真实反映本视图本请求的数据来源；
    // 仅当 source 缺失时，才回退到全局 DATA_MODE（来自 /meta），避免把配置态误当成数据态。
    const eff = (source != null && source !== "") ? source : (DATA_MODE === "live" ? "live" : "demo");
    head.insertAdjacentHTML("afterbegin", sourceBadge(eff));
  }
  const skeleton = (n = 3, h = 140, cls = "c2") =>
    `<div class="grid ${cls}">${Array.from({ length: n }).map(() => `<div class="card skeleton" style="height:${h}px"></div>`).join("")}</div>`;

  function md(text) {
    if (!text) return "";
    const lines = text.split("\n");
    let html = "", inList = false;
    const closeList = () => { if (inList) { html += "</ul>"; inList = false; } };
    for (let raw of lines) {
      let l = raw.replace(/\s+$/, "");
      if (/^\s*#{1,3}\s/.test(l)) { closeList(); html += `<div class="card-title" style="margin:14px 0 8px"><span class="st-bar"></span>${esc(l.replace(/^\s*#+\s/, ""))}</div>`; continue; }
      if (/^\s*[-*]\s+/.test(l)) { if (!inList) { html += "<ul class='md-ul'>"; inList = true; } html += `<li>${inline(l.replace(/^\s*[-*]\s+/, ""))}</li>`; continue; }
      closeList();
      if (l.trim() === "") continue;
      html += `<p class="prose" style="margin:0 0 8px">${inline(l)}</p>`;
    }
    closeList();
    return html;
  }
  function inline(s) {
    return esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`(.+?)`/g, "<code class='kbd'>$1</code>");
  }

  /* ───────── 数据获取 ───────── */
  async function get(path, params) {
    const url = new URL(API + path, location.origin);
    if (params) for (const [k, v] of Object.entries(params)) if (v != null) url.searchParams.set(k, v);
    const r = await fetch(url);
    if (!r.ok) throw new Error(`${r.status} ${path}`);
    return r.json();
  }

  /* ════════ 应用状态 ════════ */
  let current = null;        // 当前个股报告
  let currentTicker = "";
  let activeView = "overview";
  let activeArgs = {};
  let DATA_MODE = null;       // "live" | "demo"（来自 /meta，权威数据源状态）

  /* ════════ 导航 ════════ */
  const STANDALONE = {
    sentiment: "sentiment", ladder: "ladder", sector: "sector", digest: "digest",
    screener: "screener", backtest: "backtest", "signal-quality": "signal-quality",
    capital: "capital", risk: "risk", calendar: "calendar", desk: "desk",
    diagnosis: "diagnosis", research: "research", config: "config",
  };
  const RENDER = {
    sentiment: renderSentiment, ladder: renderLadder, sector: renderSector, digest: renderDigest,
    screener: renderScreener, backtest: renderBacktest, "signal-quality": renderSignalQuality,
    capital: renderCapital, risk: renderRisk, calendar: renderCalendar, desk: renderDesk,
    diagnosis: renderDiagnosis, research: renderResearch, config: loadConfig,
  };

  function setCrumb(name) { $("#crumb-cur").textContent = name; }

  function setupNav() {
    $$("#nav .nav-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        $$("#nav .nav-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        const tab = btn.dataset.tab;
        const label = btn.querySelector("span")?.textContent || tab;
        setCrumb(label);
        const view = STANDALONE[tab];
        if (view) {
          showSection(view);
          activeView = tab; activeArgs = {};
          RENDER[tab]();
          return;
        }
        // 个股报告内部 tab
        showReportTab(tab);
        activeView = tab;
        if (current) renderReportTab(tab);
        else promptAnalyze(tab);
      });
    });
  }
  function showSection(id) {
    $("#empty").hidden = true; $("#loading").hidden = true; $("#report").hidden = true;
    $$(".standalone").forEach((s) => (s.hidden = true));
    $("#" + id).hidden = false;
  }
  function showReportTab(tab) {
    $("#empty").hidden = true; $("#loading").hidden = true;
    $$(".standalone").forEach((s) => (s.hidden = true));
    $("#report").hidden = false;
    $$(".tab-panel").forEach((p) => (p.hidden = true));
    $("#tab-" + tab).hidden = false;
  }
  function promptAnalyze(tab) {
    $("#tab-" + tab).innerHTML = `<div class="empty-mini">🔍 请先在左上角输入代码并点击「分析」，再查看「${esc(tab)}」。</div>`;
  }
  function gotoTab(tab) { $(`#nav .nav-btn[data-tab="${tab}"]`)?.click(); }

  /* ════════ 加载动画 ════════ */
  const PIPELINE = [
    { n: "Task 1", name: "数据采集", desc: "22 维原始数据 fetcher" },
    { n: "Task 1.5", name: "机构建模", desc: "DCF / Comps / LBO 三段估值" },
    { n: "Task 2", name: "维度打分", desc: "20 维量化评分" },
    { n: "Task 3", name: "66 评委", desc: "9 流派投资大佬陪审团" },
    { n: "Task 4", name: "综合研判", desc: "AI 多空辩论 + 结论 + 买入区间" },
    { n: "Task 5", name: "报告组装", desc: "可视化渲染" },
  ];
  function showLoading() {
    $("#empty").hidden = true; $("#report").hidden = true;
    $$(".standalone").forEach((s) => (s.hidden = true));
    $("#loading").hidden = false;
    const ol = $("#pipeline-load"); ol.innerHTML = "";
    PIPELINE.forEach((p, i) => ol.appendChild(el("li", { id: "pl-" + i }, [
      el("div", { class: "step-no", text: String(i + 1) }),
      el("div", {}, [el("div", { class: "step-name", text: `${p.n} · ${p.name}` }), el("div", { class: "step-desc", text: p.desc })]),
      el("div", { class: "step-bar" }, el("i", {})),
    ])));
    let i = 0; const note = $("#loading-note");
    const notes = ["抓取行情与财务…", "跑 DCF / Comps / LBO…", "20 维评分中…", "召集 66 位大佬投票…", "AI 撰写多空辩论与结论…", "组装可视化报告…"];
    const tick = () => {
      if (i > 0) { const prev = $("#pl-" + (i - 1)); if (prev) { prev.classList.remove("active"); prev.classList.add("done"); } }
      if (i >= PIPELINE.length) return;
      const cur = $("#pl-" + i); if (cur) cur.classList.add("active");
      note.textContent = notes[i] || "";
      const bar = cur && cur.querySelector(".step-bar > i");
      let w = 0; const anim = setInterval(() => { w += 14; if (bar) bar.style.width = Math.min(w, 100) + "%"; if (w >= 100) clearInterval(anim); }, 60);
      i++; setTimeout(tick, 620);
    };
    tick();
  }

  /* ════════ 运行分析（异步任务链路）════════ */
  async function runAnalysis(ticker) {
    ticker = (ticker || "").trim(); if (!ticker) return;
    currentTicker = ticker;
    const depth = $("#depth").value, useAi = $("#useai").checked;
    showLoading();
    try {
      const jr = await fetch(`${API}/jobs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ticker, depth, use_ai: useAi }) });
      if (!jr.ok) throw new Error("任务创建失败");
      const { job_id } = await jr.json();
      pollJob(job_id);
    } catch (e) { toast("分析失败：" + e.message, true); $("#loading").hidden = true; $("#empty").hidden = false; }
  }
  async function pollJob(jid) {
    for (let i = 0; i < 40; i++) {
      await new Promise((r) => setTimeout(r, 500));
      try {
        const j = await (await fetch(`${API}/jobs/${jid}`)).json();
        if (j.status === "done") { current = j.result; $("#loading").hidden = true; renderAll(current, j.source); return; }
        if (j.status === "error") throw new Error(j.error || "任务执行出错");
      } catch (e) { toast("轮询失败：" + e.message, true); $("#loading").hidden = true; $("#empty").hidden = false; return; }
    }
    toast("分析超时，请重试", true); $("#loading").hidden = true; $("#empty").hidden = false;
  }

  /* ════════ 渲染总入口 ════════ */
  function renderAll(r, source) {
    clearCharts();
    const m = r.meta || {};
    $("#rh-name").textContent = m.name || "—";
    $("#rh-sub").textContent = `${m.ticker || ""} · ${m.market || ""} · ${m.industry || ""} · 来源 ${m.source || ""}`;
    $("#rh-price").textContent = isNum(m.price) ? fmt(m.price, 2) : "—";
    $("#rh-price").className = "rh-price num " + sign((r.overall_score || 0) - 5);
    const v = $("#rh-verdict"); v.textContent = r.verdict || "—"; v.className = "verdict " + verdictClass(r.verdict);
    showReportTab("overview");
    $$("#nav .nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === "overview"));
    setCrumb("概览");
    activeView = "overview";
    renderReportTab("overview");
  }
  function renderReportTab(tab) {
    if (tab === "overview") return renderOverview(current);
    if (tab === "pipeline") return renderPipeline(current);
    if (tab === "dims") return renderDims(current);
    if (tab === "jury") return renderJury(current);
    if (tab === "valuation") return renderValuation(current);
    if (tab === "debate") return renderDebate(current);
    if (tab === "zones") return renderZones(current);
    if (tab === "risks") return renderRisks(current);
    if (tab === "trap") return renderTrap(current);
  }
  function rerenderActive() {
    clearCharts();
    if (STANDALONE[activeView]) { RENDER[activeView](); return; }
    if (current) renderReportTab(activeView);
  }

  /* ════════ 个股：概览（tickflow 式：全宽 K 线 + 关键价位 + 信号）════════ */
  function renderOverview(r) {
    const m = r.meta || {}, p = $("#tab-overview");
    const sig = (r.signals || []).filter((s) => s.fired);
    const bullS = sig.filter((s) => s.side === "bullish").map((s) => `<span class="tag bull">${esc(s.name)}</span>`).join("");
    const bearS = sig.filter((s) => s.side === "bearish").map((s) => `<span class="tag bear">${esc(s.name)}</span>`).join("");
    const concl = r.ai && r.ai.core_conclusion ? md(r.ai.core_conclusion) : `<div class="muted">（未启用 AI 研判）</div>`;

    p.innerHTML = `
      <div class="grid c4" style="margin-bottom:var(--gap)">
        ${stat("现价", isNum(m.price) ? fmt(m.price, 2) : "—", m.unit || "")}
        ${stat("综合评分", fmt(r.overall_score, 1) + " /10", r.verdict || "")}
        ${stat("总市值", money(m.mcap, m.mcap_unit || "亿"), "PE " + fmt(m.pe))}
        ${stat("ROE", fmt(m.roe, 1) + "%", "营收增速 " + pct(m.revenue_growth))}
      </div>
      <div class="kline-wrap">
        <div class="card hov kline-main">
          <div class="card-head" style="margin-bottom:4px">
            <div class="card-title"><span class="st-bar"></span>个股日 K 线</div>
            <span class="card-sub">前复权 · MA5/10/20 · 成交量 · 缩放</span>
          </div>
          <div class="chart-legend" id="ov-legend"></div>
          <div id="ov-kline" class="chart xl"></div>
        </div>
        <div class="kline-side">
          <div class="card hov">
            <div class="card-title"><span class="st-bar"></span>关键价位</div>
            <div class="levels-grid" id="ov-levels">${spinnerLevels()}</div>
          </div>
          <div class="card hov">
            <div class="card-title"><span class="st-bar"></span>信号触发</div>
            <div class="card-sub" style="margin-bottom:8px">${sig.length} 个形态信号</div>
            <div style="display:flex;flex-wrap:wrap;gap:5px;margin-bottom:8px">${bullS || '<span class="muted">无多头</span>'}</div>
            <div style="display:flex;flex-wrap:wrap;gap:5px">${bearS || ""}</div>
          </div>
        </div>
      </div>
      <div class="card hov" style="margin-top:var(--gap)">
        <div class="card-title"><span class="st-bar"></span>核心结论</div>
        <div class="prose">${concl}</div>
      </div>`;
    drawKline("#ov-kline", "#ov-legend", "#ov-levels", m.ticker || currentTicker);
    refreshDsStatus();
  }

  function spinnerLevels() {
    return ["R2", "R1", "枢轴", "S1", "S2"].map((l) => `<div class="level-row"><span class="label">${l}</span><span class="off">加载中…</span></div>`).join("");
  }

  function drawKline(sel, legendSel, levelsSel, ticker) {
    const box = $(sel); if (!box) return;
    get("/kline", { ticker, days: 120 }).then((d) => {
      if (!d.available || !d.kline.length) { box.innerHTML = `<div class="empty-mini">无 K 线数据</div>`; return; }
      const k = d.kline;
      const cat = k.map((x) => x.date);
      const ohlc = k.map((x) => [x.open, x.close, x.low, x.high]);
      const vol = k.map((x, i) => [i, x.volume, x.close >= x.open ? 1 : 0]);
      const ma5 = d.ma.ma5, ma10 = d.ma.ma10, ma20 = d.ma.ma20;
      const levels = computeKeyLevels(k);
      const C = chartPalette();

      // 关键价位面板
      if (levels && $(levelsSel)) {
        const offPct = (v) => pct((v - levels.close) / levels.close);
        $(levelsSel).innerHTML = [
          ["R2 强压力", levels.r2, "up"],
          ["R1 压力", levels.r1, "up"],
          ["枢轴 P", levels.pivot, levels.pivot > levels.close ? "up" : "down"],
          ["S1 支撑", levels.s1, "down"],
          ["S2 强支撑", levels.s2, "down"],
        ].map(([lab, val, dir]) => `<div class="level-row"><span class="label">${lab}</span><div><span class="value num ${dir}">${fmt(val, 2)}</span><span class="off">${offPct(val)}</span></div></div>`).join("");
      }

      // 图例
      if ($(legendSel)) {
        $(legendSel).innerHTML = [
          ["K 线", C.bull], ["MA5", C.amber], ["MA10", C.accent2], ["MA20", C.accent],
        ].map(([n, c]) => `<span><span class="dot" style="background:${c}"></span>${n}</span>`).join("");
      }

      mountChart(box, (C) => ({
        animation: false,
        grid: [{ left: 52, right: 24, top: 10, height: "66%" }, { left: 52, right: 24, top: "78%", height: "16%" }],
        axisPointer: { link: [{ xAxisIndex: "all" }], label: { backgroundColor: C.sub } },
        tooltip: { trigger: "axis", axisPointer: { type: "cross" }, backgroundColor: C.surface, borderColor: C.axis, textStyle: { color: C.text } },
        dataZoom: [
          { type: "inside", xAxisIndex: [0, 1], start: 50, end: 100 },
          { type: "slider", xAxisIndex: [0, 1], start: 50, end: 100, height: 14, bottom: 4, borderColor: C.axis, fillerColor: "rgba(124,92,255,.15)", handleStyle: { color: C.accent }, textStyle: { color: C.sub } },
        ],
        xAxis: [
          { type: "category", data: cat, gridIndex: 0, axisLine: { lineStyle: { color: C.axis } }, axisLabel: { color: C.sub, fontSize: 10 }, axisTick: { show: false } },
          { type: "category", data: cat, gridIndex: 1, axisLine: { lineStyle: { color: C.axis } }, axisLabel: { show: false }, axisTick: { show: false } },
        ],
        yAxis: [
          { scale: true, gridIndex: 0, splitLine: { lineStyle: { color: C.split } }, axisLabel: { color: C.sub, fontSize: 10 }, axisLine: { show: false } },
          { scale: true, gridIndex: 1, splitLine: { show: false }, axisLabel: { show: false }, axisLine: { show: false } },
        ],
        series: [
          { type: "candlestick", data: ohlc, itemStyle: { color: C.bull, color0: C.bear, borderColor: C.bull, borderColor0: C.bear } },
          { type: "line", data: ma5, name: "MA5", smooth: true, showSymbol: false, lineStyle: { width: 1, color: C.amber } },
          { type: "line", data: ma10, name: "MA10", smooth: true, showSymbol: false, lineStyle: { width: 1, color: C.accent2 } },
          { type: "line", data: ma20, name: "MA20", smooth: true, showSymbol: false, lineStyle: { width: 1, color: C.accent } },
          { type: "bar", data: vol, xAxisIndex: 1, yAxisIndex: 1, itemStyle: { color: (p) => (p.data[2] ? C.bull : C.bear) } },
        ],
      }));
    }).catch((e) => (box.innerHTML = `<div class="empty-mini">K 线加载失败：${esc(e.message)}</div>`));
  }

  /* ════════ 个股：分析流水线 ════════ */
  function renderPipeline(r) {
    const p = $("#tab-pipeline");
    const steps = PIPELINE.map((s, i) => `
      <div class="list-row" style="align-items:center">
        <span class="step-no" style="background:hsl(var(--accent));color:#fff">${i + 1}</span>
        <div style="flex:1"><div class="card-title" style="margin:0">${esc(s.n)} · ${esc(s.name)}</div><div class="sub">${esc(s.desc)}</div></div>
        <span class="badge ok">已完成</span>
      </div>`).join("");
    p.innerHTML = `<div class="card"><div class="card-head"><div class="card-title"><span class="st-bar"></span>分析流水线</div><span class="card-sub">${esc((r.meta && r.meta.ticker) || "")} · 深度 ${esc(r.depth || "")}</span></div><div class="list">${steps}</div>
      <div class="callout ok" style="margin-top:14px"><span class="ct">研判来源</span>${esc(r.llm_source === "deepseek" ? "DeepSeek 驱动 · 双轨校验" : r.llm_source === "template" ? "模板叙事（未接入 LLM）" : "未启用 AI")}</div></div>`;
    refreshDsStatus();
  }

  /* ════════ 个股：维度深读 ════════ */
  function renderDims(r) {
    const p = $("#tab-dims");
    const dims = r.dimensions || [];
    const rows = dims.map((d) => `<tr>
      <td>${esc(d.name)}</td>
      <td class="num">${scoreChip(d.score)}</td>
      <td class="num muted">${fmt(d.weight, 1)}</td>
      <td><div style="display:flex;align-items:center;gap:8px"><div class="mini-bar" style="flex:1"><i style="${scoreBg(d.score)};width:${Math.max(4, d.score * 10)}%"></i></div></div></td>
      <td class="sub">${esc(d.comment || "")}</td>
    </tr>`).join("");
    p.innerHTML = `<div class="card">${sectionTitle("20 维量化评分", `${dims.length} 维`, "i-dims")}
      ${table(`<thead><tr>${th("维度")}${th("评分", { num: true })}${th("权重", { num: true })}${th("")}${th("评语")}</tr></thead>`, rows)}</div>`;
  }

  /* ════════ 个股：66 评委团 ════════ */
  function renderJury(r) {
    const p = $("#tab-jury");
    const ps = r.panel_summary || {};
    const donut = `<div class="card hov" style="display:flex;flex-direction:column;align-items:center">
      <div id="jury-donut" class="chart sm" style="height:200px"></div>
      <div class="sub" style="margin-top:4px">多头共识 ${ps.panel_consensus ?? "—"}%</div>
    </div>`;
    const groups = (r.panel_by_group || []).map((g) => `<div class="stat"><div class="stat-label">${esc(g.name)}</div><div class="stat-value" style="font-size:18px">${fmt(g.avg_score, 1)}</div><div class="stat-sub">${g.count} 人 · 多 ${g.bullish} / 空 ${g.bearish}</div></div>`).join("");
    const panel = (r.panel || []).map((x) => `<tr>
      <td><div class="name-cell">${esc(x.name)}</div><div class="sub">${esc(x.group_name)}</div></td>
      <td class="num">${scoreChip(x.score)}</td>
      <td><span class="badge ${x.signal === "bullish" ? "bull" : x.signal === "bearish" ? "bear" : "neu"}">${esc(x.verdict || x.signal)}</span></td>
      <td class="num sub">${x.confidence ?? "—"}</td>
      <td class="sub">${esc(x.comment || "")}</td>
    </tr>`).join("");
    p.innerHTML = `<div class="grid c3" style="margin-bottom:14px">${donut}<div class="card" style="grid-column:span 2">${sectionTitle("流派平均评分", "", "i-jury")}<div class="grid auto">${groups}</div></div></div>
      <div class="card">${sectionTitle("评委明细", `${ps.total ?? (r.panel || []).length} 位`, "i-jury")}${table(`<thead><tr>${th("评委")}${th("评分", { num: true })}${th("观点")}${th("置信", { num: true })}${th("点评")}</tr></thead>`, panel)}</div>`;
    mountChart($("#jury-donut"), (C) => ({
      series: [{ type: "pie", radius: ["55%", "80%"], label: { show: false }, data: [
        { value: ps.bullish ?? 0, name: "看多", itemStyle: { color: C.bull } },
        { value: ps.neutral ?? 0, name: "中性", itemStyle: { color: C.sub } },
        { value: ps.bearish ?? 0, name: "看空", itemStyle: { color: C.bear } },
      ] }],
      tooltip: { trigger: "item" },
    }));
  }

  /* ════════ 个股：估值三角 ════════ */
  function renderValuation(r) {
    const p = $("#tab-valuation");
    const v = r.valuation || {};
    const m = r.meta || {};
    const price = m.price, fair = v.fair_price;
    const upside = (isNum(price) && isNum(fair) && price) ? (fair - price) / price : null;
    const tri = valuationTriangle(price, v.dcf && v.dcf.intrinsic_per_share, v.comps && v.comps.implied_price && (v.comps.implied_price.via_median_pe || v.comps.implied_price.via_median_pb), fair);
    const model = (title, obj, key) => {
      if (!obj) return "";
      const ok = obj.verdict && !/不足|⛔|无法/.test(obj.verdict);
      return `<div class="card hov"><div class="card-title"><span class="st-bar"></span>${esc(title)}</div>
        <div class="stat-value" style="font-size:20px;color:${ok ? "hsl(var(--ok))" : "hsl(var(--warn))"}">${isNum(obj.intrinsic_per_share ?? obj.implied_price?.via_median_pe) ? fmt(obj.intrinsic_per_share ?? obj.implied_price?.via_median_pe, 2) : "—"}</div>
        <div class="stat-sub">${esc(obj.method || "")}</div>
        <div class="callout ${ok ? "ok" : "warn"}" style="margin-top:10px">${esc(obj.verdict || "")}</div></div>`;
    };
    p.innerHTML = `<div class="grid c2" style="gap:14px">
      <div class="card">${sectionTitle("估值锚三角", "现价 vs 三模型", "i-valuation")}${tri}
        <div class="callout" style="margin-top:12px"><span class="ct">综合公允价 ${isNum(fair) ? fmt(fair, 2) : "—"}</span>相对现价 ${upside == null ? "—" : `<b class="${sign(upside)}">${pct(upside)}</b>`} 空间</div>
      </div>
      <div class="grid" style="gap:14px">
        ${model("DCF 内在价值", v.dcf)}
        ${model("Comps 同业可比", v.comps)}
        ${model("LBO 杠杆收购", v.lbo)}
      </div></div>`;
  }
  function valuationTriangle(price, dcf, comps, fair) {
    const vals = [price, dcf, comps, fair].filter((v) => isNum(v) && v > 0);
    if (!vals.length) return `<div class="empty-mini">数据不足</div>`;
    const max = Math.max(...vals) * 1.1, min = Math.min(...vals) * 0.9 || 0;
    const w = 320, x = (v) => 24 + (v - min) / (max - min || 1) * (w - 48);
    const rows = [["现价", price, "var(--fg)", true], ["DCF 内在价", dcf, "var(--amber)", false], ["Comps 隐含价", comps, "var(--accent2)", false], ["综合公允价", fair, "var(--ok)", false]];
    let body = "";
    rows.forEach((rw, i) => { if (!isNum(rw[1])) return; const y = 22 + i * 34;
      body += `<line x1="24" x2="${w - 24}" y1="${y}" y2="${y}" stroke="hsl(var(--border))"/>`;
      body += `<circle cx="${x(rw[1])}" cy="${y}" r="${rw[3] ? 7 : 5}" fill="hsl(${rw[2]})" ${rw[3] ? 'stroke="#fff" stroke-width="2"' : ""}/>`;
      body += `<text x="${w - 20}" y="${y + 4}" text-anchor="end" font-size="11" fill="hsl(${rw[2]})">${fmt(rw[1], 2)}</text>`;
      body += `<text x="24" y="${y + 4}" font-size="11" fill="hsl(var(--fg-3))">${rw[0]}</text>`;
    });
    return `<svg width="${w}" height="160" viewBox="0 0 ${w} 160" style="max-width:100%">${body}</svg>`;
  }

  /* ════════ 个股：多空辩论 ════════ */
  function renderDebate(r) {
    const p = $("#tab-debate");
    const gd = r.great_divide || {};
    const ai = (r.ai && r.ai.great_divide) || {};
    const rounds = (ai.bull_say_rounds && ai.bear_say_rounds)
      ? ai.bull_say_rounds.map((b, i) => ({ bull: b, bear: ai.bear_say_rounds[i], topic: (gd.rounds && gd.rounds[i] && gd.rounds[i].topic) || `议题 ${i + 1}` }))
      : (gd.rounds || []);
    const cards = rounds.map((rd, i) => `<div class="card hov"><div class="card-title"><span class="st-bar"></span>${esc(rd.topic || "议题 " + (i + 1))}</div>
      <div class="callout bull" style="border-color:hsl(var(--bull)/.3);background:hsl(var(--bull)/.07)"><span class="ct" style="color:hsl(var(--bull))">▲ ${esc(gd.bull || "看多")}</span>${esc(rd.bull || "")}</div>
      <div class="callout bear" style="margin-top:8px;border-color:hsl(var(--bear)/.3);background:hsl(var(--bear)/.07)"><span class="ct" style="color:hsl(var(--bear))">▼ ${esc(gd.bear || "看空")}</span>${esc(rd.bear || "")}</div></div>`).join("");
    p.innerHTML = `<div class="card" style="margin-bottom:14px">${sectionTitle("多空辩论", `${esc(gd.bull || "—")} vs ${esc(gd.bear || "—")}`, "i-debate")}
      <div class="callout"><span class="ct">金句</span>${esc(gd.punchline || ai.punchline || "")}</div></div>
      <div class="grid c2">${cards}</div>`;
  }

  /* ════════ 个股：买入区间 ════════ */
  function renderZones(r) {
    const p = $("#tab-zones");
    const z = (r.ai && r.ai.buy_zones) || {};
    const m = r.meta || {};
    const cur = m.price;
    const map = [["value", "价值派", "var(--ok)"], ["growth", "成长派", "var(--accent2)"], ["technical", "技术派", "var(--amber)"], ["youzi", "游资派", "var(--brand)"]];
    const cards = map.map(([k, name, col]) => { const o = z[k]; if (!o) return "";
      const off = (isNum(cur) && isNum(o.price)) ? (o.price - cur) / cur : null;
      return `<div class="card hov"><div class="card-title"><span class="st-bar" style="background:hsl(${col})"></span>${esc(name)}</div>
        <div class="stat-value" style="font-size:24px">${isNum(o.price) ? fmt(o.price, 2) : "—"}</div>
        <div class="stat-sub">相对现价 ${off == null ? "—" : `<b class="${sign(off)}">${pct(off)}</b>`}</div>
        <div class="sub" style="margin-top:8px">${esc(o.rationale || "")}</div></div>`; }).join("");
    p.innerHTML = `<div class="card"><div class="card-head"><div class="card-title"><span class="st-bar"></span>买入区间</div><span class="card-sub">现价 ${isNum(cur) ? fmt(cur, 2) : "—"}</span></div><div class="grid c4">${cards}</div></div>`;
  }

  /* ════════ 个股：风险与欺诈 ════════ */
  function renderRisks(r) {
    const p = $("#tab-risks");
    const risks = (r.ai && r.ai.risks) || [];
    const items = risks.map((t) => `<div class="list-row"><svg class="ico" style="color:hsl(var(--danger));flex:none"><use href="#i-risks"/></svg><div class="prose" style="margin:0">${esc(t)}</div></div>`).join("")
      || `<div class="empty-mini">无明显风险点</div>`;
    p.innerHTML = `<div class="card"><div class="card-head"><div class="card-title"><span class="st-bar"></span>风险提示</div></div><div class="list">${items}</div></div>`;
  }

  /* ════════ 个股：杀猪盘检测 ════════ */
  function renderTrap(r) {
    const p = $("#tab-trap");
    const t = r.trap || {};
    const rows = (t.signals || []).map((s) => `<tr><td>${esc(s.name)}</td><td><span class="badge ${s.hit ? "danger" : "ok"}">${s.hit ? "命中" : "未命中"}</span></td><td class="sub">${esc(s.evidence || "")}</td></tr>`).join("");
    const lvl = (t.trap_level || "").replace(/[🟢🟡🟠🔴]\s*/, "");
    p.innerHTML = `<div class="grid c3" style="margin-bottom:14px">
      <div class="card"><div class="stat-label">风险等级</div><div class="stat-value" style="font-size:22px;color:hsl(var(--warn))">${esc(lvl || "—")}</div><div class="stat-sub">命中 ${t.hits ?? "?"} 项信号</div></div>
      <div class="card"><div class="stat-label">加权命中</div><div class="stat-value">${t.weighted_hits ?? "—"}</div><div class="stat-sub">含用户语境加权 ${t.user_keyword_boost ?? 0}</div></div>
      <div class="card"><div class="card-title"><span class="st-bar"></span>建议</div><div class="sub" style="margin-top:6px">${esc(t.recommendation || "")}</div></div>
    </div>
    <div class="card">${sectionTitle("8 项话术/热度信号", "", "i-trap")}${table(`<thead><tr>${th("信号")}${th("状态")}${th("证据")}</tr></thead>`, rows)}</div>`;
  }

  /* ════════ 市场：情绪仪表盘 ════════ */
  async function renderSentiment() {
    const p = $("#tab-sentiment");
    p.innerHTML = `<div class="grid c4">${[1,2,3,4].map(() => `<div class="card skeleton" style="height:120px"></div>`).join("")}</div>`;
    try {
      const d = await get("/sentiment");
      const fg = d.fear_greed, band = d.fear_greed_band;
      const stats = `<div class="grid c4">
        ${stat("恐惧贪婪指数", fmt(fg, 1), band)}
        ${stat("涨跌家数", `${d.advance}/${d.decline}`, `平 ${d.flat ?? 0}`)}
        ${stat("涨停 / 跌停", `${d.limit_up} / ${d.limit_down}`, `炸板 ${d["break"] ?? 0}`)}
        ${stat("量能热度", fmt(d.turnover_heat, 0), `量比 ${fmt(d.volume_ratio, 2)}`)}
      </div>`;
      const gauge = `<div class="card hov"><div class="card-head"><div class="card-title"><span class="st-bar"></span>市场情绪</div><span class="card-sub">${esc(d.as_of || "")}</span></div><div id="ms-gauge" class="chart" style="height:240px"></div></div>`;
      const ad = `<div class="card hov"><div class="card-head"><div class="card-title"><span class="st-bar"></span>涨跌分布</div></div><div id="ms-ad" class="chart" style="height:240px"></div></div>`;
      const sig = (d.signals || []).map((s) => `<div class="list-row"><span class="badge ${s.level === "bull" ? "bull" : s.level === "bear" ? "bear" : s.level === "warn" ? "warn" : "neu"}">${esc(s.level)}</span><div class="sub" style="margin:0">${esc(s.text)}</div></div>`).join("") || `<div class="empty-mini">暂无信号</div>`;
      const breadth = (d.advance || 0) + (d.decline || 0) + (d.flat || 0);
      const breadthPct = breadth ? ((d.advance || 0) / breadth * 100) : 0;
      p.innerHTML = stats + `
        <div class="grid c3" style="margin-top:var(--gap)">
          ${gauge}
          ${ad}
          <div class="card hov"><div class="card-head"><div class="card-title"><span class="st-bar"></span>情绪信号</div></div><div class="list" style="max-height:240px;overflow:auto">${sig}</div></div>
        </div>
        <div class="card hov" style="margin-top:var(--gap)">
          <div class="card-head"><div class="card-title"><span class="st-bar"></span>市场宽度</div><span class="card-sub">上涨占比 ${fmt(breadthPct, 1)}%</span></div>
          <div class="mini-bar" style="height:8px"><i style="background:hsl(var(--bull));width:${breadthPct}%"></i></div>
        </div>`;
      const C = chartPalette();
      mountChart($("#ms-gauge"), (c) => ({
        series: [{ type: "gauge", min: 0, max: 100, splitNumber: 5, radius: "92%", center: ["50%", "60%"],
          axisLine: { lineStyle: { width: 14, color: [[0.25, c.bear], [0.45, "#f5a623"], [0.55, "#e0d34d"], [0.75, "#f5a623"], [1, c.bull]] } },
          pointer: { itemStyle: { color: "auto" } }, axisTick: { show: false }, splitLine: { length: 12, lineStyle: { color: c.sub } },
          axisLabel: { color: c.sub, fontSize: 10, distance: 16 }, detail: { valueAnimation: true, fontSize: 26, fontWeight: 800, color: "auto", formatter: "{value}", offsetCenter: [0, "38%"] },
          title: { offsetCenter: [0, "72%"], color: c.sub, fontSize: 12 }, data: [{ value: Math.round(fg), name: band }] }],
      }));
      mountChart($("#ms-ad"), (c) => ({
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
        grid: { left: 80, right: 20, top: 10, bottom: 20 },
        xAxis: { type: "value", axisLabel: { color: c.sub }, splitLine: { lineStyle: { color: c.split } } },
        yAxis: { type: "category", data: ["跌停", "下跌", "平盘", "上涨", "涨停"], axisLabel: { color: c.text }, axisLine: { lineStyle: { color: c.axis } } },
        series: [{ type: "bar", data: [
          { value: d.limit_down, itemStyle: { color: c.bear } }, { value: d.decline, itemStyle: { color: c.bear } },
          { value: d.flat ?? 0, itemStyle: { color: c.sub } }, { value: d.advance, itemStyle: { color: c.bull } },
          { value: d.limit_up, itemStyle: { color: c.bull } },
        ], label: { show: true, position: "right", color: c.text, fontSize: 11 } }],
      }));
      refreshDsStatus(d.source);
      markSource("sentiment", d.source);
    } catch (e) { p.innerHTML = `<div class="empty-mini">情绪数据加载失败：${esc(e.message)}</div>`; }
  }

  /* ════════ 市场：连板梯队（tickflow 式：分层卡片墙 + 概念标签）════════ */
  async function renderLadder() {
    const p = $("#tab-ladder");
    p.innerHTML = `<div class="grid c4">${[1,2,3,4].map(() => `<div class="card skeleton" style="height:90px"></div>`).join("")}</div>`;
    try {
      const d = await get("/limit-ladder");
      const stats = `<div class="grid c4" style="margin-bottom:var(--gap)">
        ${stat("涨停总数", d.total_limit ?? "—", `最高 ${d.max_boards ?? 0} 板`)}
        ${stat("炸板率", pct(d.break_rate, 1), d.break_rate > 0.25 ? "偏高" : "正常")}
        ${stat("连板梯队", (d.ladder || []).length, "个层级")}
        ${stat("情绪", (d.emotion && d.emotion.stage) || "—", (d.emotion && d.emotion.side) || "")}
      </div>`;

      const tiers = (d.ladder || []).map((t) => {
        const cards = (t.stocks || []).map((s) => {
          const tags = (s.concepts || []).slice(0, 3).map((c) => `<span class="tag">${esc(c)}</span>`).join("");
          return `<div class="stock-card">
            <div class="name">${esc(s.name)}</div>
            <div class="code">${esc(s.ticker)}${s.industry ? " · " + esc(s.industry) : ""}</div>
            <div class="meta">
              <span class="${s.change_pct >= 0 ? "up" : "down"}">${pct(s.change_pct)}</span>
              ${s.mcap_yi ? `<span class="sub">市值 ${fmt(s.mcap_yi)}亿</span>` : ""}
            </div>
            <div class="tags">${tags}</div>
          </div>`;
        }).join("");
        return `<div class="tier">
          <div class="tier-head">
            <span class="tier-title">${t.board} 连板</span>
            <span class="tier-count">${t.count} 只</span>
          </div>
          <div class="tier-row">${cards || '<span class="muted">—</span>'}</div>
        </div>`;
      }).join("");

      const hot = (d.hot_sectors || []).map((s) => `<tr><td>${esc(s.name)}</td><td class="num">${s.limit_count}</td><td class="num">${fmt(s.share * 100, 1)}%</td></tr>`).join("");
      const anom = (d.anomalies || []).map((a) => `<div class="list-row"><span class="badge ${a.level === "good" ? "ok" : a.level === "warn" ? "warn" : "neu"}">${esc(a.type)}</span><div class="sub" style="margin:0">${esc(a.msg)}</div></div>`).join("");
      p.innerHTML = stats + tiers + `
        <div class="grid c2" style="margin-top:var(--gap)">
          <div class="card hov">${sectionTitle("热点板块主线", "", "i-sector")}${table(`<thead><tr>${th("板块")}${th("涨停数", { num: true })}${th("占比", { num: true })}</tr></thead>`, hot)}</div>
          <div class="card hov"><div class="card-head"><div class="card-title"><span class="st-bar"></span>异动信号</div></div><div class="list">${anom || '<div class="empty-mini">无</div>'}</div></div>
        </div>`;
      refreshDsStatus(d.source);
      markSource("ladder", d.source);
    } catch (e) { p.innerHTML = `<div class="empty-mini">连板数据加载失败：${esc(e.message)}</div>`; }
  }

  /* ════════ 市场：板块轮动 ════════ */
  async function renderSector() {
    const p = $("#tab-sector");
    p.innerHTML = `<div class="card skeleton" style="height:300px"></div>`;
    try {
      const d = await get("/sector-rotation", { top_n: 25 });
      const top = (d.industry || []).slice(0, 12);
      const allBoards = (d.industry || []).concat(d.concept || []).slice(0, 40);
      const sectorRow = (b) => `<tr><td>${esc(b.name)}</td><td class="num ${sign(b.change_pct)}">${pct(b.change_pct)}</td><td class="num ${sign(b.chg_5d)}">${pct(b.chg_5d)}</td><td class="num ${sign(b.chg_10d)}">${pct(b.chg_10d)}</td><td class="num ${sign(b.net_inflow_yi)}">${money(b.net_inflow_yi)}</td></tr>`;
      const rows = allBoards.map(sectorRow).join("");
      p.innerHTML = `<div class="grid c2" style="gap:14px">
        <div class="card hov"><div class="card-head"><div class="card-title"><span class="st-bar"></span>行业 10 日涨幅 Top</div></div><div id="sec-chart" class="chart" style="height:300px"></div></div>
        <div class="card hov">${sectionTitle("板块轮动矩阵", "今日/5日/10日 · 主力净流入", "i-sector")}${table(`<thead><tr>${th("板块")}${th("今日", { num: true, sortable: true, key: "change_pct" })}${th("5日", { num: true, sortable: true, key: "chg_5d" })}${th("10日", { num: true, sortable: true, key: "chg_10d" })}${th("主力净流入", { num: true, sortable: true, key: "net_inflow_yi" })}</tr></thead>`, rows)}</div>
      </div>`;
      const C = chartPalette();
      mountChart($("#sec-chart"), (c) => ({
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
        grid: { left: 80, right: 20, top: 10, bottom: 20 },
        xAxis: { type: "value", axisLabel: { color: c.sub, formatter: (v) => (v * 100).toFixed(0) + "%" }, splitLine: { lineStyle: { color: c.split } } },
        yAxis: { type: "category", data: top.map((b) => b.name).reverse(), axisLabel: { color: c.text, fontSize: 11 }, axisLine: { lineStyle: { color: c.axis } } },
        series: [{ type: "bar", data: top.map((b) => ({ value: +(b.chg_10d * 100).toFixed(2), itemStyle: { color: b.chg_10d >= 0 ? c.bull : c.bear } })).reverse(), label: { show: true, position: "right", color: c.text, fontSize: 10, formatter: "{c}%" } }],
      }));
      makeSortable($("#tab-sector table"), allBoards, sectorRow);
      refreshDsStatus(d.source);
      markSource("sector", d.source);
    } catch (e) { p.innerHTML = `<div class="empty-mini">板块数据加载失败：${esc(e.message)}</div>`; }
  }

  /* ════════ 选股引擎（tickflow 式：策略芯片 + 紧凑表 + 信号标签）════════ */
  async function renderScreener() {
    const p = $("#tab-screener");
    const uni = $("#sc-universe").value, sort = $("#sc-sort").value;
    p.innerHTML = `<div class="card skeleton" style="height:300px"></div>`;
    try {
      const d = await get("/screener", { universe: uni, sort, limit: 30 });
      markSource("screener", d.source);
      const stocks = d.stocks || [];
      const activeFilter = p.dataset.filter || "";

      // 策略芯片：统计所有出现过的多头信号
      const signalCounts = {};
      stocks.forEach((s) => (s.bull_signals || []).forEach((sig) => { signalCounts[sig] = (signalCounts[sig] || 0) + 1; }));
      const chips = Object.entries(signalCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10)
        .map(([name, cnt]) => strategyChip(name, cnt, name === activeFilter, "filterScreener(this)"))
        .join("");
      const filtered = activeFilter ? stocks.filter((s) => (s.bull_signals || []).includes(activeFilter)) : stocks;

      const screenerRow = (s, i) => {
        const tags = (s.bull_signals || []).slice(0, 4).map((t) => `<span class="tag bull">${esc(t)}</span>`).join("");
        const momColor = s.momentum > 0 ? "#f0495e" : s.momentum < 0 ? "#21c08a" : "#7b879c";
        return `<tr><td class="rank">${i + 1}</td><td><div class="name-cell">${esc(s.name)}</div><div class="sub">${esc(s.ticker)}</div></td><td class="sub">${esc(s.industry || "")}</td>
          <td class="num">${isNum(s.price) ? fmt(s.price, 2) : "—"}</td>
          <td class="num"><div style="display:flex;align-items:center;gap:6px;justify-content:flex-end"><span class="score-chip" style="${scoreBg(s.score / 10)}">${fmt(s.score, 1)}</span></div></td>
          <td class="num">${fmt(s.rps, 1)}</td>
          <td class="num">${fmt(s.momentum, 1)}</td>
          <td class="num">${sparklineSvg([Math.max(0, s.rps), Math.max(0, s.momentum + 50), Math.max(0, s.score / 2), Math.max(0, s.signal_count * 10)], momColor)}</td>
          <td class="num">${s.signal_count}</td>
          <td style="display:flex;flex-wrap:wrap;gap:3px">${tags}</td></tr>`;
      };
      const rows = filtered.map(screenerRow).join("");
      p.innerHTML = `
        <div class="card">
          <div class="card-head">
            <div class="card-title"><span class="st-bar"></span>选股结果</div>
            <span class="card-sub">扫描 ${d.scanned ?? 0} · 命中 ${filtered.length}/${d.matched ?? 0} · 池=${esc(uni)}</span>
          </div>
          <div class="chip-set" style="margin-bottom:10px">${chips}</div>
          ${table(`<thead><tr>${th("#")}${th("名称")}${th("行业")}${th("现价", { num: true })}${th("评分", { num: true, sortable: true, key: "score" })}${th("RPS", { num: true, sortable: true, key: "rps" })}${th("动量", { num: true, sortable: true, key: "momentum" })}${th("趋势", { num: true })}${th("信号数", { num: true, sortable: true, key: "signal_count" })}${th("多头信号")}</tr></thead>`, rows)}
        </div>`;
      window.filterScreener = (btn) => {
        const name = btn.dataset.sc;
        p.dataset.filter = p.dataset.filter === name ? "" : name;
        renderScreener();
      };
      makeSortable($("#tab-screener table"), filtered, screenerRow);
      window._screenerStocks = stocks; // 保留原始数据用于排序/过滤
    } catch (e) { p.innerHTML = `<div class="empty-mini">选股失败：${esc(e.message)}</div>`; }
  }

  /* ════════ 信号回测 ════════ */
  async function renderBacktest() {
    const p = $("#tab-backtest");
    const tk = $("#bt-ticker").value.trim() || "600519";
    p.innerHTML = `<div class="card skeleton" style="height:300px"></div>`;
    try {
      const d = await get("/backtest", { ticker: tk, days: 130 });
      markSource("backtest", d.source);
      if (!d.available) { p.innerHTML = `<div class="empty-mini">${esc(d.reason || "无数据")}</div>`; return; }
      const eq = d.equity || {};
      const curve = (eq.curve || []);
      const stats = `<div class="grid c4">
        ${stat("总收益", pct(eq.total_return), "")}
        ${stat("最大回撤", pct(eq.max_drawdown), "")}
        ${stat("夏普", fmt(eq.sharpe, 2), "")}
        ${stat("样本K线", eq.bars ?? "—", "")}
      </div>`;
      const sig = (d.signal_stats || []).map((s) => {
        const h5 = s.horizons && s.horizons["5"]; const h20 = s.horizons && s.horizons["20"];
        return `<tr><td>${esc(s.signal_id)}</td><td class="num">${s.samples ?? "—"}</td>
          <td class="num ${sign(h5 ? h5.win_rate - 0.5 : 0)}">${h5 ? fmt(h5.win_rate * 100, 1) + "%" : "—"}</td>
          <td class="num ${sign(h20 ? h20.avg_return : 0)}">${h20 ? pct(h20.avg_return) : "—"}</td>
          <td>${s.available ? '<span class="badge ok">可用</span>' : '<span class="badge warn">样本不足</span>'}</td></tr>`;
      }).join("");
      p.innerHTML = stats + `<div class="grid c2" style="margin-top:14px">
        <div class="card hov"><div class="card-head"><div class="card-title"><span class="st-bar"></span>演示净值曲线</div><span class="card-sub">${esc(d.name || tk)}</span></div><div id="bt-eq" class="chart" style="height:260px"></div></div>
        <div class="card hov">${sectionTitle("信号胜率（5日/20日）", "", "i-backtest")}${table(`<thead><tr>${th("信号")}${th("样本", { num: true })}${th("5日胜率", { num: true })}${th("20日收益", { num: true })}${th("")}</tr></thead>`, sig)}</div>
      </div>`;
      const C = chartPalette();
      mountChart($("#bt-eq"), (c) => ({
        tooltip: { trigger: "axis" }, grid: { left: 50, right: 16, top: 16, bottom: 30 },
        xAxis: { type: "category", data: curve.map((_, i) => i), axisLabel: { show: false }, axisLine: { lineStyle: { color: c.axis } } },
        yAxis: { scale: true, splitLine: { lineStyle: { color: c.split } }, axisLabel: { color: c.sub, formatter: (v) => (v * 100 - 100).toFixed(0) + "%" } },
        series: [{ type: "line", data: curve, smooth: true, showSymbol: false, lineStyle: { color: c.accent, width: 2 }, areaStyle: { color: "rgba(124,92,255,.12)" } }],
      }));
    } catch (e) { p.innerHTML = `<div class="empty-mini">回测失败：${esc(e.message)}</div>`; }
  }

  /* ════════ 信号胜率表 ════════ */
  async function renderSignalQuality() {
    const p = $("#tab-signal-quality");
    p.innerHTML = `<div class="card skeleton" style="height:300px"></div>`;
    try {
      const d = await get("/signal-quality");
      const rows = (d.signal_stats || []).map((s) => {
        const h5 = s.horizons && s.horizons["5"], h10 = s.horizons && s.horizons["10"], h20 = s.horizons && s.horizons["20"];
        const reliable = h5 && h5.win_rate >= 0.55 && h20 && h20.avg_return > 0;
        return `<tr><td>${esc(s.signal_id)}</td><td class="num">${s.samples ?? "—"}</td>
          <td class="num ${sign(h5 ? h5.win_rate - 0.5 : 0)}">${h5 ? fmt(h5.win_rate * 100, 1) + "%" : "—"}</td>
          <td class="num ${sign(h10 ? h10.win_rate - 0.5 : 0)}">${h10 ? fmt(h10.win_rate * 100, 1) + "%" : "—"}</td>
          <td class="num ${sign(h20 ? h20.win_rate - 0.5 : 0)}">${h20 ? fmt(h20.win_rate * 100, 1) + "%" : "—"}</td>
          <td class="num ${sign(h20 ? h20.avg_return : 0)}">${h20 ? pct(h20.avg_return) : "—"}</td>
          <td>${reliable ? '<span class="badge ok">高可靠</span>' : '<span class="badge neu">—</span>'}</td></tr>`;
      }).join("");
      p.innerHTML = `<div class="card">${sectionTitle("18 形态信号历史胜率", "跨标的回测 · N=5/10/20 日", "i-signal")}
        ${table(`<thead><tr>${th("信号")}${th("样本", { num: true })}${th("5日胜率", { num: true })}${th("10日胜率", { num: true })}${th("20日胜率", { num: true })}${th("20日收益", { num: true })}${th("可靠度")}</tr></thead>`, rows)}</div>`;
    } catch (e) { p.innerHTML = `<div class="empty-mini">计算失败：${esc(e.message)}</div>`; }
  }

  /* ════════ 资金流向 ════════ */
  async function renderCapital() {
    const p = $("#tab-capital");
    const tk = $("#cf-ticker").value.trim() || "600519";
    p.innerHTML = `<div class="grid c4">${[1,2,3,4].map(() => `<div class="card skeleton" style="height:120px"></div>`).join("")}</div>`;
    try {
      const [ind, board, north] = await Promise.all([
        get("/capital-flow", { ticker: tk }).catch(() => ({})),
        get("/capital-flow/board", { scope: "industry", topn: 12 }).catch(() => ({ rows: [] })),
        get("/capital-flow/north").catch(() => ({})),
      ]);
      const t = ind.tiers || {};
      const xlabels = ["超大单", "大单", "中单", "小单"];
      const today = xlabels.map((k) => (t[k] && t[k].today_yi) || 0);
      const d20 = xlabels.map((k) => (t[k] && t[k].twenty_d_yi) || 0);
      const stats = `<div class="grid c4">
        ${stat("主力净流入(今日)", money(ind.main_net_inflow_yi), "", ind.main_net_inflow_yi)}
        ${stat("主力净流入(20日)", money(ind.main_net_inflow_20d_yi), "", ind.main_net_inflow_20d_yi)}
        ${stat("占流通比", fmt(ind.main_pct_float, 2) + "%", ind.strength_grade || "")}
        ${stat("北向合计(今日)", money(north.tgt_yi), north.trend || "")}
      </div>`;
      const bar = `<div class="card hov"><div class="card-head"><div class="card-title"><span class="st-bar"></span>五档资金流 · ${esc(ind.name || tk)}</div><span class="badge ${ind.verdict && /流入/.test(ind.verdict) ? "bull" : "bear"}">${esc(ind.verdict || "")}</span></div><div id="cf-bar" class="chart" style="height:240px"></div></div>`;
      const boardRows = (board.rows || []).map((b) => `<tr><td>${esc(b.name)}</td><td class="num ${sign(b.change_pct)}">${pct(b.change_pct)}</td><td class="num ${sign(b.net_inflow_yi)}">${money(b.net_inflow_yi)}</td><td class="num">${fmt(b.net_ratio, 1)}%</td></tr>`).join("");
      const boardCard = `<div class="card hov">${sectionTitle("行业板块资金榜", "", "i-sector")}${table(`<thead><tr>${th("板块")}${th("涨幅", { num: true })}${th("主力净流入", { num: true })}${th("净占比", { num: true })}</tr></thead>`, boardRows)}</div>`;
      p.innerHTML = stats + `<div class="grid c2" style="margin-top:14px">${bar}${boardCard}</div>`;
      const C = chartPalette();
      mountChart($("#cf-bar"), (c) => ({
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" } }, legend: { data: ["今日", "20日"], textStyle: { color: c.sub }, top: 0 },
        grid: { left: 60, right: 20, top: 30, bottom: 20 },
        xAxis: { type: "category", data: xlabels, axisLabel: { color: c.text }, axisLine: { lineStyle: { color: c.axis } } },
        yAxis: { type: "value", axisLabel: { color: c.sub, formatter: (v) => v + "亿" }, splitLine: { lineStyle: { color: c.split } } },
        series: [
          { name: "今日", type: "bar", data: today.map((v) => ({ value: +v.toFixed(2), itemStyle: { color: v >= 0 ? c.bull : c.bear } })) },
          { name: "20日", type: "bar", data: d20.map((v) => ({ value: +v.toFixed(2), itemStyle: { color: v >= 0 ? c.accent2 : c.sub } })) },
        ],
      }));
      refreshDsStatus(ind.source || board.source);
      markSource("capital", ind.source || board.source);
    } catch (e) { p.innerHTML = `<div class="empty-mini">资金数据加载失败：${esc(e.message)}</div>`; }
  }

  /* ════════ 风险监控 ════════ */
  async function renderRisk() {
    const p = $("#tab-risk");
    const tk = $("#rk-ticker").value.trim();
    p.innerHTML = `<div class="card skeleton" style="height:240px"></div>`;
    try {
      const d = await get("/risk-watch", tk ? { ticker: tk } : {});
      if (tk && d.single) {
        const s = d.single; const lu = s.lockup || {};
        const rows = [
          ["PE", fmt(s.pe), s.valuation_anomaly ? `<span class="badge danger">${esc(s.valuation_anomaly)}</span>` : '<span class="badge ok">正常</span>'],
          ["PB", fmt(s.pb), ""],
          ["解禁", lu.has_lockup ? `${esc(lu.unlock_date)} · ${money(lu.unlock_yi)} · 压力 ${esc(lu.pressure || "")}` : "无解禁"],
          ["减持压力", (lu.three_lines && lu.three_lines.can_reduce) ? "存在减持条件" : "暂无"],
        ].map((r) => `<tr><td>${r[0]}</td><td class="num">${r[1]}</td><td>${r[2]}</td></tr>`).join("");
        p.innerHTML = `<div class="card">${sectionTitle("个股风险 · " + esc(s.name || tk), "", "i-risk")}${table(`<thead><tr>${th("指标")}${th("值", { num: true })}${th("评估")}</tr></thead>`, rows)}<div class="callout warn" style="margin-top:12px"><span class="ct">风险标签</span>${(s.risk_tags || []).map((t) => `<span class="tag warn">${esc(t)}</span>`).join(" ") || "无明显标签"}</div></div>`;
      } else {
        const la = (d.lockup_alerts || []).map((x) => `<tr><td>${esc(x.name)}</td><td class="num">${fmt(x.pe)}</td><td>${money(x.lockup?.unlock_yi)}</td><td><span class="badge ${x.lockup?.pressure === "高" ? "danger" : "warn"}">${esc(x.lockup?.pressure || "")}</span></td></tr>`).join("");
        const va = (d.valuation_alerts || []).map((x) => `<tr><td>${esc(x.name)}</td><td class="num">${fmt(x.pe)}</td><td>${esc(x.valuation_anomaly || "")}</td></tr>`).join("");
        p.innerHTML = `<div class="grid c2" style="gap:14px">
          <div class="card hov">${sectionTitle("解禁减持预警", `扫描 ${d.scanned ?? 0}`, "i-risk")}${table(`<thead><tr>${th("标的")}${th("PE", { num: true })}${th("解禁规模", { num: true })}${th("压力")}</tr></thead>`, la)}</div>
          <div class="card hov">${sectionTitle("估值异常扫描", "", "i-risks")}${table(`<thead><tr>${th("标的")}${th("PE", { num: true })}${th("异常")}</tr></thead>`, va)}</div>
        </div>`;
      }
      refreshDsStatus(d.source);
      markSource("risk", d.source);
    } catch (e) { p.innerHTML = `<div class="empty-mini">风险扫描失败：${esc(e.message)}</div>`; }
  }

  /* ════════ 财经日历 ════════ */
  async function renderCalendar() {
    const p = $("#tab-calendar");
    const days = $("#cal-days").value; const tk = $("#cal-ticker").value.trim();
    p.innerHTML = `<div class="card skeleton" style="height:240px"></div>`;
    try {
      const d = await get("/event-calendar", tk ? { ticker: tk, days } : { days });
      const rows = (d.events || []).map((e) => `<tr><td class="num">${esc(e.date)}</td><td><span class="badge">${esc(e.type)}</span></td><td>${esc(e.detail)}</td><td><span class="badge ${/多/.test(e.impact || "") ? "bull" : /空|稀释/.test(e.impact || "") ? "bear" : "neu"}">${esc(e.impact || "")}</span></td>${tk ? "" : `<td class="sub">${esc(e.name || "")}</td>`}</tr>`).join("");
      const head = tk ? `<thead><tr>${th("日期", { num: true })}${th("类型")}${th("详情")}${th("影响")}</tr></thead>` : `<thead><tr>${th("日期", { num: true })}${th("类型")}${th("详情")}${th("影响")}${th("标的")}</tr></thead>`;
      p.innerHTML = `<div class="card">${sectionTitle("财经日历", `未来 ${days} 日 · ${esc(d.source || "")}`, "i-calendar")}${table(head, rows)}</div>`;
      refreshDsStatus(d.source);
      markSource("calendar", d.source);
    } catch (e) { p.innerHTML = `<div class="empty-mini">日历加载失败：${esc(e.message)}</div>`; }
  }

  /* ════════ 自选 · 监控 ════════ */
  async function renderDesk() {
    const p = $("#tab-desk");
    p.innerHTML = `<div class="grid c2"><div class="card skeleton" style="height:200px"></div><div class="card skeleton" style="height:200px"></div></div>`;
    try {
      const [wl, ev] = await Promise.all([get("/watchlist").catch(() => ({ items: [] })), get("/events", { limit: 30 }).catch(() => ({ items: [] }))]);
      const items = (wl.items || []).map((w) => `<tr><td><div class="name-cell">${esc(w.name || w.ticker)}</div><div class="sub">${esc(w.ticker)}</div></td>
        <td class="num">${isNum(w.price) ? fmt(w.price, 2) : "—"}</td>
        <td class="num ${sign(w.change_pct)}">${pct(w.change_pct)}</td>
        <td class="num ${sign((w.profit_pct ?? 0))}">${pct(w.profit_pct)}</td>
        <td class="sub">${esc(w.note || "")}</td>
        <td><button class="btn btn-ghost sm" data-del="${esc(w.ticker)}">移除</button></td></tr>`).join("");
      const evRows = (ev.items || []).map((e) => `<tr><td class="sub">${esc(e.time || "")}</td><td>${esc(e.name || "")}</td><td><span class="badge ${actionClass(e.action)}">${esc(e.action || "")}</span></td><td class="sub">${esc(e.detail || "")}</td></tr>`).join("");
      p.innerHTML = `<div class="grid c2" style="gap:14px">
        <div class="card hov"><div class="card-head"><div class="card-title"><span class="st-bar"></span>自选股</div><span class="card-sub">${wl.count ?? 0} 只</span></div>
          ${wl.items && wl.items.length ? table(`<thead><tr>${th("标的")}${th("现价", { num: true })}${th("涨跌", { num: true })}${th("收益", { num: true })}${th("备注")}${th("")}</tr></thead>`, items) : '<div class="empty-mini">自选为空，可在个股页点击「＋自选」</div>'}</div>
        <div class="card hov"><div class="card-head"><div class="card-title"><span class="st-bar"></span>盘中预警事件</div><span class="card-sub">${(ev.stats && ev.stats.total) || 0} 条</span></div>
          ${ev.items && ev.items.length ? table(`<thead><tr>${th("时间")}${th("标的")}${th("动作")}${th("详情")}</tr></thead>`, evRows) : '<div class="empty-mini">暂无预警事件</div>'}</div>
      </div>`;
      $$("#tab-desk [data-del]").forEach((b) => b.addEventListener("click", async () => {
        await fetch(`${API}/watchlist/${b.dataset.del}`, { method: "DELETE" }); toast("已移除"); renderDesk();
      }));
      const badge = $("#desk-badge"); if (badge) { const n = (ev.items || []).length; if (n) { badge.hidden = false; badge.textContent = n; } else badge.hidden = true; }
    } catch (e) { p.innerHTML = `<div class="empty-mini">加载失败：${esc(e.message)}</div>`; }
  }

  /* ════════ 自选 · 盘中预警扫描 ════════ */
  async function checkDeskAlerts() {
    const btn = $("#desk-refresh");
    if (!btn) return renderDesk();
    const oldHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<svg class="ico spin"><use href="#i-refresh"/></svg>扫描中…`;
    try {
      const r = await fetch(`${API}/monitor/check`, { method: "POST" });
      if (!r.ok) throw new Error(`${r.status}`);
      const d = await r.json();
      const n = (d.new_events || []).length;
      toast(n ? `扫描完成，新增 ${n} 条盘中预警` : "扫描完成，当前无新增预警");
    } catch (e) { toast("预警扫描失败：" + e.message, true); }
    finally { btn.disabled = false; btn.innerHTML = oldHtml; renderDesk(); }
  }

  /* ════════ 个股全景诊断 ════════ */
  async function renderDiagnosis() {
    const p = $("#tab-diagnosis");
    const tk = $("#dx-ticker").value.trim() || "600519";
    p.innerHTML = `<div class="grid c3">${[1,2,3].map(() => `<div class="card skeleton" style="height:140px"></div>`).join("")}</div>`;
    try {
      const d = await get("/diagnosis", { ticker: tk });
      if (!d.available) { p.innerHTML = `<div class="empty-mini">${esc(d.reason || "无数据")}</div>`; return; }
      const dims = d.dimensions || {};
      const radar = `<div class="card hov" style="display:flex;flex-direction:column;align-items:center"><div id="dx-radar" class="chart" style="height:300px"></div></div>`;
      const gauge = `<div class="card hov" style="display:flex;flex-direction:column;align-items:center"><div class="stat-label" style="align-self:flex-start">综合研判</div><div id="dx-gauge" class="chart" style="height:240px;width:100%"></div><div class="badge ${actionClass(d.action_en)}" style="margin-top:4px;font-size:13px;padding:6px 16px">${esc(d.action)}</div></div>`;
      const dimCards = Object.entries(dims).map(([k, v]) => {
        const name = { technical: "技术面", capital: "资金面", sentiment: "情绪面", valuation: "估值面", event: "事件面", risk: "风控面" }[k] || k;
        return `<div class="card hov"><div class="card-head"><div class="card-title"><span class="st-bar"></span>${esc(name)}</div>${scoreChip(v.score)}</div><div class="stat-sub">${esc(v.note || "")}</div></div>`;
      }).join("");
      p.innerHTML = `<div class="grid c2" style="gap:14px">${radar}${gauge}</div>
        <div class="grid c3" style="margin-top:14px">${dimCards}</div>
        <div class="card hov" style="margin-top:14px"><div class="card-head"><div class="card-title"><span class="st-bar"></span>结论</div><span class="card-sub">综合 ${fmt(d.composite, 1)} 分</span></div><div class="prose">${esc(d.conclusion || "")}</div>
          <div class="callout warn" style="margin-top:10px"><span class="ct">风险标记</span>${(d.risk_flags || []).map((t) => `<span class="tag warn">${esc(t)}</span>`).join(" ") || "无"}</div></div>`;
      const C = chartPalette();
      mountChart($("#dx-radar"), (c) => ({
        tooltip: {}, radar: { indicator: [["技术面", 100], ["资金面", 100], ["情绪面", 100], ["估值面", 100], ["事件面", 100], ["风控面", 100]].map(([n, m]) => ({ name: n, max: m })),
          axisName: { color: c.text }, splitLine: { lineStyle: { color: c.split } }, splitArea: { areaStyle: { color: [c.surface, "transparent"] } }, axisLine: { lineStyle: { color: c.axis } } },
        series: [{ type: "radar", data: [{ value: [dims.technical?.score, dims.capital?.score, dims.sentiment?.score, dims.valuation?.score, dims.event?.score, dims.risk?.score], areaStyle: { color: "rgba(124,92,255,.25)" }, lineStyle: { color: c.accent }, itemStyle: { color: c.accent } }] }],
      }));
      mountChart($("#dx-gauge"), (c) => ({
        series: [{ type: "gauge", startAngle: 210, endAngle: -30, min: 0, max: 100, radius: "95%", center: ["50%", "55%"],
          progress: { show: true, width: 14, itemStyle: { color: scoreColor(d.composite / 10) } }, axisLine: { lineStyle: { width: 14, color: [[1, c.split]] } },
          axisTick: { show: false }, splitLine: { show: false }, axisLabel: { color: c.sub, fontSize: 9, distance: 14 }, pointer: { show: false },
          detail: { valueAnimation: true, fontSize: 30, fontWeight: 800, color: "auto", formatter: "{value}", offsetCenter: [0, 0] }, data: [{ value: Math.round(d.composite) }] }],
      }));
      refreshDsStatus(d.source);
      markSource("diagnosis", d.source);
    } catch (e) { p.innerHTML = `<div class="empty-mini">诊断失败：${esc(e.message)}</div>`; }
  }

  /* ════════ 综合研报 ════════ */
  async function renderResearch() {
    const p = $("#tab-research");
    const tk = $("#rr-ticker").value.trim();
    p.innerHTML = `<div class="card skeleton" style="height:300px"></div>`;
    try {
      const d = await get("/research-report", { ticker: tk || undefined, fmt: "json" });
      if (!d.available) { p.innerHTML = `<div class="empty-mini">${esc(d.reason || "无数据")}</div>`; return; }
      const mdText = d.markdown || "";
      // 若市场日报无个股，展示市场级结构化
      let body;
      if (d.type === "market_daily") {
        const s = d.sections || {};
        const rel = (s.reliable_signals || []).map((x) => `<span class="tag bull">${esc(x.signal_id || x)}</span>`).join("");
        body = `<div class="card hov">${sectionTitle("市场日报", esc(s.header?.as_of || ""), "i-research")}
          <div class="grid c3" style="margin-bottom:12px">
            ${stat("恐惧贪婪", fmt(s.sentiment?.fear_greed, 1), s.sentiment?.fear_greed_band || "")}
            ${stat("速览", "盘后", "")}
            ${stat("可靠信号", (s.reliable_signals || []).length + " 个", "")}
          </div>
          <div class="prose">${md(s.digest?.summary || "")}</div>
          <div style="margin-top:10px">${rel || ""}</div></div>`;
      } else {
        body = `<div class="card hov">${sectionTitle("个股深度研报", esc((d.sections?.header?.name) || tk), "i-research")}
          <div class="prose" style="max-height:560px;overflow:auto">${md(mdText)}</div></div>`;
      }
      p.innerHTML = body + `<div class="card" style="margin-top:14px"><div class="card-head"><div class="card-title"><span class="st-bar"></span>Markdown 源文</div><button class="btn btn-ghost sm" id="rr-copy2"><svg class="ico"><use href="#i-copy"/></svg>复制</button></div><pre class="md-src" style="white-space:pre-wrap;font-family:var(--font-mono);font-size:11.5px;color:hsl(var(--fg-2));max-height:320px;overflow:auto;margin:0">${esc(mdText)}</pre></div>`;
      const copy = () => { navigator.clipboard?.writeText(mdText).then(() => toast("已复制 Markdown"), () => toast("复制失败", true)); };
      $("#rr-copy2").addEventListener("click", copy);
      refreshDsStatus(d.source);
      markSource("research", d.source);
    } catch (e) { p.innerHTML = `<div class="empty-mini">研报生成失败：${esc(e.message)}</div>`; }
  }

  /* ════════ 盘后速览（通用渲染）════════ */
  async function renderDigest() {
    const p = $("#tab-digest");
    p.innerHTML = `<div class="card skeleton" style="height:300px"></div>`;
    try {
      const d = await get("/daily-digest");
      const skip = ["version", "source", "as_of", "note", "digest_id", "generated_at"];
      const blocks = Object.entries(d).filter(([k]) => !skip.includes(k)).map(([k, v]) => {
        const title = k.replace(/_/g, " ");
        let inner = "";
        if (typeof v === "string") inner = `<div class="prose">${md(v)}</div>`;
        else if (Array.isArray(v)) inner = v.map((x) => `<div class="list-row"><div class="prose" style="margin:0">${typeof x === "string" ? esc(x) : esc(JSON.stringify(x))}</div></div>`).join("");
        else if (v && typeof v === "object") inner = `<div class="prose">${md(JSON.stringify(v, null, 2))}</div>`;
        else inner = `<div class="sub">${esc(String(v))}</div>`;
        return `<div class="card hov">${sectionTitle(title, "", "i-digest")}${inner}</div>`;
      }).join("");
      p.innerHTML = `<div class="grid c2" style="gap:14px">${blocks}</div>`;
      refreshDsStatus(d.source);
      markSource("digest", d.source);
    } catch (e) { p.innerHTML = `<div class="empty-mini">速览失败：${esc(e.message)}</div>`; }
  }

  /* ════════ 接口配置 ════════ */
  async function loadConfig() {
    const p = $("#tab-config");
    p.innerHTML = `<div class="card skeleton" style="height:200px"></div>`;
    try {
      const d = await get("/config");
      const cfg = d.config || {};
      const src = d.data_source_effective || cfg.data_source;
      const provRows = (d.providers || []).map((pr) => `<tr><td>${esc(pr.name || pr.id)}</td><td><span class="badge ${pr.available ? "ok" : "warn"}">${pr.available ? "可用" : "不可用"}</span></td><td class="sub">${esc(pr.note || "")}</td></tr>`).join("");
      const dsOpts = (d.providers || []).map((pr) => `<option value="${esc(pr.id)}" ${pr.id === src ? "selected" : ""}>${esc(pr.name || pr.id)}</option>`).join("");
      p.innerHTML = `<div class="card"><div class="card-head"><div class="card-title"><span class="st-bar"></span>数据源配置</div><span class="card-sub">当前：${esc(src)}</span></div>
        <div class="grid c2" style="gap:14px;align-items:end">
          <div><label class="stat-label">数据源</label><select id="cfg-ds" class="q-select" style="width:100%;margin-top:6px">${dsOpts || ""}</select></div>
          <button id="cfg-save" class="btn btn-primary">保存并重建链路</button>
        </div>
        <div class="card-sub" style="margin-top:14px">数据源状态</div>
        ${table(`<thead><tr>${th("数据源")}${th("状态")}${th("说明")}</tr></thead>`, provRows)}
      </div>`;
      $("#cfg-save").addEventListener("click", async () => {
        const ds = $("#cfg-ds").value;
        try { await fetch(`${API}/config`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ data_source: ds }) }); toast("已保存，链路已重建"); refreshDsStatus(ds); }
        catch (e) { toast("保存失败：" + e.message, true); }
      });
    } catch (e) { p.innerHTML = `<div class="empty-mini">配置加载失败：${esc(e.message)}</div>`; }
  }

  /* ════════ 数据源状态条 ════════ */
  let _metaCache = null;
  async function loadMeta(force) {
    if (_metaCache && !force) return _metaCache;
    try { _metaCache = await get("/meta"); } catch { /* 保留上次缓存 */ }
    return _metaCache;
  }
  async function refreshDsStatus(force) {
    const m = await loadMeta(force);
    if (!m) return;
    DATA_MODE = m.data_mode === "live" ? "live" : "demo";
    const box = $("#ds-status"); const live = $("#live-badge");
    if (box) box.querySelector(".ds-text").textContent = "数据源：" + (m.data_source || DATA_MODE);
    if (live) {
      const offline = DATA_MODE !== "live";
      live.classList.toggle("off", offline);
      live.lastChild.textContent = offline ? "离线" : "实时";
    }
  }

  /* ════════ 通用：可排序表格 ════════ */
  function makeSortable(tableEl, data, rowFn) {
    if (!tableEl || !rowFn) return;
    const ths = $$("thead th.sortable", tableEl);
    ths.forEach((thx) => thx.addEventListener("click", () => {
      const key = thx.dataset.key; const cur = thx.classList.contains("sorted"); const asc = cur ? thx.dataset.asc !== "1" : true;
      $$("thead th", tableEl).forEach((t) => t.classList.remove("sorted"));
      thx.classList.add("sorted"); thx.dataset.asc = asc ? "1" : "0";
      const sorted = [...data].sort((a, b) => { const x = a[key], y = b[key]; if (isNum(x) && isNum(y)) return asc ? x - y : y - x; return asc ? String(x ?? "").localeCompare(String(y ?? "")) : String(y ?? "").localeCompare(String(x ?? "")); });
      const tbody = tableEl.querySelector("tbody");
      tbody.innerHTML = sorted.map((r, i) => rowFn(r, i)).join("");
    }));
  }

  /* ════════ 历史抽屉 ════════ */
  async function openHistory() {
    const list = $("#history-list"); list.innerHTML = `<div class="empty-mini">加载中…</div>`;
    $("#history-drawer").hidden = false; $("#drawer-mask").hidden = false;
    try {
      const d = await get("/history", { limit: 40 });
      const items = (d.items || []).map((it) => `<div class="list-row" data-h="${esc(it.ticker)}" style="cursor:pointer"><div><div class="name-cell">${esc(it.name || it.ticker)}</div><div class="sub">${esc(it.ticker)} · ${esc(it.depth || "")} · ${esc(it.created_at || "")}</div></div><span class="badge ${verdictClass(it.verdict)}">${esc(it.verdict || "")}</span></div>`).join("");
      list.innerHTML = items || `<div class="empty-mini">暂无历史</div>`;
      $$("#history-list [data-h]").forEach((b) => b.addEventListener("click", () => { closeDrawer(); $("#ticker").value = b.dataset.h; runAnalysis(b.dataset.h); }));
    } catch (e) { list.innerHTML = `<div class="empty-mini">加载失败</div>`; }
  }
  function closeDrawer() { $("#history-drawer").hidden = true; $("#drawer-mask").hidden = true; }

  /* ════════ 对比弹窗 ════════ */
  async function openCompare() { $("#compare-modal").hidden = false; $("#drawer-mask").hidden = false; }
  async function runCompare() {
    const tickers = $("#cmp-tickers").value.trim(); if (!tickers) return toast("请输入代码");
    const depth = $("#cmp-depth").value; const box = $("#cmp-result"); box.innerHTML = `<div class="empty-mini">对比中…</div>`;
    try {
      const d = await get("/compare", { tickers, depth });
      const rows = (d.items || []).map((it) => `<tr><td><div class="name-cell">${esc(it.name || it.ticker)}</div><div class="sub">${esc(it.ticker)}</div></td>
        <td class="num">${isNum(it.price) ? fmt(it.price, 2) : "—"}</td><td class="num">${fmt(it.pe)}</td><td class="num">${fmt(it.pb)}</td>
        <td class="num">${fmt(it.roe, 1)}%</td><td class="num">${fmt(it.overall_score, 1)}</td><td><span class="badge ${verdictClass(it.verdict)}">${esc(it.verdict || "")}</span></td>
        <td class="num">${isNum(it.fair_price) ? fmt(it.fair_price, 2) : "—"}</td></tr>`).join("");
      box.innerHTML = `<div class="card">${sectionTitle("横向对比", `${d.count} 只`, "i-compare")}${table(`<thead><tr>${th("标的")}${th("现价", { num: true })}${th("PE", { num: true })}${th("PB", { num: true })}${th("ROE", { num: true })}${th("评分", { num: true })}${th("结论")}${th("公允价", { num: true })}</tr></thead>`, rows)}</div>`;
    } catch (e) { box.innerHTML = `<div class="empty-mini">对比失败：${esc(e.message)}</div>`; }
  }

  /* ════════ 事件绑定 ════════ */
  function bind() {
    $("#query").addEventListener("submit", (e) => { e.preventDefault(); runAnalysis($("#ticker").value); });
    $$(".q-chips .chip, .quick .chip").forEach((c) => c.addEventListener("click", () => { $("#ticker").value = c.dataset.t; runAnalysis(c.dataset.t); }));
    $("#btn-theme").addEventListener("click", toggleTheme);
    $("#btn-theme-2").addEventListener("click", toggleTheme);
    $("#btn-addwatch").addEventListener("click", async () => {
      if (!currentTicker) return toast("请先分析一只股票");
      try { await fetch(`${API}/watchlist`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ticker: currentTicker }) }); toast("已加入自选"); }
      catch (e) { toast("加入失败：" + e.message, true); }
    });
    $("#btn-history").addEventListener("click", openHistory);
    $("#history-close").addEventListener("click", closeDrawer);
    $("#btn-compare").addEventListener("click", openCompare);
    $("#compare-close").addEventListener("click", () => { $("#compare-modal").hidden = true; $("#drawer-mask").hidden = true; });
    $("#drawer-mask").addEventListener("click", closeDrawer);
    $("#cmp-run").addEventListener("click", runCompare);
    $("#rr-copy").addEventListener("click", () => { const t = $("#rr-ticker").value.trim(); get("/research-report", { ticker: t || undefined, fmt: "markdown" }).then((d) => { const txt = d.content || d.markdown || ""; navigator.clipboard?.writeText(txt).then(() => toast("已复制 Markdown"), () => toast("复制失败", true)); }).catch((e) => toast("复制失败：" + e.message, true)); });
    // 市场视图刷新/运行
    $("#ms-refresh").addEventListener("click", renderSentiment);
    $("#ladder-refresh").addEventListener("click", renderLadder);
    $("#sector-refresh").addEventListener("click", renderSector);
    $("#dg-refresh").addEventListener("click", renderDigest);
    $("#sc-scan").addEventListener("click", renderScreener);
    $("#bt-run").addEventListener("click", renderBacktest);
    $("#sq-refresh").addEventListener("click", renderSignalQuality);
    $("#cf-run").addEventListener("click", renderCapital);
    $("#cf-refresh").addEventListener("click", renderCapital);
    $("#rk-run").addEventListener("click", renderRisk);
    $("#rk-refresh").addEventListener("click", renderRisk);
    $("#cal-refresh").addEventListener("click", renderCalendar);
    $("#desk-refresh").addEventListener("click", checkDeskAlerts);
    $("#dx-run").addEventListener("click", renderDiagnosis);
    $("#rr-run").addEventListener("click", renderResearch);
  }

  /* ════════ 启动 ════════ */
  function init() {
    initTheme();
    setupNav();
    bind();
    refreshDsStatus();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
