"""龙虎榜游资评分（融合自经验学习项目 aiagents-stock 的 longhubang_scoring 体系）。

对龙虎榜个股给出「游资参与度」综合评分（0~100），维度：

  - 资金含金量 capital_quality (0~30)：净买入额的分档
  - 净流入 net_inflow (0~25)：净买入方向强度
  - 抛压 sell_pressure (0~20)：低抛压得高分
  - 机构共振 institution (0~15)：机构专用 / 沪深股通席位
  - 顶级游资 bonus (0~10)：赵老哥 / 章盟主 / 方新侠等知名席位命中

设计原则（与 AxiomDesk 一致）：
  - 真实龙虎榜接口（东财 datacenter）为 best-effort：任意失败 → 确定性 demo 兜底，永不抛错；
  - 评分逻辑本身是完全确定、可测、可解释的，是「融合贯通」的核心价值点；
  - 该模块与 v3.1.0 的连板梯队天然互补：高位连板股正是最易上龙虎榜的短线定价区。
"""

from __future__ import annotations

import json
import threading
import time
from datetime import date
from typing import Any

from ..config_store import effective_data_source
from ..providers.base import ProviderError
from ..providers.http_base import http_get, to_float

# 顶级游资席位关键词（命中即加 bonus）
_FAMOUS_SEATS = [
    "赵老哥",
    "章盟主",
    "方新侠",
    "作手新一",
    "炒股养家",
    "孙哥",
    "小鳄鱼",
    "宁波桑田路",
    "著名刺客",
    "上塘路",
    "溧阳路",
    "欢乐海岸",
    "金田路",
    "宁波解放南",
]
_INSTITUTION_HINTS = ["机构专用", "机构席位", "沪股通", "深股通", "北上资金"]

_CACHE_TTL = 120.0
_cache: dict[str, Any] = {"ts": 0.0, "val": None}
_lock = threading.Lock()


def _today() -> str:
    return date.today().strftime("%Y%m%d")


def _score_capital_quality(net_buy_yi: float) -> float:
    a = abs(net_buy_yi)
    if a >= 2.0:
        return 30.0
    if a >= 1.0:
        return 24.0
    if a >= 0.5:
        return 18.0
    if a >= 0.2:
        return 12.0
    return 6.0


def _score_net_inflow(net_buy_yi: float) -> float:
    if net_buy_yi >= 1.0:
        return 25.0
    if net_buy_yi >= 0.5:
        return 18.0
    if net_buy_yi >= 0.2:
        return 12.0
    if net_buy_yi > 0:
        return 6.0
    return 0.0


def _score_sell_pressure(net_buy_yi: float) -> float:
    # 净买入为正 → 抛压低，得高分
    if net_buy_yi >= 0.5:
        return 20.0
    if net_buy_yi > 0:
        return 14.0
    if net_buy_yi >= -0.2:
        return 6.0
    return 0.0


def _score_institution(seats: list[str]) -> float:
    joined = " ".join(seats)
    if any(h in joined for h in ("机构专用", "机构席位")):
        return 15.0
    if "沪股通" in joined or "深股通" in joined or "北上资金" in joined:
        return 10.0
    return 0.0


def _score_bonus(seats: list[str]) -> float:
    joined = " ".join(seats)
    hits = sum(1 for name in _FAMOUS_SEATS if name in joined)
    if hits >= 2:
        return 10.0
    if hits == 1:
        return 6.0
    return 0.0


def score_row(row: dict[str, Any]) -> dict[str, Any]:
    """对单条龙虎榜记录评分，返回结构化评分。"""
    net_buy = float(row.get("net_buy_yi", 0.0) or 0.0)
    seats: list[str] = list(row.get("seats", []) or [])
    cq = _score_capital_quality(net_buy)
    ni = _score_net_inflow(net_buy)
    sp = _score_sell_pressure(net_buy)
    inst = _score_institution(seats)
    bonus = _score_bonus(seats)
    total = round(cq + ni + sp + inst + bonus, 1)
    if total >= 80:
        tier = "顶级游资抢筹"
    elif total >= 60:
        tier = "机构/游资共振"
    elif total >= 40:
        tier = "游资参与"
    else:
        tier = "一般"
    tags: list[str] = []
    joined = " ".join(seats)
    for name in _FAMOUS_SEATS:
        if name in joined:
            tags.append(name)
    if inst >= 15:
        tags.append("机构专用")
    elif inst >= 10:
        tags.append("沪深股通")
    return {
        "code": str(row.get("code", "")),
        "name": str(row.get("name", "")),
        "net_buy_yi": round(net_buy, 2),
        "seats": seats,
        "scores": {
            "capital_quality": cq,
            "net_inflow": ni,
            "sell_pressure": sp,
            "institution": inst,
            "bonus": bonus,
        },
        "total": total,
        "tier": tier,
        "tags": tags,
    }


