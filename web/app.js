/* UZI 投研终端 · 前端逻辑（无依赖原生 JS）
 * 红=涨、绿=跌（中国习惯）。渲染 9 大板块 + 历史抽屉 + 对比弹窗。
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
  function setupNav() {
    $$("#nav .nav-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        $$("#nav .nav-btn").forEach(b => b.classList.remove("active"));
        $$(".tab-panel").forEach(p => (p.hidden = true));
        btn.classList.add("active");
        $("#tab-" + btn.dataset.tab).hidden = false;
        if (btn.dataset.tab === "jury") renderJury();
        if (btn.dataset.tab === "valuation") renderValuation();
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
        toast("轮询失败：" + e.message); finishLoading(); return;
      }
    }
    toast("分析超时，请重试"); finishLoading();
  }

  // 同步兜底（保留）：GET /api/analyze
  async function runSync(ticker) {
    const depth = $("#depth").value, boost = +$("#boost").value || 0, useAi = $("#useai").checked;
    showLoading();
    try {
      const u = `${api}/api/analyze?ticker=${encodeURIComponent(ticker)}&depth=${depth}&boost=${boost}&use_ai=${useAi}`;
      const r = await fetch(u);
      const data = await r.json();
      if (data.error) throw new Error(data.error);
      current = data; finishLoading(); renderAll(current, data.llm_source);
    } catch (e) { toast("分析失败：" + e.message); finishLoading(); }
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
    const cc = (ai.core_conclusion || "").replace(/但是/g, '<span class="but">但是</span>');
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

  // ───────── 流水线 ─────────
  function renderPipeline() {
    const panel = $("#tab-pipeline"); panel.innerHTML = "";
    panel.appendChild(el("div", { class: "section-title", text: "分析流水线（UZI-Skill 6 段式）" }));
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
      el("div", { class: "muted", style: "font-size:11.5px;margin-top:4px", text: "留空则自动降级为离线模板（确定性，无需联网）。环境变量 UZI_DEEPSEEK_API_KEY 可覆盖此处。" }),
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
    // 报告头也能点回概览
    renderPipeline();
  }

  document.addEventListener("DOMContentLoaded", () => { setupNav(); bind(); });
})();
