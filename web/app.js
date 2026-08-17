/* AxiomDesk · 公理级投研终端前端逻辑（无依赖原生 JS）
 * 红=涨、绿=跌（中国习惯）。渲染 9 大板块 + 自选·监控 + 历史抽屉 + 对比弹窗。
 */
(() => {
  "use strict";

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const api = "";

  const PIPELINE = [
    { n: "Task 1", name: "数据采集", desc: "22 维原始数据 fetcher（行情/财务/行业/舆情…）" },
    { n: "Task 1.5", name: "机构建模", desc: "DCF / Comps / LBO 三段估值模型" },
    { n: "Task 2", name: "维度打分", desc: "20 维量化评分 + 定性判断" },
    { n: "Task 3", name: "66 评委", desc: "9 流派投资大佬量化陪审团" },
    { n: "Task 4", name: "综合研判", desc: "AI 多空辩论 + 核心结论 + 买入区间" },
    { n: "Task 5", name: "报告组装", desc: "可视化渲染与导出" },
  ];

  // ───────── 工具 ─────────
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fmt = (x, d = 2) => (x == null || isNaN(x)) ? "—" : Number(x).toFixed(d);
  const pct = (x) => (x == null || isNaN(x)) ? "—" : `${(x * 100 >= 0 ? "+" : "")}${(x * 100).toFixed(1)}%`;
  const money = (x, u = "亿") => (x == null || isNaN(x)) ? "—" : `${fmt(x, 0)} ${u}`;

  function verdictClass(v) {
    return { "强烈买入": "strong-buy", "买入": "buy", "关注": "watch", "谨慎": "caution", "回避": "avoid" }[v] || "watch";
  }
  function scoreColor(s) {
    if (s >= 8) return "#21c08a";
    if (s >= 6) return "#6fcf97";
    if (s >= 4) return "#f5a623";
    if (s >= 2) return "#ef9b4d";
    return "#f0495e";
  }
  function toast(msg) {
    const t = $("#toast");
    t.textContent = msg; t.hidden = false;
    clearTimeout(t._t); t._t = setTimeout(() => (t.hidden = true), 2600);
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
    (Array.isArray(children) ? children : [children]).forEach(c => {
      if (c == null) return;
      e.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return e;
  }

  // ───────── SVG ─────────
  function scoreGauge(score) {
    const r = 54, c = 2 * Math.PI * r, off = c * (1 - Math.min(10, Math.max(0, score)) / 10);
    const col = scoreColor(score);
    return `<svg width="140" height="140" viewBox="0 0 140 140">
      <circle cx="70" cy="70" r="${r}" fill="none" stroke="#16283c" stroke-width="12"/>
      <circle cx="70" cy="70" r="${r}" fill="none" stroke="${col}" stroke-width="12" stroke-linecap="round"
        stroke-dasharray="${c}" stroke-dashoffset="${off}" transform="rotate(-90 70 70)"/>
      <text x="70" y="66" text-anchor="middle" font-size="32" font-weight="800" fill="${col}">${fmt(score,1)}</text>
      <text x="70" y="88" text-anchor="middle" font-size="11" fill="#93a4bd">综合评分 /10</text>
    </svg>`;
  }
  function consensusDonut(bull, neu, bear) {
    const total = bull + neu + bear || 1;
    const segs = [["#21c08a", bull], ["#93a4bd", neu], ["#f0495e", bear]];
    const r = 52, cx = 70, cy = 70, c = 2 * Math.PI * r;
    let acc = 0, arcs = "";
    for (const [col, v] of segs) {
      const frac = v / total;
      if (frac <= 0) continue;
      const len = frac * c, gap = 2;
      arcs += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${col}" stroke-width="20"
        stroke-dasharray="${Math.max(0, len - gap)} ${c - Math.max(0, len - gap)}" stroke-dashoffset="${-acc}" transform="rotate(-90 ${cx} ${cy})"/>`;
      acc += len;
    }
    return `<svg width="140" height="140" viewBox="0 0 140 140">${arcs}
      <text x="70" y="66" text-anchor="middle" font-size="22" font-weight="800" fill="#e8eef7">${Math.round(bull/total*100)}%</text>
      <text x="70" y="86" text-anchor="middle" font-size="10" fill="#93a4bd">多头共识</text></svg>`;
  }
  function valuationTriangle(price, dcf, comps, fair) {
    const vals = [price, dcf, comps, fair].filter(v => v != null && !isNaN(v) && v > 0);
    const max = Math.max(...vals) * 1.1 || 1, min = Math.min(...vals) * 0.9 || 0;
    const w = 320, x = (v) => 20 + (v - min) / (max - min || 1) * (w - 40);
    const rows = [
      ["现价", price, "#e8eef7", true],
      ["DCF 内在价", dcf, "#4ea8ff", false],
      ["Comps 隐含价", comps, "#f5a623", false],
      ["综合公允价", fair, "#21c08a", false],
    ];
    let body = "";
    rows.forEach((rw, i) => {
      const y = 24 + i * 30;
      const col = rw[2], isP = rw[3];
      const vx = x(rw[1]);
      body += `<line x1="20" x2="${w-20}" y1="${y}" y2="${y}" stroke="#16283c" stroke-width="1"/>`;
      body += `<circle cx="${vx}" cy="${y}" r="${isP ? 7 : 5}" fill="${col}" ${isP ? 'stroke="#fff" stroke-width="2"' : ''}/>`;
      body += `<text x="${w-16}" y="${y+4}" text-anchor="end" font-size="11" fill="${col}">${fmt(rw[1],2)}</text>`;
      body += `<text x="20" y="${y+4}" font-size="11" fill="#93a4bd">${rw[0]}</text>`;
    });
    return `<svg width="${w}" height="150" viewBox="0 0 ${w} 150" style="max-width:100%">${body}</svg>`;
  }

  // ───────── 导航 ─────────
  const STANDALONE = { ladder: "market", sector: "sector", backtest: "backtest" };
  function setupNav() {
    $$("#nav .nav-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        $$("#nav .nav-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        const view = STANDALONE[btn.dataset.tab];
        if (view) {
          // 市场级独立视图（连板梯队 / 板块轮动 / 信号回测），单独显隐
          $("#empty").hidden = true;
          $("#report").hidden = true;
          $$(".standalone").forEach(s => (s.hidden = true));
          $("#" + view).hidden = false;
          $("#tab-" + view).hidden = false;
          if (view === "market") renderLadder();
          if (view === "sector") renderSectorRotation();
          if (view === "backtest") renderBacktest();
          return;
        }
        // 个股 report 内部 tab
        $("#empty").hidden = true;
        $("#report").hidden = false;
        $$(".standalone").forEach(s => (s.hidden = true));
        $$(".tab-panel").forEach(p => (p.hidden = true));
        $("#tab-" + btn.dataset.tab).hidden = false;
        if (btn.dataset.tab === "jury") renderJury();
        if (btn.dataset.tab === "valuation") renderValuation();
        if (btn.dataset.tab === "desk") renderDesk();
        if (btn.dataset.tab === "config") loadConfig();
      });
    });
  }
  function gotoTab(name) {
    const b = $(`#nav .nav-btn[data-tab="${name}"]`);
    if (b) b.click();
  }

  // ───────── 加载动画 ─────────
  function showLoading() {
    $("#empty").hidden = true; $("#report").hidden = true;
    const box = $("#loading"); box.hidden = false;
    const ol = $("#pipeline-load"); ol.innerHTML = "";
    PIPELINE.forEach((p, i) => ol.appendChild(el("li", { id: "pl-" + i }, [
      el("div", { class: "step-no", text: String(i + 1) }),
      el("div", {}, [el("div", { class: "step-name", text: `${p.n} · ${p.name}` }), el("div", { class: "step-desc", text: p.desc })]),
      el("div", { class: "step-bar" }, el("i", {})),
    ])));
    let i = 0;
    const note = $("#loading-note");
    const notes = ["抓取行情与财务…", "跑 DCF / Comps / LBO…", "20 维评分中…", "召集 66 位大佬投票…", "AI 撰写多空辩论与结论…", "组装可视化报告…"];
    const tick = () => {
      if (i > 0) { const prev = $("#pl-" + (i - 1)); if (prev) { prev.classList.remove("active"); prev.classList.add("done"); } }
      if (i >= PIPELINE.length) return;
      const cur = $("#pl-" + i); if (cur) cur.classList.add("active");
      note.textContent = notes[i] || "";
      const bar = cur && cur.querySelector(".step-bar > i");
      let w = 0;
      const anim = setInterval(() => { w += 14; if (bar) bar.style.width = Math.min(w, 100) + "%"; if (w >= 100) clearInterval(anim); }, 60);
      i++; setTimeout(tick, 620);
    };
    tick();
  }
  function finishLoading() { $("#loading").hidden = true; }
  function showEmpty() {
    $("#empty").hidden = false;
    $("#report").hidden = true;
    $("#loading").hidden = true;
  }

  // ───────── 主流程 ─────────
  let current = null;
  async function runAnalysis(ticker) {
    ticker = (ticker || "").trim();
    if (!ticker) return;
    const depth = $("#depth").value, boost = +$("#boost").value || 0, useAi = $("#useai").checked;
    showLoading();
    try {
      // 走异步任务链路：POST /jobs → 轮询 → 渲染（展示企业级异步能力）
      const jr = await fetch(`${api}/api/jobs`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, depth, boost, use_ai: useAi }),
      });
      if (!jr.ok) throw new Error("任务创建失败");
      const { job_id } = await jr.json();
      pollJob(job_id);
    } catch (e) {
      toast("分析失败：" + e.message);
      finishLoading();
      showEmpty();
    }
  }
  async function pollJob(jid) {
    for (let i = 0; i < 40; i++) {
      await new Promise(r => setTimeout(r, 500));
      try {
        const r = await fetch(`${api}/api/jobs/${jid}`);
        const j = await r.json();
        if (j.status === "done") { current = j.result; finishLoading(); renderAll(current, j.source); return; }
        if (j.status === "error") throw new Error(j.error || "任务执行出错");
      } catch (e) {
        toast("轮询失败：" + e.message); finishLoading(); showEmpty(); return;
      }
    }
    toast("分析超时，请重试"); finishLoading(); showEmpty();
  }

  // ───────── 渲染总入口 ─────────
  function renderAll(r, source) {
    const m = r.meta || {};
    // 头
    $("#rh-name").textContent = m.name || "—";
    $("#rh-sub").textContent = `${m.ticker || ""} · ${m.market || ""} · ${m.industry || ""} · 来源 ${m.source || ""}`;
    $("#rh-price").textContent = `¥${fmt(m.price)}`;
    const v = $("#rh-verdict"); v.textContent = r.verdict || "—"; v.className = "verdict " + verdictClass(r.verdict);
    const badge = $("#llm-badge");
    if (source === "deepseek") { badge.textContent = "研判：DeepSeek 在线"; badge.className = "llm-badge online"; }
    else { badge.textContent = "研判：离线模板(含人格声纹)"; badge.className = "llm-badge offline"; }

    // 数据溯源徽标：透明展示行情/基本面来源，避免「假自信」结论
    const dq = m.data_quality || {};
    const dqEl = $("#rh-dataq");
    if (dq.fundamentals) {
      const map = {
        live: ["行情·基本面 实时", "live"],
        estimated: ["行情实时 · 基本面由 PE/PB 估算", "est"],
        demo: ["离线演示合成数据", "demo"],
      };
      const [txt, cls] = map[dq.fundamentals] || ["—", ""];
      dqEl.textContent = "数据：" + txt;
      dqEl.className = "rh-dataq " + cls;
      dqEl.hidden = false;
    } else {
      dqEl.hidden = true;
    }

    renderOverview(r);
    renderDims(r);
    renderRisks(r);
    renderTrap(r);
    // jury / valuation / debate / zones 为懒渲染（tab 切换时）
    renderDebate(r); renderZones(r);
    $("#empty").hidden = true; $("#report").hidden = false;
    gotoTab("overview");
  }

  // ───────── 概览 ─────────
  function renderOverview(r) {
    const m = r.meta || {}, ai = r.ai || {};
    const panel = $("#tab-overview"); panel.innerHTML = "";
    const grpMap = {}; (r.panel_by_group || []).forEach(g => (grpMap[g.id] = g.color));

    // 数据可信度声明（当基本面为估算/演示时高亮提示）
    if (r.data_disclaimer) {
      panel.appendChild(el("div", { class: "data-disclaimer", text: r.data_disclaimer }));
    }

    const left = el("div", { class: "gauge-wrap" }, [
      el("div", { class: "card", style: "display:flex;flex-direction:column;align-items:center;gap:6px" }, [
        el("div", { html: scoreGauge(r.overall_score) }),
        el("div", { class: "gauge-cap", text: `结论「${r.verdict || "—"}」` }),
      ]),
    ]);
    const right = el("div", { class: "gauge-wrap" }, [
      el("div", { class: "card", style: "display:flex;flex-direction:column;align-items:center;gap:8px;width:100%" }, [
        el("div", { html: consensusDonut(r.panel_summary?.bullish||0, r.panel_summary?.neutral||0, r.panel_summary?.bearish||0) }),
        el("div", { class: "donut-legend" }, [
          el("div", { html: `<i style="background:#21c08a"></i>看多 ${r.panel_summary?.bullish||0}` }),
          el("div", { html: `<i style="background:#93a4bd"></i>中性 ${r.panel_summary?.neutral||0}` }),
          el("div", { html: `<i style="background:#f0495e"></i>看空 ${r.panel_summary?.bearish||0}` }),
        ]),
      ]),
    ]);
    const ovGrid = el("div", { class: "ov-grid" }, [left, right]);
    panel.appendChild(ovGrid);

    // KPI
    const kpis = [
      ["现价", `¥${fmt(m.price)}`], ["市值", money(m.mcap, m.mcap_unit)],
      ["PE", fmt(m.pe)], ["PB", fmt(m.pb)], ["ROE", `${fmt(m.roe,1)}%`],
      ["净利率", `${fmt(m.net_margin,1)}%`], ["营收增速", `${fmt(m.revenue_growth,1)}%`],
      ["负债率", pct(m.debt_ratio)], ["动量", pct(m.momentum)], ["舆情", fmt(m.sentiment,1)],
    ];
    const strip = el("div", { class: "kpi-strip" }, kpis.map(([l, v]) => el("div", { class: "kpi" }, [
      el("div", { class: "k-label", text: l }), el("div", { class: "k-val", text: v }),
    ])));
    panel.appendChild(strip);

    // 核心结论
    const cc = esc(ai.core_conclusion || "").replace(/但是/g, '<span class="but">但是</span>');
    panel.appendChild(el("div", { class: "conclusion" }, [
      el("div", { class: "c-label", text: "AI 综合研判 · 核心结论（判断靠 AI）" }),
      el("div", { class: "c-body", html: cc || "—" }),
    ]));

    // 估值三角解读
    panel.appendChild(el("div", { class: "section-title", text: "估值三角 · AI 解读" }));
    panel.appendChild(el("div", { class: "val-interp" }, [
      el("div", { class: "vi-label", text: "DCF / Comps / LBO 交叉验证" }),
      el("div", { html: esc(ai.valuation_interpretation || "—") }),
    ]));

    // 陪审团洞察
    panel.appendChild(el("div", { class: "section-title", text: "陪审团洞察 · 人格化点评" }));
    panel.appendChild(el("div", { class: "val-interp" }, [
      el("div", { html: esc((ai.panel_insights || "—")).replace(/\n/g, "<br>") }),
    ]));

    // 快速跳转
    panel.appendChild(el("div", { class: "section-title", text: "深入查看" }));
    panel.appendChild(el("div", { class: "jury-toolbar" }, [
      jumpBtn("66 评委团", "jury"), jumpBtn("估值三角", "valuation"), jumpBtn("多空辩论", "debate"),
      jumpBtn("买入区间", "zones"), jumpBtn("风险与欺诈", "risks"), jumpBtn("杀猪盘", "trap"),
    ]));
  }
  function jumpBtn(label, tab) {
    return el("button", { class: "chip", onclick: () => gotoTab(tab) }, label);
  }

  // ───────── 维度 ─────────
  function renderDims(r) {
    const panel = $("#tab-dims"); panel.innerHTML = "";
    const ai = r.ai || {}; const dc = ai.dim_commentary || {};
    panel.appendChild(el("div", { class: "section-title", text: "20 维量化打分 + AI 维度评语" }));
    const wrap = el("div", { class: "card" });
    (r.dimensions || []).forEach(d => {
      const col = scoreColor(d.score);
      const row = el("div", { class: "dim-row" }, [
        el("div", { class: "dim-name", text: d.name }),
        el("div", { class: "dim-bar" }, el("i", { style: `width:${d.score*10}%;background:${col}` })),
        el("div", { class: "dim-score", style: `color:${col}`, text: fmt(d.score,1) }),
      ]);
      const c = dc[d.key];
      if (c) row.appendChild(el("div", { class: "dim-ai", html: `<b style="color:#93a4bd">${esc(d.name)}：</b>${esc(c)}` }));
      wrap.appendChild(row);
    });
    panel.appendChild(wrap);
  }

  // ───────── 评委团（人格声纹核心）─────────
  let juryFilter = { group: "", signal: "" };
  function renderJury() {
    const panel = $("#tab-jury"); panel.innerHTML = "";
    const r = current; if (!r) return;
    const grpMap = {}; (r.panel_by_group || []).forEach(g => (grpMap[g.id] = g.color));
    panel.appendChild(el("div", { class: "section-title", text: `66 位投资大佬评审团 · 各持立场、各用声纹` }));

    const toolbar = el("div", { class: "jury-toolbar" });
    const gsel = el("select", { class: "q-depth", onchange: e => { juryFilter.group = e.target.value; renderJuryCards(panel, grpMap); } });
    gsel.appendChild(el("option", { value: "" }, "全部流派"));
    (r.panel_by_group || []).forEach(g => gsel.appendChild(el("option", { value: g.id }, `${g.name} (${g.count})`)));
    const ssel = el("select", { class: "q-depth", onchange: e => { juryFilter.signal = e.target.value; renderJuryCards(panel, grpMap); } });
    [["", "全部立场"], ["bullish", "看多"], ["bearish", "看空"], ["neutral", "中性"]].forEach(([v, t]) => ssel.appendChild(el("option", { value: v }, t)));
    toolbar.appendChild(el("span", { class: "muted", text: "筛选：" }));
    toolbar.appendChild(gsel); toolbar.appendChild(ssel);
    panel.appendChild(toolbar);

    renderJuryCards(panel, grpMap);
  }
  function renderJuryCards(panel, grpMap) {
    $$(".jury-grid", panel).forEach(n => n.remove());
    const r = current;
    const grid = el("div", { class: "jury-grid" });
    (r.panel || []).forEach(inv => {
      if (juryFilter.group && inv.group !== juryFilter.group) return;
      if (juryFilter.signal && inv.signal !== juryFilter.signal) return;
      const col = grpMap[inv.group] || "#4ea8ff";
      const card = el("div", { class: "inv-card", style: `--grp:${col}` }, [
        el("div", { class: "inv-head" }, [
          el("div", {}, [el("span", { class: "inv-name", text: inv.name }), " ", el("span", { class: "inv-en", text: inv.en || "" })]),
          el("span", { class: "inv-grp", text: inv.group_name || inv.group }),
        ]),
        el("div", { class: "inv-meta" }, [
          el("span", { class: "sig " + inv.signal, text: { bullish: "看多", bearish: "看空", neutral: "中性" }[inv.signal] || inv.signal }),
          el("span", { class: "inv-score", style: `color:${scoreColor(inv.score)}`, text: `${fmt(inv.score,1)}/10` }),
          el("span", { text: `信心 ${inv.confidence||"—"}` }),
          el("span", { text: inv.verdict || "" }),
        ]),
        el("div", { class: "inv-comment", text: inv.comment || "" }),
        inv.catchphrase ? el("div", { class: "inv-quote", text: `“${inv.catchphrase}”` }) : null,
        (() => { const t = el("div", { class: "inv-tags" }); (inv.fields || []).forEach(f => t.appendChild(el("span", { class: "tag", text: f.replace(/^\d+_/, "") }))); return t; })(),
        inv.out_of_range ? el("div", { class: "inv-out", text: "⚠ 该评委不在本票射程，按基本面代理评估" }) : null,
      ]);
      grid.appendChild(card);
    });
    panel.appendChild(grid);
  }

  // ───────── 估值三角 ─────────
  function renderValuation() {
    const panel = $("#tab-valuation"); panel.innerHTML = "";
    const r = current; if (!r) return;
    const v = r.valuation || {};
    panel.appendChild(el("div", { class: "section-title", text: "估值三角 · DCF / Comps / LBO" }));

    const dcf = v.dcf || {}, comps = v.comps || {}, lbo = v.lbo || {};
    const tri = el("div", { class: "card" }, [
      el("div", { class: "vi-label", text: "三种方法给出价 vs 现价（越右越贵）" }),
      el("div", { html: valuationTriangle(r.meta?.price, dcf.intrinsic_per_share, comps.implied_price?.via_median_pe, v.fair_price) }),
    ]);

    const notes = el("div", { class: "tri-notes" });
    notes.appendChild(vmodelCard("DCF 两段 + Gordon 终值", dcf.verdict || "—", dcf.methodology_log, "#4ea8ff"));
    notes.appendChild(vmodelCard("Comps 同业可比", comps.valuation_verdict || "—", comps.methodology_log, "#f5a623"));
    notes.appendChild(vmodelCard("LBO 杠杆收购测试", lbo.verdict || "—", lbo.methodology_log, "#21c08a"));

    panel.appendChild(el("div", { class: "tri-wrap" }, [tri, notes]));

    panel.appendChild(el("div", { style: "margin-top:12px;font-size:13px;color:#93a4bd", html:
      `综合公允价 <b style="color:#21c08a">¥${fmt(v.fair_price)}</b>（锚：${v.fair_method || "—"}）` }));
  }
  function vmodelCard(name, verdict, log, col) {
    let badge = "⚪";
    if (/低估|便宜|深度|🟢/.test(verdict)) badge = "🟢";
    else if (/高估|昂贵|🔴/.test(verdict)) badge = "🔴";
    else if (/注意|略|🟡|🟠/.test(verdict)) badge = "🟡";
    return el("div", { class: "vmodel" }, [
      el("div", {}, [el("span", { class: "vm-name", text: name }), el("span", { class: "vm-badge", style: `background:${col}22;color:${col}`, text: badge + " " + verdict })]),
      el("div", { class: "vm-log", text: (log || []).join("\n") || "—" }),
    ]);
  }

  // ───────── 多空辩论 ─────────
  function renderDebate(r) {
    const panel = $("#tab-debate"); panel.innerHTML = "";
    const ai = r.ai || {}; const gd = ai.great_divide || {};
    const egd = r.great_divide || {};
    panel.appendChild(el("div", { class: "section-title", text: "多空大辩论 · 人格化角色扮演" }));

    panel.appendChild(el("div", { class: "punch", html: esc(gd.punchline || egd.punchline || "—") }));

    const bull = (gd.bull_say_rounds || []).filter(Boolean);
    const bear = (gd.bear_say_rounds || []).filter(Boolean);
    const n = Math.max(bull.length, bear.length);
    const cols = el("div", { class: "debate-cols" }, [
      el("div", { class: "debate-col" }, [el("h3", { class: "bull", text: "多方观点" })]),
      el("div", { class: "debate-col" }, [el("h3", { class: "bear", text: "空方观点" })]),
    ]);
    for (let i = 0; i < n; i++) {
      const who = parseWho(bull[i] || "");
      cols.children[0].appendChild(speech("bull", who.name, who.text, bull[i]));
      const wo = parseWho(bear[i] || "");
      cols.children[1].appendChild(speech("bear", wo.name, wo.text, bear[i]));
    }
    panel.appendChild(cols);

    // 引擎骨架补充
    if (egd.rounds && egd.rounds.length) {
      panel.appendChild(el("div", { class: "section-title", text: "结构化分歧骨架" }));
      const wrap = el("div", { class: "card" });
      egd.rounds.forEach(rt => wrap.appendChild(el("div", { style: "padding:8px 0;border-bottom:1px solid var(--border)", html:
        `<b style="color:#e8eef7">${esc(rt.topic)}</b><br><span style="color:#21c08a">多方：</span>${esc(rt.bull)}<br><span style="color:#f0495e">空方：</span>${esc(rt.bear)}` })));
      panel.appendChild(wrap);
    }
  }
  function parseWho(line) {
    const m = (line || "").match(/^([^：:]+)[：:]\s*(.*)$/s);
    if (m) return { name: m[1].trim(), text: m[2].trim() };
    return { name: "评委", text: line || "" };
  }
  function speech(side, name, text, full) {
    return el("div", { class: "speech " + side }, [
      el("span", { class: "who", text: name }),
      el("div", { text: text || full || "" }),
    ]);
  }

  // ───────── 买入区间 ─────────
  function renderZones(r) {
    const panel = $("#tab-zones"); panel.innerHTML = "";
    const ai = r.ai || {}; const bz = ai.buy_zones || {};
    const px = (r.meta && r.meta.price) || 0;
    panel.appendChild(el("div", { class: "section-title", text: "四派买入区间（价值 / 成长 / 技术 / 游资）" }));
    const order = [["value", "价值派"], ["growth", "成长派"], ["technical", "技术派"], ["youzi", "游资派"]];
    const maxP = Math.max(px, ...order.map(([k]) => bz[k]?.price || 0)) * 1.05 || 1;
    const ladder = el("div", { class: "zone-ladder" });
    order.forEach(([k, label]) => {
      const z = bz[k] || {}; const price = z.price || 0;
      const pctw = (price / maxP * 100).toFixed(1);
      const disc = price < px ? `低于现价 ${pct((px-price)/px)}` : `高于现价 ${pct((price-px)/px)}`;
      ladder.appendChild(el("div", { class: "zone" }, [
        el("div", { class: "z-name", text: label }),
        el("div", { class: "z-bar" }, el("i", { style: `width:${pctw}%` })),
        el("div", { class: "z-price", text: `¥${fmt(price)}` }),
        el("div", { class: "z-rat", text: `${z.rationale || ""} · ${disc}` }),
      ]));
    });
    panel.appendChild(ladder);
  }

  // ───────── 风险与欺诈 ─────────
  function renderRisks(r) {
    const panel = $("#tab-risks"); panel.innerHTML = "";
    const ai = r.ai || {};
    panel.appendChild(el("div", { class: "section-title", text: "风险与欺诈提示（至少 3 条 · 具体到数字/事件）" }));
    const list = el("div", { class: "risk-list" });
    (ai.risks || []).forEach((t, i) => list.appendChild(el("div", { class: "risk-item" }, [
      el("span", { class: "ri-no", text: "⚠" }), el("div", { html: esc(t) }),
    ])));
    if (!(ai.risks || []).length) list.appendChild(el("div", { class: "muted", text: "—" }));
    panel.appendChild(list);
  }

  // ───────── 杀猪盘 ─────────
  function renderTrap(r) {
    const panel = $("#tab-trap"); panel.innerHTML = "";
    const t = r.trap || {};
    panel.appendChild(el("div", { class: "section-title", text: "杀猪盘 / 欺诈信号检测（8 信号）" }));
    const head = el("div", { style: "display:flex;align-items:center;gap:14px;margin-bottom:12px" }, [
      el("div", { class: "trap-level", text: t.trap_level || "—" }),
      el("div", { class: "muted", text: `命中加权 ${t.weighted_hits ?? 0} · 用户语境加权 ${t.user_keyword_boost ?? 0}` }),
    ]);
    panel.appendChild(head);

    const table = el("table", { class: "trap-table" });
    table.appendChild(el("tr", {}, [el("th", { text: "#" }), el("th", { text: "信号" }), el("th", { text: "命中" }), el("th", { text: "证据" })]));
    (t.signals || []).forEach(s => table.appendChild(el("tr", {}, [
      el("td", { text: String(s.id) }),
      el("td", { text: s.name }),
      el("td", { html: s.hit ? '<span class="hit-yes">命中</span>' : '<span class="hit-no">未命中</span>' }),
      el("td", { class: "muted", text: s.evidence || "" }),
    ])));
    panel.appendChild(el("div", { class: "card" }, [table]));
    if (t.recommendation) panel.appendChild(el("div", { class: "trap-rec", html: esc(t.recommendation) }));
  }

  // ───────── 连板梯队 · 涨停异动监控（融合 a-stock-data / tickflow-stock-panel）─────────
  async function renderLadder() {
    const panel = $("#tab-ladder");
    panel.innerHTML = '<div class="loading-title">正在拉取全市场涨停快照…</div>';
    try {
      const d = await (await fetch(`${api}/api/limit-ladder`)).json();
      const emo = d.emotion || {};
      $("#ladder-source").hidden = false;
      $("#ladder-source").textContent = (d.source === "live" ? "实时(东财)" : "离线演示") + (d.as_of ? " · " + d.as_of : "");

      const card = (label, val) => `<div class="ov-card"><div class="ov-val">${val}</div><div class="ov-label">${label}</div></div>`;
      let html = '<div class="ladder-overview">';
      html += card("涨停家数", d.total_limit);
      html += card("最高连板", d.max_boards + " 板");
      html += card("炸板率", (d.break_rate * 100).toFixed(0) + "%");
      html += card("市场情绪", emo.stage || "—");
      html += "</div>";

      if (d.anomalies && d.anomalies.length) {
        html += '<div class="ladder-anom">';
        d.anomalies.forEach(a => { html += `<div class="anom anom-${a.level}"><b>【${a.type}】</b>${esc(a.msg)}</div>`; });
        html += "</div>";
      }

      html += '<h3 class="ladder-h">连板梯队</h3><div class="ladder">';
      (d.ladder || []).forEach(t => {
        const stocks = (t.stocks || []).map(s => `<span class="lb-stock" title="${(s.industry || "")}">${esc(s.name || s.code)}</span>`).join("");
        html += `<div class="ladder-row"><div class="lb-board">${t.board}板 <span class="lb-count">${t.count}</span></div><div class="lb-stocks">${stocks}</div></div>`;
      });
      html += "</div>";

      if (d.hot_sectors && d.hot_sectors.length) {
        html += '<h3 class="ladder-h">热点板块（涨停分布）</h3><div class="hot-sectors">';
        d.hot_sectors.forEach(s => { html += `<span class="hs">${esc(s.name)} <b>${s.limit_count}</b></span>`; });
        html += "</div>";
      }

      if (d.monitor_pool && d.monitor_pool.length) {
        html += `<h3 class="ladder-h">重点监控池（${d.monitor_count} 只 · 3板及以上）</h3><div class="mon-pool">`;
        d.monitor_pool.forEach(s => { html += `<span class="mp">${esc(s.name || s.code)} <i>${s.boards}板</i></span>`; });
        html += "</div>";
      }

      if (d.sector_flow && d.sector_flow.length) {
        html += '<h3 class="ladder-h">板块资金流（主力净流入 TOP）</h3><div class="sector-flow">';
        d.sector_flow.forEach(s => {
          const sign = s.net_inflow_yi >= 0 ? "+" : "";
          html += `<div class="sf-row"><span class="sf-name">${esc(s.name)}</span><span class="sf-pct">${(s.change_pct * 100).toFixed(2)}%</span><span class="sf-in">${sign}${s.net_inflow_yi.toFixed(1)}亿</span></div>`;
        });
        html += "</div>";
      }

      // ── 龙虎榜游资评分（融合 aiagents-stock 评分体系）──
      try {
        const lh = await (await fetch(`${api}/api/longhubang`)).json();
        if (lh && lh.rows && lh.rows.length) {
          html += `<h3 class="ladder-h">龙虎榜游资评分 <span class="lh-src">${lh.source === "live" ? "实时(东财)" : "离线演示"}</span></h3><div class="lh-list">`;
          lh.rows.forEach(r => {
            const tags = (r.tags || []).map(t => `<span class="lh-tag">${esc(t)}</span>`).join("");
            const sign = r.net_buy_yi >= 0 ? "+" : "";
            html += `<div class="lh-row lh-tier-${_lh_tier(r.total)}"><div class="lh-name">${esc(r.name)} <i>${esc(r.code)}</i></div>`
              + `<div class="lh-score">${r.total}<small>分</small></div>`
              + `<div class="lh-tier">${esc(r.tier)}</div>`
              + `<div class="lh-net">${sign}${r.net_buy_yi.toFixed(2)}亿</div>`
              + `<div class="lh-tags">${tags}</div></div>`;
          });
          html += "</div>";
        }
      } catch (_e) { /* 龙虎榜加载失败不影响梯队主视图 */ }

      html += `<div class="ladder-note">数据源：${d.source === "live" ? "实时(东财 push2ex)" : "离线演示"} · ${d.as_of || ""}${d.source !== "live" ? " · 演示数据不代表真实行情" : ""}</div>`;
      panel.innerHTML = html;
    } catch (e) {
      panel.innerHTML = `<div class="loading-title">连板数据加载失败：${esc(e.message)}</div>`;
    }
  }

  function _lh_tier(total) { return total >= 80 ? "s" : total >= 60 ? "a" : total >= 40 ? "b" : "c"; }

  // ───────── 板块轮动矩阵（融合 tickflow 轮动矩阵 + a-stock-data 板块资金流）─────────
  async function renderSectorRotation() {
    const panel = $("#tab-sector");
    panel.innerHTML = '<div class="loading-title">正在拉取板块轮动快照…</div>';
    try {
      const d = await (await fetch(`${api}/api/sector-rotation`)).json();
      $("#sector-source").hidden = false;
      $("#sector-source").textContent = (d.source === "live" ? "实时(东财)" : "离线演示") + (d.as_of ? " · " + d.as_of : "");

      const pct = v => (v * 100).toFixed(2) + "%";
      const cell = v => `<span class="${v >= 0 ? "chg-pos" : "chg-neg"}">${v >= 0 ? "+" : ""}${pct(v)}</span>`;
      const netCell = v => `<span class="${v >= 0 ? "chg-pos" : "chg-neg"}">${v >= 0 ? "+" : ""}${v.toFixed(1)}亿</span>`;

      let html = "";
      if (d.leaders && d.leaders.length) {
        html += '<div class="sr-leaders"><span class="sr-lbl">10日强势主线 ▲</span>';
        d.leaders.slice(0, 6).forEach(s => { html += `<span class="sr-chip chg-pos">${esc(s.name)} ${pct(s.chg_10d)}</span>`; });
        html += "</div>";
      }
      if (d.laggards && d.laggards.length) {
        html += '<div class="sr-leaders"><span class="sr-lbl">10日弱势板块 ▼</span>';
        d.laggards.slice(0, 6).forEach(s => { html += `<span class="sr-chip chg-neg">${esc(s.name)} ${pct(s.chg_10d)}</span>`; });
        html += "</div>";
      }

      const board = (title, rows) => {
        if (!rows || !rows.length) return "";
        let h = `<h3 class="ladder-h">${title}</h3><div class="sr-table"><div class="sr-th"><span>板块</span><span>今日</span><span>5日</span><span>10日</span><span>主力净流入</span><span>净占比</span></div>`;
        rows.forEach(r => {
          h += `<div class="sr-tr"><span class="sr-name">${esc(r.name)}</span>${cell(r.change_pct)}${cell(r.chg_5d)}${cell(r.chg_10d)}${netCell(r.net_inflow_yi)}<span class="${r.net_ratio >= 0 ? "chg-pos" : "chg-neg"}">${pct(r.net_ratio)}</span></div>`;
        });
        return h + "</div>";
      };
      html += board("行业板块", d.industry);
      html += board("概念板块", d.concept);
      html += `<div class="ladder-note">数据源：${d.source === "live" ? "实时(东财 push2 clist)" : "离线演示"} · ${d.as_of || ""}${d.source !== "live" ? " · 演示数据不代表真实行情" : ""} · 红涨绿跌</div>`;
      panel.innerHTML = html;
    } catch (e) {
      panel.innerHTML = `<div class="loading-title">板块轮动加载失败：${esc(e.message)}</div>`;
    }
  }

  // ───────── 信号胜率回测 + 净值模拟（融合 tickflow 回测 + instock rate_stats）─────────
  async function renderBacktest() {
    const panel = $("#tab-backtest");
    const ticker = ($("#bt-ticker").value || "600519").trim();
    panel.innerHTML = '<div class="loading-title">正在回放信号历史胜率…</div>';
    try {
      const d = await (await fetch(`${api}/api/backtest?ticker=${encodeURIComponent(ticker)}`)).json();
      if (!d.available) {
        panel.innerHTML = `<div class="loading-title">无法回测：${esc(d.reason || "未知原因")}</div>`;
        return;
      }
      const s = d.summary || {};
      const card = (l, v) => `<div class="ov-card"><div class="ov-val">${v}</div><div class="ov-label">${l}</div></div>`;
      let html = `<div class="ladder-overview">`;
      html += card("已回测信号", s.signals_checked ?? "—");
      html += card("样本数", s.total_samples ?? "—");
      html += card("5日胜率", s.win_rate != null ? (s.win_rate * 100).toFixed(1) + "%" : "—");
      html += card("5日均收益", s.avg_return != null ? (s.avg_return * 100).toFixed(2) + "%" : "—");
      html += "</div>";

      const eq = (d.equity || {});
      html += `<div class="bt-eq">`;
      html += `<div class="bt-eq-head">演示净值曲线（起始 1.0）· 总收益 <b class="${eq.total_return >= 0 ? "chg-pos" : "chg-neg"}">${(eq.total_return * 100).toFixed(1)}%</b> · 最大回撤 <b>${(eq.max_drawdown * 100).toFixed(1)}%</b> · 夏普 <b>${eq.sharpe ?? "—"}</b></div>`;
      html += _equitySvg(eq.curve || []) + "</div>";

      if (d.signal_stats && d.signal_stats.length) {
        html += '<h3 class="ladder-h">信号历史胜率（回放检测）</h3><div class="sr-table bt-tbl"><div class="sr-th"><span>信号</span><span>样本</span><span>1日胜率</span><span>5日胜率</span><span>20日胜率</span><span>5日均收益</span></div>';
        d.signal_stats.forEach(x => {
          const h = x.horizons || {};
          const wr = p => (h[p] ? (h[p].win_rate * 100).toFixed(0) + "%" : "—");
          const ar = p => (h[p] ? (h[p].avg_return * 100).toFixed(2) + "%" : "—");
          html += `<div class="sr-tr"><span class="sr-name">${esc(x.signal_id)}</span><span>${x.samples ?? "—"}</span><span>${wr("1")}</span><span>${wr("5")}</span><span>${wr("20")}</span><span>${ar("5")}</span></div>`;
        });
        html += "</div>";
      }
      html += `<div class="ladder-note">数据源：${d.source === "live" ? "实时行情" : "离线演示"} · 净值模拟为「强多头信号买入 / 强空头或到期卖出」演示策略，非投资建议</div>`;
      panel.innerHTML = html;
    } catch (e) {
      panel.innerHTML = `<div class="loading-title">回测加载失败：${esc(e.message)}</div>`;
    }
  }

  function _equitySvg(curve) {
    if (!curve.length) return "";
    const W = 680, H = 180, pad = 10;
    const mn = Math.min(...curve), mx = Math.max(...curve);
    const span = (mx - mn) || 1;
    const x = i => pad + (i / (curve.length - 1)) * (W - 2 * pad);
    const y = v => H - pad - ((v - mn) / span) * (H - 2 * pad);
    const pts = curve.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
    const base = y(1.0);
    return `<svg viewBox="0 0 ${W} ${H}" class="bt-svg" preserveAspectRatio="none">`
      + `<line x1="${pad}" y1="${base}" x2="${W - pad}" y2="${base}" class="bt-base"/>`
      + `<polyline points="${pts}" class="bt-line"/></svg>`;
  }

  // ───────── 自选·监控（执行层：自选/计划/预警/记忆）─────────
  async function renderDesk() {
    const panel = $("#tab-desk");
    panel.innerHTML = "";
    panel.appendChild(el("div", { class: "section-title", text: "自选股 · 操作计划 · 盘中预警 · 跨会话记忆" }));

    const form = el("div", { class: "desk-add" }, [
      el("input", { id: "dk-ticker", class: "q-ticker", placeholder: "代码/名称，如 600519" }),
      el("input", { id: "dk-cost", class: "cfg-num", type: "number", step: "0.001", min: "0", placeholder: "成本价" }),
      el("input", { id: "dk-stop", class: "cfg-num", type: "number", step: "0.001", min: "0", placeholder: "止损" }),
      el("input", { id: "dk-target", class: "cfg-num", type: "number", step: "0.001", min: "0", placeholder: "止盈" }),
      el("button", { class: "run", onclick: addWatchForm }, "加入自选"),
    ]);
    panel.appendChild(form);
    panel.appendChild(el("div", { class: "desk-actions" }, [
      el("button", { class: "ghost-btn", onclick: checkMonitor }, "⚡ 检查盘中预警"),
      el("button", { class: "ghost-btn", onclick: clearEvents }, "清空事件"),
      el("button", { class: "ghost-btn", onclick: refreshDesk }, "⟳ 刷新"),
    ]));

    panel.appendChild(el("div", { class: "section-title", text: "自选清单 · 实时盈亏" }));
    panel.appendChild(el("div", { class: "desk-box", id: "desk-watch" }));
    panel.appendChild(el("div", { class: "section-title", text: "盘中预警事件（30 分钟去重）" }));
    panel.appendChild(el("div", { class: "desk-box", id: "desk-events" }));
    panel.appendChild(el("div", { class: "section-title", text: "操作计划（多情景：主攻 / 回调低吸 / 破位离场）" }));
    panel.appendChild(el("div", { class: "desk-box", id: "desk-plans" }));
    panel.appendChild(el("div", { class: "section-title", text: "跨会话记忆" }));
    panel.appendChild(el("div", { class: "desk-box", id: "desk-memory" }));

    await Promise.all([loadWatch(), loadEvents(), loadPlans(), loadMemory()]);
    refreshBadge();
  }
  async function loadWatch() {
    const box = $("#desk-watch"); box.innerHTML = "";
    try {
      const d = await (await fetch(`${api}/api/watchlist`)).json();
      if (!(d.items || []).length) { box.appendChild(el("div", { class: "muted", text: "暂无自选，先加一只吧" })); return; }
      const table = el("table", { class: "desk-table" });
      table.appendChild(el("tr", {}, ["标的", "现价", "成本", "浮动盈亏", "止损", "止盈", "状态", "操作"].map(c => el("th", { text: c }))));
      (d.items || []).forEach(w => {
        const up = w.pnl_pct >= 0;
        table.appendChild(el("tr", {}, [
          el("td", { html: `<b>${esc(w.name)}</b><br><span class="muted">${esc(w.ticker)}</span>` }),
          el("td", { text: `¥${fmt(w.price)}` }),
          el("td", { text: `¥${fmt(w.cost)}` }),
          el("td", { class: up ? "up" : "down", text: `${pct(w.pnl_pct)} (${up ? "+" : ""}${fmt(w.pnl_abs)})` }),
          el("td", { text: w.stop_loss ? `¥${fmt(w.stop_loss)}` : "—" }),
          el("td", { text: w.target ? `¥${fmt(w.target)}` : "—" }),
          el("td", { class: "muted", text: w.live ? "实时" : "离线" }),
          el("td", {}, el("button", { class: "ghost-btn sm", onclick: () => removeWatch(w.ticker) }, "删除")),
        ]));
      });
      box.appendChild(table);
    } catch (e) { box.appendChild(el("div", { class: "muted", text: "加载失败：" + e.message })); }
  }
  async function loadEvents() {
    const box = $("#desk-events"); box.innerHTML = "";
    try {
      const d = await (await fetch(`${api}/api/events?unacknowledged=true&limit=100`)).json();
      const items = d.items || [];
      if (!items.length) { box.appendChild(el("div", { class: "muted", text: "暂无未确认预警事件" })); return; }
      const kindMap = { stop_loss: ["跌破止损", "down"], take_profit: ["触及止盈", "up"], entry: ["进入入场区", "up"], big_move: ["异动", "warn"], breakout: ["突破目标", "up"] };
      items.forEach(ev => {
        const [ktxt, kcls] = kindMap[ev.kind] || [ev.kind, "warn"];
        box.appendChild(el("div", { class: "ev-item" }, [
          el("span", { class: "ev-kind " + kcls, text: ktxt }),
          el("div", { class: "ev-msg", text: ev.message }),
          el("span", { class: "muted", text: new Date((ev.fired_at || 0) * 1000).toLocaleTimeString() }),
          el("button", { class: "ghost-btn sm", onclick: () => ackEvent(ev.id) }, "确认"),
        ]));
      });
    } catch (e) { box.appendChild(el("div", { class: "muted", text: "加载失败：" + e.message })); }
  }
  async function loadPlans() {
    const box = $("#desk-plans"); box.innerHTML = "";
    try {
      const d = await (await fetch(`${api}/api/plans`)).json();
      const items = d.items || [];
      if (!items.length) { box.appendChild(el("div", { class: "muted", text: "暂无操作计划，可先运行分析，再到「自选」或本页生成" })); return; }
      items.forEach(p => {
        box.appendChild(el("div", { class: "plan-item" }, [
          el("div", { class: "plan-head" }, [
            el("b", { text: p.name || p._ticker }),
            el("span", { class: "verdict " + verdictClass(p.verdict), text: p.verdict || "—" }),
            el("span", { class: "muted", text: `${p.direction || ""} · RR ${fmt(p.risk_reward)} · 仓位 ${p.position_pct ?? "—"}%` }),
          ]),
          el("div", { class: "plan-meta", text: `入场 ¥${fmt(p.entry_zone?.min)}~${fmt(p.entry_zone?.max)} · 止损 ¥${fmt(p.stop_loss)} · 目标 ¥${fmt(p.target_1)}/${fmt(p.target_2)}` }),
          el("div", { class: "plan-sc" }, (p.scenarios || []).map(s => el("div", { class: "plan-sc-item", text: `${s.name}：${s.condition} → ${s.action}` }))),
          el("div", { class: "plan-ops" }, [
            el("button", { class: "ghost-btn sm", onclick: () => refreshPlan(p._ticker) }, "重新生成"),
            el("button", { class: "ghost-btn sm", onclick: () => removePlan(p._ticker) }, "删除"),
          ]),
        ]));
      });
    } catch (e) { box.appendChild(el("div", { class: "muted", text: "加载失败：" + e.message })); }
  }
  async function loadMemory() {
    const box = $("#desk-memory"); box.innerHTML = "";
    const tk = (current && current.meta && current.meta.ticker) || $("#dk-ticker").value.trim();
    if (!tk) { box.appendChild(el("div", { class: "muted", text: "先运行一次分析，这里会展示该标的的历史研判记忆" })); return; }
    try {
      const d = await (await fetch(`${api}/api/memory/${encodeURIComponent(tk)}`)).json();
      if (!(d.items || []).length) { box.appendChild(el("div", { class: "muted", text: `暂无 ${tk} 的历史记忆（真实数据模式分析后自动沉淀）` })); return; }
      (d.items || []).slice(0, 10).forEach(it => {
        box.appendChild(el("div", { class: "mem-item" }, [
          el("span", { class: "mem-kind " + it.kind, text: { fact: "事实", view: "观点", decision: "决策" }[it.kind] || it.kind }),
          el("span", { class: "mem-text", text: it.content }),
        ]));
      });
    } catch (e) { box.appendChild(el("div", { class: "muted", text: "加载失败：" + e.message })); }
  }
  async function addWatchForm() {
    const tk = $("#dk-ticker").value.trim();
    if (!tk) { toast("请输入代码/名称"); return; }
    const body = { ticker: tk };
    const cost = parseFloat($("#dk-cost").value); if (!isNaN(cost) && cost > 0) body.cost = cost;
    const stop = parseFloat($("#dk-stop").value); if (!isNaN(stop) && stop > 0) body.stop_loss = stop;
    const tgt = parseFloat($("#dk-target").value); if (!isNaN(tgt) && tgt > 0) body.target = tgt;
    try {
      const r = await fetch(`${api}/api/watchlist`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const d = await r.json();
      if (!r.ok) throw new Error((d.error || d.detail) || "加入失败");
      toast(`已加入自选：${d.item?.name || tk}`);
      $("#dk-ticker").value = "";
      refreshDesk();
    } catch (e) { toast("加入失败：" + e.message); }
  }
  async function removeWatch(tk) {
    try { await fetch(`${api}/api/watchlist/${encodeURIComponent(tk)}`, { method: "DELETE" }); toast("已移除"); refreshDesk(); }
    catch (e) { toast("操作失败：" + e.message); }
  }
  async function checkMonitor() {
    toast("正在检查盘中预警…");
    try {
      const d = await (await fetch(`${api}/api/monitor/check`, { method: "POST" })).json();
      toast(`检查完成：新增 ${(d.new_events || []).length} 条事件`);
      await loadEvents(); refreshBadge();
    } catch (e) { toast("检查失败：" + e.message); }
  }
  async function ackEvent(id) {
    try { await fetch(`${api}/api/events/${id}/ack`, { method: "POST" }); loadEvents(); refreshBadge(); }
    catch (e) { toast("操作失败：" + e.message); }
  }
  async function clearEvents() {
    try { await fetch(`${api}/api/events/clear`, { method: "POST" }); toast("已清空事件"); loadEvents(); refreshBadge(); }
    catch (e) { toast("操作失败：" + e.message); }
  }
  async function refreshPlan(tk) {
    toast("正在生成操作计划…");
    try {
      const r = await fetch(`${api}/api/plans/${encodeURIComponent(tk)}`, { method: "POST" });
      const d = await r.json();
      if (!r.ok) throw new Error((d.error || d.detail) || "生成失败");
      toast("计划已更新"); loadPlans();
    } catch (e) { toast("生成失败：" + e.message); }
  }
  async function removePlan(tk) {
    try { await fetch(`${api}/api/plans/${encodeURIComponent(tk)}`, { method: "DELETE" }); toast("计划已删除"); loadPlans(); }
    catch (e) { toast("操作失败：" + e.message); }
  }
  async function refreshDesk() { await Promise.all([loadWatch(), loadEvents(), loadPlans(), loadMemory()]); }
  async function refreshBadge() {
    const b = $("#desk-badge");
    try {
      const d = await (await fetch(`${api}/api/events?unacknowledged=true&limit=1`)).json();
      const n = (d.stats || {}).unacknowledged || 0;
      if (n > 0) { b.textContent = n > 99 ? "99+" : String(n); b.hidden = false; } else b.hidden = true;
    } catch { b.hidden = true; }
  }
  async function addWatchCurrent() {
    if (!current) return;
    const m = current.meta || {};
    try {
      const r = await fetch(`${api}/api/watchlist`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ticker: m.ticker, cost: m.price }) });
      const d = await r.json();
      if (!r.ok) throw new Error((d.error || d.detail) || "加入失败");
      toast(`已加入自选：${d.item?.name || m.ticker}`); refreshBadge();
    } catch (e) { toast("加入失败：" + e.message); }
  }

  // ───────── 流水线 ─────────
  function renderPipeline() {
    const panel = $("#tab-pipeline"); panel.innerHTML = "";
    panel.appendChild(el("div", { class: "section-title", text: "分析流水线（公理级 6 段式）" }));
    const ol = el("ol", { class: "pipeline" });
    PIPELINE.forEach((p, i) => ol.appendChild(el("li", {}, [
      el("div", { class: "step-no", text: String(i + 1) }),
      el("div", {}, [el("div", { class: "step-name", text: `${p.n} · ${p.name}` }), el("div", { class: "step-desc", text: p.desc })]),
    ])));
    panel.appendChild(ol);
  }

  // ───────── 历史抽屉 ─────────
  async function openHistory() {
    $("#history-drawer").hidden = false; $("#drawer-mask").hidden = false;
    try {
      const r = await fetch(`${api}/api/history?limit=40`);
      const data = await r.json();
      const list = $("#history-list"); list.innerHTML = "";
      (data.items || []).forEach(it => {
        list.appendChild(el("div", { class: "hist-item", onclick: () => { loadHistoryItem(it.id); } }, [
          el("div", { class: "hi-top" }, [
            el("span", { class: "hi-name", text: `${it.ticker}` }),
            el("span", { class: "verdict " + verdictClass(it.verdict), text: it.verdict || "—" }),
          ]),
          el("div", { class: "hi-meta", text: `评分 ${fmt(it.overall,1)} · ${it.depth} · 来源 ${it.source || "?"} · ${new Date((it.created_at||0)*1000).toLocaleString()}` }),
        ]));
      });
      if (!(data.items || []).length) list.appendChild(el("div", { class: "muted", text: "暂无历史记录" }));
    } catch (e) { toast("历史加载失败：" + e.message); }
  }
  async function loadHistoryItem(id) {
    try {
      const r = await fetch(`${api}/api/jobs/${id}`);
      const j = await r.json();
      if (j.result) { current = j.result; finishLoading(); renderAll(current, j.source); closeDrawers(); toast("已载入历史分析"); }
    } catch (e) { toast("载入失败：" + e.message); }
  }
  function closeDrawers() { $("#history-drawer").hidden = true; $("#drawer-mask").hidden = true; $("#compare-modal").hidden = true; }

  // ───────── 对比弹窗 ─────────
  async function runCompare() {
    const tickers = $("#cmp-tickers").value.trim();
    const depth = $("#cmp-depth").value;
    if (!tickers) { toast("请输入对比标的"); return; }
    try {
      const u = `${api}/api/compare?tickers=${encodeURIComponent(tickers)}&depth=${depth}`;
      const r = await fetch(u); const data = await r.json();
      const box = $("#cmp-result"); box.innerHTML = "";
      if (!(data.items || []).length) { box.appendChild(el("div", { class: "muted", text: "无结果" })); return; }
      const table = el("table", { class: "cmp-table" });
      const cols = ["标的", "行业", "现价", "PE", "ROE%", "增速%", "评分", "结论", "公允价", "共识%", "陷阱"];
      table.appendChild(el("tr", {}, cols.map(c => el("th", { text: c }))));
      (data.items || []).forEach(it => {
        if (it.error) { table.appendChild(el("tr", {}, [el("td", { text: it.ticker }), el("td", { colspan: "10", text: "错误：" + it.error })])); return; }
        table.appendChild(el("tr", {}, [
          el("td", { html: `<b>${esc(it.name)}</b><br><span class="muted">${esc(it.ticker)}</span>` }),
          el("td", { text: it.industry || "—" }),
          el("td", { text: `¥${fmt(it.price)}` }),
          el("td", { text: fmt(it.pe) }),
          el("td", { text: fmt(it.roe, 1) }),
          el("td", { text: fmt(it.rev_growth, 1) }),
          el("td", { text: fmt(it.overall_score, 1) }),
          el("td", {}, el("span", { class: "verdict " + verdictClass(it.verdict), text: it.verdict })),
          el("td", { text: `¥${fmt(it.fair_price)}` }),
          el("td", { text: (it.consensus ?? "—") + "%" }),
          el("td", { text: it.trap_level || "—" }),
        ]));
      });
      box.appendChild(table);
    } catch (e) { toast("对比失败：" + e.message); }
  }

  // ───────── 接口配置页（数据源 + LLM）─────────
  let cfgState = null;

  async function loadConfig() {
    const panel = $("#tab-config");
    panel.innerHTML = "";
    panel.appendChild(el("div", { class: "section-title", text: "数据源 / 接口配置" }));
    panel.appendChild(el("div", { class: "muted", style: "margin:-6px 0 14px", html:
      "配置<b>实时生效</b>并持久化到本地 <code>config.json</code>（重启不丢失）。可启停 / 排序 / 增删真实数据源，并一键测试连通性。" }));
    try {
      const r = await fetch(`${api}/api/config`);
      const d = await r.json();
      cfgState = { config: d.config, providers: d.providers, effective: d.data_source_effective };
    } catch (e) {
      panel.appendChild(el("div", { class: "muted", text: "加载配置失败：" + e.message }));
      return;
    }
    renderConfig();
  }

  function renderConfig() {
    const panel = $("#tab-config");
    panel.innerHTML = "";
    panel.appendChild(el("div", { class: "section-title", text: "数据源模式" }));
    const eff = cfgState.effective;
    const banner = el("div", { class: "cfg-banner" }, [
      el("span", { class: "cfg-eff" }, `当前生效：${eff === "auto" ? "自动多源 failover" : (eff === "demo" ? "纯离线" : "指定源 " + eff)}`),
    ]);
    panel.appendChild(banner);

    // 模式选择
    const dsSel = el("select", { class: "q-depth", onchange: e => (cfgState.config.data_source = e.target.value) });
    const dsOpts = [["auto", "自动（按优先级 failover）"], ["demo", "纯离线（不联网，内置+合成）"]];
    cfgState.providers.forEach(p => dsOpts.push([p.id, "仅 " + p.name]));
    dsOpts.forEach(([v, t]) => dsSel.appendChild(el("option", { value: v }, t)));
    dsSel.value = cfgState.config.data_source;
    panel.appendChild(el("div", { class: "cfg-mode" }, [
      el("span", { class: "muted", text: "数据来源：" }),
      dsSel,
    ]));

    // 接口卡片
    panel.appendChild(el("div", { class: "section-title", text: "实时数据接口（按优先级串联 failover）" }));
    const grid = el("div", { class: "cfg-grid" });
    cfgState.providers.slice().sort((a, b) => a.priority - b.priority).forEach(p => {
      const s = cfgState.config.providers[p.id] || {};
      let badgeCls = "cfg-badge off", badgeTxt = "未启用";
      if (p.enabled) { badgeCls = "cfg-badge on"; badgeTxt = "● 已启用"; }
      else if (!p.installed) { badgeCls = "cfg-badge warn"; badgeTxt = p.requires_token && !p.has_token ? "🔑 需 token" : "⚠ 未安装"; }
      else { badgeCls = "cfg-badge idle"; badgeTxt = "○ 已安装未启用"; }

      const card = el("div", { class: "cfg-card" }, [
        el("div", { class: "cfg-head" }, [
          el("div", {}, [
            el("div", { class: "cfg-name", text: p.name }),
            el("div", { class: "cfg-desc", text: p.desc }),
          ]),
          el("span", { class: badgeCls, id: "badge-" + p.id, text: badgeTxt }),
        ]),
      ]);

      // 开关 + 优先级 + 超时
      const tog = el("input", { type: "checkbox", id: "en-" + p.id, onchange: e => {
        s.enabled = e.target.checked;
        cfgState.config.providers[p.id] = s;
        const b = $("#badge-" + p.id);
        if (b) { b.className = e.target.checked ? "cfg-badge on" : "cfg-badge idle"; b.textContent = e.target.checked ? "● 已启用" : "○ 已安装未启用"; }
      } });
      tog.checked = !!p.enabled;
      if (!p.installed && !p.requires_token) tog.disabled = true; // 未安装且没有 token 需求，仍允许尝试（部分环境可装）
      const prio = el("input", { type: "number", min: "1", max: "99", class: "cfg-num", value: String(p.priority), onchange: e => { s.priority = +e.target.value || 99; cfgState.config.providers[p.id] = s; } });
      const timeout = el("input", { type: "number", min: "1", max: "60", class: "cfg-num", value: String(p.timeout || 8), onchange: e => { s.timeout = +e.target.value || 8; cfgState.config.providers[p.id] = s; } });
      const proxy = el("input", { type: "text", class: "cfg-text", placeholder: "代理 http://...", value: p.proxy || "", onchange: e => { s.proxy = e.target.value; cfgState.config.providers[p.id] = s; } });

      const ctrl = el("div", { class: "cfg-ctrl" }, [
        el("label", { class: "cfg-inline" }, [tog, el("span", { text: "启用" })]),
        el("label", { class: "cfg-inline" }, [el("span", { class: "muted", text: "优先级" }), prio]),
        el("label", { class: "cfg-inline" }, [el("span", { class: "muted", text: "超时(s)" }), timeout]),
      ]);
      card.appendChild(ctrl);
      card.appendChild(el("div", { class: "cfg-ctrl" }, [
        el("label", { class: "cfg-full" }, [el("span", { class: "muted", text: "代理（可选）" }), proxy]),
      ]));

      // token（按需）
      if (p.requires_token) {
        const tk = el("input", { type: "password", class: "cfg-text", placeholder: "Tushare token", value: p.has_token ? "********" : "", onchange: e => { s.token = e.target.value; cfgState.config.providers[p.id] = s; } });
        card.appendChild(el("div", { class: "cfg-ctrl" }, [el("label", { class: "cfg-full" }, [el("span", { class: "muted", text: "Token" }), tk])]));
      }

      // 安装提示
      if (!p.installed && p.install) {
        card.appendChild(el("div", { class: "cfg-install", text: "未安装：" + p.install }));
      }

      // 测试
      const testBtn = el("button", { id: "test-" + p.id, class: "ghost-btn sm", onclick: () => testProvider(p.id) }, "测试连接");
      const testRes = el("span", { id: "testres-" + p.id, class: "cfg-test" });
      card.appendChild(el("div", { class: "cfg-ctrl cfg-testrow" }, [testBtn, testRes]));

      grid.appendChild(card);
    });
    panel.appendChild(grid);

    // LLM
    panel.appendChild(el("div", { class: "section-title", text: "AI 研判（DeepSeek）" }));
    const llm = cfgState.config.llm || {};
    const key = el("input", { type: "password", class: "cfg-text", placeholder: "sk-...", value: llm.api_key ? "********" : "", onchange: e => { cfgState.config.llm.api_key = e.target.value; } });
    const base = el("input", { type: "text", class: "cfg-text", value: llm.base_url || "", onchange: e => { cfgState.config.llm.base_url = e.target.value; } });
    const model = el("input", { type: "text", class: "cfg-text", value: llm.model || "", onchange: e => { cfgState.config.llm.model = e.target.value; } });
    panel.appendChild(el("div", { class: "cfg-card" }, [
      el("div", { class: "cfg-ctrl" }, [el("label", { class: "cfg-full" }, [el("span", { class: "muted", text: "API Key" }), key])]),
      el("div", { class: "cfg-ctrl" }, [el("label", { class: "cfg-full" }, [el("span", { class: "muted", text: "Base URL" }), base])]),
      el("div", { class: "cfg-ctrl" }, [el("label", { class: "cfg-full" }, [el("span", { class: "muted", text: "模型" }), model])]),
      el("div", { class: "muted", style: "font-size:11.5px;margin-top:4px", text: "留空则自动降级为离线模板（确定性，无需联网）。环境变量 AXIOM_DEEPSEEK_API_KEY 可覆盖此处。" }),
    ]));

    // 操作
    const saveBtn = el("button", { class: "run", onclick: () => saveConfig() }, "保存配置");
    const resetBtn = el("button", { class: "ghost-btn", onclick: () => resetConfig() }, "恢复默认");
    panel.appendChild(el("div", { class: "cfg-actions" }, [saveBtn, resetBtn]));
  }

  async function testProvider(id) {
    const btn = $("#test-" + id), res = $("#testres-" + id);
    if (btn) { btn.disabled = true; btn.textContent = "测试中…"; }
    try {
      const r = await fetch(`${api}/api/config/test`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: id, ticker: "600519" }),
      });
      const d = await r.json();
      if (res) {
        if (d.status === "ok") {
          res.className = "cfg-test ok";
          res.textContent = `✓ ${d.latency_ms}ms · ${d.sample.name} ¥${fmt(d.sample.price)} · ${d.sample.source}`;
        } else {
          res.className = "cfg-test fail";
          res.textContent = "✗ " + (d.error || "失败");
        }
      }
    } catch (e) {
      if (res) { res.className = "cfg-test fail"; res.textContent = "请求失败：" + e.message; }
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "测试连接"; }
    }
  }

  async function saveConfig() {
    const cfg = cfgState.config;
    try {
      const r = await fetch(`${api}/api/config`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data_source: cfg.data_source, cache_ttl: cfg.cache_ttl, providers: cfg.providers, llm: cfg.llm }),
      });
      const d = await r.json();
      cfgState = { config: d.config, providers: d.providers, effective: d.data_source_effective };
      renderConfig();
      toast("配置已保存并生效");
    } catch (e) {
      toast("保存失败：" + e.message);
    }
  }

  async function resetConfig() {
    try {
      const r = await fetch(`${api}/api/config/reset`, { method: "POST" });
      const d = await r.json();
      cfgState = { config: d.config, providers: d.providers, effective: d.data_source_effective };
      renderConfig();
      toast("已恢复默认配置");
    } catch (e) {
      toast("重置失败：" + e.message);
    }
  }

  // ───────── 事件绑定 ─────────
  function bind() {
    $("#query").addEventListener("submit", e => { e.preventDefault(); runAnalysis($("#ticker").value); });
    $$(".chip[data-t]").forEach(c => c.addEventListener("click", () => { $("#ticker").value = c.dataset.t; runAnalysis(c.dataset.t); }));
    $("#btn-history").addEventListener("click", openHistory);
    $("#history-close").addEventListener("click", closeDrawers);
    $("#drawer-mask").addEventListener("click", closeDrawers);
    $("#btn-compare").addEventListener("click", () => ($("#compare-modal").hidden = false));
    $("#compare-close").addEventListener("click", closeDrawers);
    $("#cmp-run").addEventListener("click", runCompare);
    $("#btn-addwatch").addEventListener("click", addWatchCurrent);
    $("#ladder-refresh").addEventListener("click", () => { if (!$("#market").hidden) renderLadder(); });
    $("#sector-refresh").addEventListener("click", () => { if (!$("#sector").hidden) renderSectorRotation(); });
    $("#bt-run").addEventListener("click", () => { if (!$("#backtest").hidden) renderBacktest(); });
    $("#bt-ticker").addEventListener("keydown", e => { if (e.key === "Enter" && !$("#backtest").hidden) renderBacktest(); });
    refreshBadge();
    // 报告头也能点回概览
    renderPipeline();
  }

  document.addEventListener("DOMContentLoaded", () => { setupNav(); bind(); });
})();
