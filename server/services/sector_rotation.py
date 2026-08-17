"""板块轮动矩阵（融合自经验学习项目 tickflow-stock-panel 轮动矩阵 + a-stock-data 板块资金流）。

从东财 push2 ``clist`` 直连抓取行业 / 概念板块的：

  - 今日涨跌幅 (f3)
  - 5 日涨跌幅 (f104)
  - 10 日涨跌幅 (f105)
  - 主力净流入 (f62，单位元 → 亿)
  - 主力净占比 (f184，%)

用于识别「板块轮动主线」：哪些板块在 5/10 日维度持续走强、资金在往哪条线聚集。
A 股是强板块轮动市场，这是择时与选主线的最高频需求。

设计原则（与 AxiomDesk / limit_ladder 一致）：
  - 零依赖、零鉴权、直连东财；
  - ``AXIOM_DATA_SOURCE=demo`` 或任意网络失败 → 确定性 demo 兜底，永不抛错给前端；
  - 自带短 TTL 缓存，避免每个请求都打东财。
"""

from __future__ import annotations

import threading
import time
from typing import Any

from ..config_store import effective_data_source
from ..providers.base import ProviderError
from ..providers.http_base import http_get, to_float
from ..providers.market import _EM_HEADERS

# 板块维度：行业 (m:90+t:2) / 概念 (m:90+t:3)
_FS = {"industry": "m:90+t:2", "concept": "m:90+t:3"}
_FIELDS = "f12,f14,f3,f104,f105,f62,f184"

_CACHE_TTL = 90.0
_cache: dict[str, Any] = {"ts": 0.0, "val": None}
_lock = threading.Lock()


def _params_from_config() -> tuple[float, str]:
    try:
        from ..config_store import get_config

        cfg = get_config()
        t = cfg.get("providers", {}).get("tencent", {})
        return float(t.get("timeout", 8.0)), str(t.get("proxy", ""))
    except Exception:
        return 8.0, ""


def fetch_sector_board(dimension: str, top_n: int, timeout: float, proxy: str) -> list[dict]:
    """抓取单个维度的板块轮动列表。失败抛 ProviderError。"""
    fs = _FS.get(dimension)
    if fs is None:
        raise ProviderError(f"未知板块维度：{dimension}")
    url = (
        "https://push2.eastmoney.com/api/qt/clist/get?pn=1"
        f"&pz={top_n}&po=1&np=1&fltt=2&invt=2&fid=f3&fs={fs}"
        f"&fields={_FIELDS}"
    )
    txt = http_get(url, timeout=timeout, proxy=proxy, headers=_EM_HEADERS, encoding="utf-8")
    d = __import__("json").loads(txt)
    diff = (d.get("data") or {}).get("diff") or []
    out: list[dict] = []
    for it in diff:
        out.append(
            {
                "code": str(it.get("f12", "")),
                "name": str(it.get("f14", "")),
                "change_pct": to_float(it.get("f3")) / 100.0,
                "chg_5d": to_float(it.get("f104")) / 100.0,
                "chg_10d": to_float(it.get("f105")) / 100.0,
                "net_inflow_yi": to_float(it.get("f62")) / 1e8,
                "net_ratio": to_float(it.get("f184")) / 100.0,
            }
        )
    return out


def _demo_board(dimension: str) -> list[dict]:
    """确定性演示板块（离线 / CI 可复现）。"""
    if dimension == "industry":
        base = [
            ("半导体", 0.031, 0.082, 0.141, 18.6, 0.061),
            ("汽车零部件", 0.018, 0.041, 0.073, 9.2, 0.034),
            ("消费电子", 0.012, 0.029, 0.052, 6.4, 0.028),
            ("化学制药", -0.006, 0.015, 0.022, 3.1, 0.011),
            ("证券", 0.004, -0.012, -0.021, -2.4, -0.009),
            ("房地产开发", -0.014, -0.031, -0.048, -7.8, -0.026),
            ("白酒", -0.009, -0.018, -0.027, -4.2, -0.015),
            ("银行", 0.002, 0.006, 0.011, 1.8, 0.006),
        ]
    else:
        base = [
            ("华为鸿蒙", 0.045, 0.092, 0.161, 12.3, 0.072),
            ("机器人概念", 0.028, 0.061, 0.118, 10.5, 0.058),
            ("AI 算力", 0.021, 0.047, 0.089, 8.1, 0.043),
            ("低空经济", 0.016, 0.033, 0.061, 5.2, 0.029),
            ("可控核聚变", -0.022, 0.009, 0.018, 1.1, 0.008),
            ("短剧游戏", -0.018, -0.041, -0.063, -3.6, -0.021),
            ("元宇宙", -0.011, -0.024, -0.039, -2.8, -0.017),
            ("纾困概念", -0.007, -0.013, -0.019, -1.2, -0.006),
        ]
    return [
        {
            "code": f"DEMO{i:02d}",
            "name": name,
            "change_pct": c,
            "chg_5d": c5,
            "chg_10d": c10,
            "net_inflow_yi": net,
            "net_ratio": nr,
        }
        for i, (name, c, c5, c10, net, nr) in enumerate(base)
    ]


def build_sector_rotation(top_n: int = 30, force_refresh: bool = False) -> dict:
    """构建板块轮动矩阵视图。

    返回 {source, as_of, industry:[...], concept:[...], leaders, laggards}。
    demo 态或网络失败 → 确定性演示数据，前端据此标注「离线演示」。
    """
    now = time.time()
    with _lock:
        cached = (
            _cache["val"]
            if (not force_refresh and _cache["val"] is not None and (now - _cache["ts"]) < _CACHE_TTL)
            else None
        )
    if cached is not None:
        return cached

    source = "live"
    as_of = time.strftime("%Y-%m-%d %H:%M")
    try:
        if effective_data_source().lower() == "demo":
            raise ProviderError("demo 模式")
        timeout, proxy = _params_from_config()
        industry = fetch_sector_board("industry", top_n, timeout, proxy)
        concept = fetch_sector_board("concept", top_n, timeout, proxy)
        if not industry and not concept:
            raise ProviderError("板块数据为空")
    except Exception:
        source = "demo"
        as_of = __import__("datetime").date.today().isoformat()
        industry = _demo_board("industry")
        concept = _demo_board("concept")

    def _rank(board: list[dict]) -> dict:
        strong = sorted(board, key=lambda x: x.get("chg_10d", 0.0), reverse=True)
        return {"strong": strong[:5], "weak": strong[-5:][::-1]}

    out = {
        "source": source,
        "as_of": as_of,
        "industry": industry,
        "concept": concept,
        "leaders": _rank(industry)["strong"] + _rank(concept)["strong"],
        "laggards": _rank(industry)["weak"] + _rank(concept)["weak"],
    }
    with _lock:
        _cache["ts"] = time.time()
        _cache["val"] = out
    return out


def clear_cache() -> None:
    with _lock:
        _cache["ts"] = 0.0
        _cache["val"] = None