def _demo_rows() -> list[dict]:
    """确定性演示龙虎榜（离线 / CI 可复现）。"""
    return [
        {"code": "002594", "name": "比亚迪", "net_buy_yi": 3.2, "seats": ["机构专用", "方新侠", "作手新一"]},
        {"code": "300750", "name": "宁德时代", "net_buy_yi": 2.4, "seats": ["沪股通", "赵老哥"]},
        {"code": "600519", "name": "贵州茅台", "net_buy_yi": -0.6, "seats": ["机构专用"]},
        {"code": "002230", "name": "科大讯飞", "net_buy_yi": 1.1, "seats": ["章盟主", "宁波桑田路", "上塘路"]},
        {"code": "601318", "name": "中国平安", "net_buy_yi": 0.4, "seats": ["机构专用", "深股通"]},
        {"code": "300059", "name": "东方财富", "net_buy_yi": 0.15, "seats": ["著名刺客"]},
    ]


def fetch_longhubang(date_s: str | None = None) -> list[dict]:
    """best-effort 抓取东财龙虎榜明细；失败返回空列表（交由 demo 兜底）。

    注：东财 datacenter 龙虎榜接口参数随版本变化，此处为尽力实现；
    真实部署若需 live 数据，按当前接口契约微调 reportName/filter 即可。
    """
    try:
        d = date_s or _today()
        url = (
            "https://datacenter-web.eastmoney.com/api/data/v1/get"
            f"?reportName=RPT_DAILYBILLBOARD_DETAILS&columns=ALL"
            f"&filter=(TRADE_DATE%3D%27{d}%27)&pageSize=30&sortColumns=NET_BUY"
            "&sortTypes=-1&source=WEB&client=WEB"
        )
        txt = http_get(url, timeout=8.0, proxy="", encoding="utf-8")
        obj = json.loads(txt)
        rows = (obj.get("result", {}) or {}).get("data", []) or []
        out: list[dict] = []
        for r in rows:
            seats = []
            for side in ("b1", "b2", "b3", "b4", "b5", "s1", "s2", "s3", "s4", "s5"):
                nm = r.get(side + "_name") or r.get(side)
                if nm:
                    seats.append(str(nm))
            nb = to_float(r.get("NET_BUY")) / 1e4  # 元 → 万
            out.append(
                {
                    "code": str(r.get("SECURITY_CODE", "") or r.get("CODE", "")),
                    "name": str(r.get("SECURITY_NAME_ABBR", "") or r.get("NAME", "")),
                    "net_buy_yi": round(nb / 1e4, 2) if nb else 0.0,
                    "seats": seats,
                }
            )
        return out
    except Exception:
        return []


def build_longhubang(date_s: str | None = None, top_n: int = 20) -> dict[str, Any]:
    """构建龙虎榜游资评分视图。live 优先，失败/为空 → 确定性 demo。"""
    now = time.time()
    with _lock:
        cached = _cache["val"] if (_cache["val"] is not None and (now - _cache["ts"]) < _CACHE_TTL) else None
    if cached is not None:
        return cached

    source = "live"
    rows = []
    try:
        if effective_data_source().lower() == "demo":
            raise ProviderError("demo 模式")
        rows = fetch_longhubang(date_s)
    except Exception:
        source = "demo"

    if not rows:
        source = "demo"
        rows = _demo_rows()

    scored = [score_row(r) for r in rows]
    scored.sort(key=lambda x: x["total"], reverse=True)
    out = {
        "source": source,
        "as_of": date_s or _today(),
        "count": len(scored),
        "rows": scored[:top_n],
    }
    with _lock:
        _cache["ts"] = time.time()
        _cache["val"] = out
    return out


def clear_cache() -> None:
    with _lock:
        _cache["ts"] = 0.0
        _cache["val"] = None
