# -*- coding: utf-8 -*-
"""估值模型 · 忠实移植自 UZI-Skill `scripts/lib/fin_models.py` (v3.9.4)。

三种机构级模型，全部纯 Python、可离线、可溯源：
  1. compute_dcf      — WACC(CAPM) + 两段 FCF + Gordon 终值 + 敏感性表
  2. build_comps      — 同业可比倍数、分位数、隐含价
  3. quick_lbo        — 入场 EV / 杠杆 / 退出 IRR / MOIC

所有函数接收一个 `features` dict（来自 data_provider），输出结构化 dict，
每个关键步骤都写入 `methodology_log`，便于前端引用“为什么是这个价”。
"""
from __future__ import annotations

import statistics
from typing import Any

# ── A 股默认假设 ──
DEFAULT_RF = 0.025            # 10Y 国债收益率
DEFAULT_ERP = 0.06           # A 股历史股权风险溢价
DEFAULT_BETA = 1.00
DEFAULT_TAX = 0.25
DEFAULT_TERMINAL_G = 0.025   # 长期名义 GDP
DEFAULT_STAGE1_YEARS = 5
DEFAULT_STAGE2_YEARS = 5
DEFAULT_STAGE1_GROWTH = 0.10
DEFAULT_STAGE2_GROWTH = 0.05


def _num(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ═══════════════════════════════════════════════════════════════
# 1. DCF
# ═══════════════════════════════════════════════════════════════

def compute_wacc(rf=DEFAULT_RF, erp=DEFAULT_ERP, beta=DEFAULT_BETA,
                 cost_of_debt_pretax=0.045, target_debt_ratio=0.30, tax=DEFAULT_TAX) -> dict:
    cost_of_equity = rf + beta * erp
    after_tax_kd = cost_of_debt_pretax * (1 - tax)
    equity_weight = 1 - target_debt_ratio
    wacc = equity_weight * cost_of_equity + target_debt_ratio * after_tax_kd
    return {
        "wacc": round(wacc, 4),
        "cost_of_equity": round(cost_of_equity, 4),
        "after_tax_kd": round(after_tax_kd, 4),
        "equity_weight": equity_weight,
        "debt_weight": target_debt_ratio,
    }


def compute_dcf(features: dict, assumptions: dict | None = None) -> dict:
    a = {
        "stage1_growth": DEFAULT_STAGE1_GROWTH,
        "stage2_growth": DEFAULT_STAGE2_GROWTH,
        "stage1_years": DEFAULT_STAGE1_YEARS,
        "stage2_years": DEFAULT_STAGE2_YEARS,
        "terminal_g": DEFAULT_TERMINAL_G,
        "beta": DEFAULT_BETA,
        "tax": DEFAULT_TAX,
        "target_debt_ratio": 0.30,
    }
    # 用个股 beta 覆盖
    if features.get("beta"):
        a["beta"] = _num(features["beta"])
    a.update(assumptions or {})

    wacc_info = compute_wacc(beta=a["beta"], tax=a["tax"], target_debt_ratio=a["target_debt_ratio"])
    wacc = wacc_info["wacc"]

    fcf0 = _num(features.get("fcf_latest_yi"))
    _fcf_proxy = False
    if fcf0 <= 0:
        rev = _num(features.get("revenue_latest_yi"))
        nm = _num(features.get("net_margin")) / 100
        fcf0 = rev * nm * 0.8
        _fcf_proxy = True
    if fcf0 <= 0:
        return {
            "method": "DCF (两段 + Gordon 终值)",
            "verdict": "⛔ 数据不足 · 无法 DCF",
            "intrinsic_per_share": None,
            "safety_margin_pct": None,
            "error": "FCF / 营收 / 净利率均缺失",
            "methodology_log": ["DCF 跳过 · FCF、营收、净利率均无数据"],
            "assumptions": a,
        }

    projected_fcf, year_labels, cur = [], [], fcf0
    for i in range(1, a["stage1_years"] + 1):
        cur *= (1 + a["stage1_growth"])
        projected_fcf.append(round(cur, 3)); year_labels.append(f"Y{i}")
    for i in range(1, a["stage2_years"] + 1):
        cur *= (1 + a["stage2_growth"])
        projected_fcf.append(round(cur, 3)); year_labels.append(f"Y{a['stage1_years'] + i}")

    pv_fcf = []
    for idx, fcf in enumerate(projected_fcf, start=1):
        df = 1 / (1 + wacc) ** idx
        pv_fcf.append(round(fcf * df, 3))
    pv_explicit = round(sum(pv_fcf), 3)

    terminal_fcf = projected_fcf[-1] * (1 + a["terminal_g"])
    tv_at_end = terminal_fcf / (wacc - a["terminal_g"]) if (wacc - a["terminal_g"]) > 0 else 0
    n_years = len(projected_fcf)
    tv_pv = round(tv_at_end / (1 + wacc) ** n_years, 3)

    enterprise_value = round(pv_explicit + tv_pv, 3)
    _td, _cash = _num(features.get("total_debt_yi")), _num(features.get("cash_yi"))
    _has_debt = (features.get("total_debt_yi") not in (None, 0)) or (features.get("cash_yi") not in (None, 0))
    net_debt = _td - _cash
    equity_value = round(enterprise_value - net_debt, 3)
    _net_debt_note = "" if _has_debt else "（净债桥缺失 · EV≈股权价值 · 高杠杆公司会高估）"

    shares_yi = _num(features.get("shares_outstanding_yi"))
    if shares_yi <= 0:
        mc = _num(features.get("market_cap_yi")); px = _num(features.get("price"))
        shares_yi = mc / px if px > 0 else 1.0
    per_share = round(equity_value / shares_yi, 2) if shares_yi > 0 else 0

    cur_price = _num(features.get("price"))
    safety_margin = round((per_share - cur_price) / cur_price * 100, 1) if (cur_price > 0 and per_share > 0) else 0

    sensitivity = _sensitivity_table(fcf0, a, net_debt, shares_yi, wacc, a["terminal_g"])

    return {
        "method": "DCF (两段 + Gordon 终值)",
        "wacc": wacc,
        "wacc_breakdown": wacc_info,
        "base_fcf_yi": round(fcf0, 3),
        "fcf_proxy": _fcf_proxy,
        "projected_fcf_yi": projected_fcf,
        "year_labels": year_labels,
        "pv_explicit_yi": pv_explicit,
        "terminal_value_yi": round(tv_at_end, 3),
        "tv_pv_yi": tv_pv,
        "tv_pct_of_ev": round(tv_pv / enterprise_value * 100, 1) if enterprise_value > 0 else 0,
        "enterprise_value_yi": enterprise_value,
        "net_debt_yi": round(net_debt, 3),
        "equity_value_yi": equity_value,
        "net_debt_bridge_note": _net_debt_note,
        "shares_yi": round(shares_yi, 3),
        "intrinsic_per_share": per_share,
        "current_price": cur_price,
        "safety_margin_pct": safety_margin,
        "verdict": _dcf_verdict(safety_margin),
        "sensitivity_table": sensitivity,
        "assumptions": a,
        "methodology_log": [
            f"WACC = CAPM: k_e={(wacc_info['cost_of_equity']*100):.2f}%, 税后 k_d={(wacc_info['after_tax_kd']*100):.2f}%, 加权 WACC={(wacc*100):.2f}%",
            f"基期 FCF = {fcf0:.2f} 亿{'(营收×净利率×0.8 代理)' if _fcf_proxy else ''}",
            f"两段增长 {(a['stage1_growth']*100):.0f}%({a['stage1_years']}年) → {(a['stage2_growth']*100):.0f}%({a['stage2_years']}年)",
            f"显式期 PV = {pv_explicit:.1f} 亿; 终值 PV = {tv_pv:.1f} 亿 (占 EV {round(tv_pv/enterprise_value*100,0) if enterprise_value>0 else 0:.0f}%)",
            f"EV {enterprise_value:.1f} − 净债 {net_debt:.1f} = 股权价值 {equity_value:.1f} 亿{_net_debt_note}",
            f"每股内在价值 ¥{per_share:.2f} (现价 ¥{cur_price:.2f}, 安全边际 {safety_margin:+.1f}%)",
        ],
    }


def _sensitivity_table(fcf0, a, net_debt, shares_yi, wacc_center, g_center) -> dict:
    wacc_row = [wacc_center - 0.02, wacc_center - 0.01, wacc_center, wacc_center + 0.01, wacc_center + 0.02]
    g_col = [g_center - 0.01, g_center - 0.005, g_center, g_center + 0.005, g_center + 0.01]
    rows = []
    for w in wacc_row:
        row = []
        for g in g_col:
            cur = fcf0
            proj = []
            for _ in range(a["stage1_years"]):
                cur *= (1 + a["stage1_growth"]); proj.append(cur)
            for _ in range(a["stage2_years"]):
                cur *= (1 + a["stage2_growth"]); proj.append(cur)
            pv_exp = sum(f / (1 + w) ** (i + 1) for i, f in enumerate(proj))
            tv = proj[-1] * (1 + g) / (w - g) if (w - g) > 0 else 0
            tv_pv = tv / (1 + w) ** len(proj)
            eq = pv_exp + tv_pv - net_debt
            ps = eq / shares_yi if shares_yi > 0 else 0
            row.append(round(ps, 2))
        rows.append(row)
    return {"wacc_axis": [f"{round(w*100,1)}%" for w in wacc_row],
            "g_axis": [f"{round(g*100,1)}%" for g in g_col],
            "values_per_share": rows, "center_cell": rows[2][2]}


def _dcf_verdict(safety_margin: float) -> str:
    if safety_margin >= 30: return "🟢 深度低估 — 安全边际充足"
    if safety_margin >= 15: return "🟡 略微低估 — 可关注"
    if safety_margin >= -15: return "⚪ 基本合理"
    if safety_margin >= -30: return "🟠 略微高估"
    return "🔴 明显高估"


# ═══════════════════════════════════════════════════════════════
# 2. COMPS
# ═══════════════════════════════════════════════════════════════

def build_comps(target: dict, peers: list[dict]) -> dict:
    def _same(p):
        tt = str(target.get("ticker") or target.get("code") or "").strip()
        pt = str(p.get("ticker") or p.get("code") or "").strip()
        if tt and pt and tt == pt: return True
        tn = str(target.get("name") or "").strip(); pn = str(p.get("name") or "").strip()
        return bool(tn and pn and tn == pn)

    valid = [p for p in peers if isinstance(p, dict) and not _same(p)]
    if len(valid) < 2:
        return {"method": "同业可比 (Comps)", "peer_count": len(valid), "peer_stats": {},
                "target_percentile": {}, "implied_price": {}, "valuation_verdict": "⚪ 同行样本不足 · 无法对标",
                "methodology_log": [f"有效同行 n={len(valid)}，跳过分位数与估值结论"]}

    metrics = ["pe", "pb", "ps", "ev_ebitda", "ev_sales", "roe", "net_margin", "revenue_growth"]
    stats: dict[str, dict] = {}
    for m in metrics:
        vals = [_num(p.get(m)) for p in valid if _num(p.get(m)) > 0]
        if not vals: continue
        q = statistics.quantiles(vals, n=4) if len(vals) > 1 else [vals[0], vals[0], vals[0]]
        stats[m] = {"min": round(min(vals), 2), "p25": round(q[0], 2), "median": round(statistics.median(vals), 2),
                    "p75": round(q[2], 2), "max": round(max(vals), 2), "mean": round(sum(vals)/len(vals), 2), "n": len(vals)}

    tgt_pct: dict[str, float] = {}
    for m, s in stats.items():
        tv = _num(target.get(m))
        if tv <= 0: continue
        vals = sorted(_num(p.get(m)) for p in valid if _num(p.get(m)) > 0)
        rank = sum(1 for v in vals if v < tv)
        tgt_pct[m] = round(rank / len(vals) * 100, 0) if vals else 50

    cur_px = _num(target.get("price"))
    implied = {}
    if stats.get("pe") and target.get("eps"):
        implied["via_median_pe"] = round(stats["pe"]["median"] * _num(target.get("eps")), 2)
    if stats.get("pb") and target.get("bvps"):
        implied["via_median_pb"] = round(stats["pb"]["median"] * _num(target.get("bvps")), 2)

    pe_pct = tgt_pct.get("pe", 50)
    if pe_pct <= 25: val = "🟢 便宜（PE 低于 75% 同行）"
    elif pe_pct <= 50: val = "🟡 合理偏低"
    elif pe_pct <= 75: val = "⚪ 合理偏高"
    else: val = "🔴 昂贵（PE 高于 75% 同行）"

    return {"method": "同业可比 (Comps)", "peer_count": len(valid), "peer_stats": stats,
            "target_percentile": tgt_pct, "implied_price": implied, "current_price": cur_px,
            "valuation_verdict": val,
            "methodology_log": [f"有效同行池 n={len(valid)}",
                                f"PE 中位数 {stats.get('pe',{}).get('median','-')} · 目标 PE {target.get('pe','-')}",
                                f"目标 PE 分位 {pe_pct}%",
                                f"隐含价(中位PE×EPS)=¥{implied.get('via_median_pe','-')}",
                                f"结论: {val}"]}


# ═══════════════════════════════════════════════════════════════
# 3. LBO
# ═══════════════════════════════════════════════════════════════

def quick_lbo(features: dict, entry_multiple=8.0, debt_multiple=5.0, exit_multiple=8.0,
              hold_years=5, ebitda_growth=0.08, interest_rate=0.06) -> dict:
    ebitda = _num(features.get("ebitda_yi"))
    if ebitda <= 0:
        rev = _num(features.get("revenue_latest_yi")); nm = _num(features.get("net_margin")) / 100
        ni = rev * nm; ebitda = ni / 0.6 if ni > 0 else rev * 0.15

    entry_ev = entry_multiple * ebitda
    entry_debt = debt_multiple * ebitda
    entry_equity = entry_ev - entry_debt

    path, cur = [], ebitda
    for _ in range(1, hold_years + 1):
        cur *= (1 + ebitda_growth); path.append(round(cur, 2))

    debt = entry_debt
    debt_schedule = [round(debt, 2)]
    for y_eb in path:
        interest = debt * interest_rate
        fcf = y_eb * 0.5 - interest
        paydown = max(0, fcf * 0.7)
        debt = max(0, debt - paydown)
        debt_schedule.append(round(debt, 2))

    exit_ebitda = path[-1]
    exit_ev = exit_multiple * exit_ebitda
    exit_debt = debt_schedule[-1]
    exit_equity = exit_ev - exit_debt

    if entry_equity > 0 and exit_equity > 0:
        moic = exit_equity / entry_equity
        irr = (moic ** (1 / hold_years) - 1)
    else:
        moic, irr = 0, 0

    return {"method": "杠杆收购测试 (LBO)", "entry_ebitda_yi": round(ebitda, 2),
            "entry_multiple": entry_multiple, "entry_ev_yi": round(entry_ev, 2),
            "entry_debt_yi": round(entry_debt, 2), "entry_equity_yi": round(entry_equity, 2),
            "leverage_turns": debt_multiple, "ebitda_path": path, "debt_schedule": debt_schedule,
            "exit_ebitda_yi": round(exit_ebitda, 2), "exit_multiple": exit_multiple,
            "exit_ev_yi": round(exit_ev, 2), "exit_equity_yi": round(exit_equity, 2),
            "moic": round(moic, 2), "irr_pct": round(irr * 100, 1),
            "pass_pe_test": irr >= 0.20,
            "verdict": "🟢 PE 买方可赚 20%+ IRR" if irr >= 0.20 else ("🟡 PE 买方 15-20% IRR" if irr >= 0.15 else "🔴 低于 PE 收益门槛"),
            "methodology_log": [
                f"入场 EBITDA {ebitda:.1f}亿 × {entry_multiple}x = EV {entry_ev:.1f}亿",
                f"{debt_multiple}x 杠杆 → 债 {entry_debt:.1f}亿 + 股本 {entry_equity:.1f}亿",
                f"{hold_years}年 {(ebitda_growth*100):.0f}% 成长 → Y{hold_years} EBITDA {exit_ebitda:.1f}亿",
                f"退出 {exit_multiple}x × {exit_ebitda:.1f} = {exit_ev:.1f}亿 EV",
                f"退出股权 {exit_equity:.1f} / 入场股权 {entry_equity:.1f} = {moic:.2f}x MOIC ({(irr*100):.1f}% IRR)"]}


# ═══════════════════════════════════════════════════════════════
# 汇总
# ═══════════════════════════════════════════════════════════════

def valuation(features: dict, peers: list[dict] | None = None) -> dict:
    """返回 dcf / comps / lbo / fair_price。

    - DCF：两段 + Gordon 终值（与 fin_models 一致）。增速与公司自身营收增速绑定，
      避免成熟白马被永远 10% 增长高估：stage1=clamp(rg*0.5,2%,9%)；stage2=clamp(rg*0.25,1.5%,4.5%)。
      DCF 对 WACC 与永续增速极敏感，作为「乐观情景」交叉验证。
    - Comps：同业可比倍数，作为公允价主导锚（稳定、贴近市场）。
    - LBO：PE 买方 IRR 交叉验证。
    综合公允价 = Comps 隐含价（样本充足时）优先，否则用 DCF。
    """
    rg = _num(features.get("revenue_growth"))
    a = {
        "stage1_growth": min(0.09, max(0.02, rg * 0.5 / 100)),
        "stage2_growth": min(0.045, max(0.015, rg * 0.25 / 100)),
    }
    dcf = compute_dcf(features, a)
    comps = build_comps(features, peers or [])
    lbo = quick_lbo(features)

    dcf_px = dcf.get("intrinsic_per_share") or 0
    comps_px = comps.get("implied_price", {}).get("via_median_pe") or 0
    has_dcf = dcf_px > 0 and dcf.get("verdict", "").startswith("🟢") or dcf_px > 0
    has_comps = comps_px > 0

    # 公允价主导锚：Comps 优先（样本充足），否则 DCF
    if has_comps:
        fair = round(comps_px, 2)
        fair_method = "comps"
    elif has_dcf:
        fair = round(dcf_px, 2)
        fair_method = "dcf"
    else:
        fair = round(_num(features.get("price")), 2)
        fair_method = "price"

    return {"dcf": dcf, "comps": comps, "lbo": lbo, "fair_price": fair,
            "fair_method": fair_method, "has_dcf": bool(dcf_px > 0), "has_comps": bool(has_comps)}
