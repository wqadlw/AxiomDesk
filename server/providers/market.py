"""市场级数据（涨停池 / 炸板池 / 板块资金流 / 指数行情）· 零依赖直连。

数据维度设计融合自经验学习项目：
  - a-stock-data：东财 push2ex 涨停/炸板池、push2 clist 板块资金流（requests 直连、零鉴权）
  - adata / easyquotation：指数行情（腾讯 qt.gtimg.cn 批量快照）

与个股 Provider 不同，本模块提供的是「全市场情绪快照」，不参与个股 failover 链，
而是由 engine 通过 `get_market_context()` 拉取一次、TTL 缓存，供：
  - 情绪周期信号（涨停家数 / 连板高度 / 炸板率 → 冰点~亢奋）
  - 龙头战法信号（市场活跃度加权）
  - d2 技术维度 / 叙述层（大盘环境、行业资金主线）

所有网络失败抛 ProviderError，engine 侧容错降级为确定性 demo 快照，永不中断分析。
"""

from __future__ import annotations

import json
import threading
import time
from datetime import date
from typing import Any

from .base import ProviderError
from .http_base import http_get, to_float

# ───────────────────────── 常量 ─────────────────────────
_EM_UT = "7eea3edcaed734bea9cbfc24409ed989"
_EM_HEADERS = {
    "Referer": "https://quote.eastmoney.com/",
    "Origin": "https://quote.eastmoney.com",
}

# 情绪周期阈值（参考 daily_stock_analysis 情绪周期方法论）
EMOTION_BANDS: list[tuple[float, str]] = [
    (0.80, "亢奋(风险积聚)"),
    (0.62, "活跃"),
    (0.45, "回暖"),
    (0.30, "低迷"),
    (0.00, "冰点"),
]

# TTL 缓存（市场快照变化快，设 60s，避免每个分析请求都打东财）
_CACHE_TTL = 60.0
_cache: dict[str, Any] = {"ts": 0.0, "val": None}
_lock = threading.Lock()


# ───────────────────────── 抓取函数 ─────────────────────────
def _today() -> str:
    return date.today().strftime("%Y%m%d")


def fetch_limit_pool(timeout: float = 8.0, proxy: str = "", date_s: str | None = None) -> dict:
    """东财涨停池：返回 {count, max_boards, board_dist:{1:n,...}, pool:[{code,name,boards,industry}]}。"""
    url = (
        f"https://push2ex.eastmoney.com/getTopicZTPool?ut={_EM_UT}&dpt=wz.ztzt"
        f"&Pageindex=0&pagesize=300&sort=fbt%3Aasc&date={date_s or _today()}"
    )
    txt = http_get(url, timeout=timeout, proxy=proxy, headers=_EM_HEADERS, encoding="utf-8")
    d = json.loads(txt)
    pool = (d.get("data") or {}).get("pool") or []
    dist: dict[str, int] = {}
    max_boards = 0
    rows: list[dict] = []
    for p in pool:
        boards = int(to_float(p.get("lbc")) or 0)
        max_boards = max(max_boards, boards)
        dist[str(boards)] = dist.get(str(boards), 0) + 1
        rows.append(
            {
                "code": str(p.get("c", "")),
                "name": str(p.get("n", "")),
                "boards": boards,
                "industry": str(p.get("hybk", "")),
            }
        )
    return {"count": len(pool), "max_boards": max_boards, "board_dist": dist, "pool": rows}


def fetch_break_pool(timeout: float = 8.0, proxy: str = "", date_s: str | None = None) -> dict:
    """东财炸板池：返回 {count, pool:[{code,name,boards,industry}]}。"""
    url = (
        f"https://push2ex.eastmoney.com/getTopicZBPool?ut={_EM_UT}&dpt=wz.ztzt"
        f"&Pageindex=0&pagesize=300&sort=fund%3Aasc&date={date_s or _today()}"
    )
    txt = http_get(url, timeout=timeout, proxy=proxy, headers=_EM_HEADERS, encoding="utf-8")
    d = json.loads(txt)
    pool = (d.get("data") or {}).get("pool") or []
    rows = [
        {
            "code": str(p.get("c", "")),
            "name": str(p.get("n", "")),
            "boards": int(to_float(p.get("lbc")) or 0),
            "industry": str(p.get("hybk", "")),
        }
        for p in pool
    ]
    return {"count": len(pool), "pool": rows}


def fetch_sector_flow(timeout: float = 8.0, proxy: str = "", top_n: int = 8) -> list[dict]:
    """东财行业板块资金流（主力净流入排行）：返回 [{name, change_pct, net_inflow_yi, net_ratio}]。"""
    url = (
        "https://push2.eastmoney.com/api/qt/clist/get?pn=1"
        f"&pz={top_n}&po=1&np=1&fltt=2&invt=2&fid=f62&fs=m:90+t:2"
        "&fields=f12,f14,f2,f3,f62,f184"
    )
    txt = http_get(url, timeout=timeout, proxy=proxy, headers=_EM_HEADERS, encoding="utf-8")
    d = json.loads(txt)
    diff = (d.get("data") or {}).get("diff") or []
    out: list[dict] = []
    for it in diff:
        out.append(
            {
                "name": str(it.get("f14", "")),
                "change_pct": to_float(it.get("f3")) / 100.0,
                "net_inflow_yi": to_float(it.get("f62")) / 1e8,
                "net_ratio": to_float(it.get("f184")) / 100.0,
            }
        )
    return out


def fetch_index_quote(timeout: float = 8.0, proxy: str = "") -> dict:
    """腾讯批量指数快照：返回 {code: {name, price, change_pct}}（上证/深成/创业板）。"""
    codes = "sh000001,sz399001,sz399006"
    txt = http_get(f"https://qt.gtimg.cn/q={codes}", timeout=timeout, proxy=proxy, encoding="gbk")
    out: dict[str, dict] = {}
    for line in txt.split(";"):
        line = line.strip()
        if "=" not in line:
            continue
        key = line.split("=", 1)[0].replace("v_", "")
        body = line.split("=", 1)[1].strip().strip('"').rstrip(";").strip('"')
        f = body.split("~")
        if len(f) < 33 or not f[3]:
            continue
        out[key] = {
            "name": f[1],
            "price": to_float(f[3]),
            "change_pct": to_float(f[32]) / 100.0,
        }
    if not out:
        raise ProviderError("腾讯指数行情返回为空")
    return out


def fetch_index_kline(timeout: float = 8.0, proxy: str = "", days: int = 130) -> list[dict]:
    """腾讯上证指数日 K（供 RPS 相对强度计算），返回由近到远 OHLCV。失败返回空列表。"""
    try:
        txt = http_get(
            f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000001,day,,,{days},qfq",
            timeout=timeout,
            proxy=proxy,
            encoding="utf-8",
        )
        d = json.loads(txt)
        node = d.get("data", {}).get("sh000001", {})
        arr = node.get("day") or node.get("qfqday") or []
        rows: list[dict] = []
        for r in arr:
            if len(r) < 6:
                continue
            rows.append(
                {
                    "date": str(r[0]),
                    "open": to_float(r[1]),
                    "close": to_float(r[2]),
                    "high": to_float(r[3]),
                    "low": to_float(r[4]),
                    "volume": to_float(r[5]),
                }
            )
        rows.reverse()
        return rows
    except Exception:
        return []


# ───────────────────────── 情绪周期映射 ─────────────────────────
def market_emotion(limit_count: int, max_boards: int, break_rate: float) -> dict:
    """由涨停家数 / 连板高度 / 炸板率推导市场情绪阶段与得分（0~1）。

    打分思路（参考 daily_stock_analysis 情绪周期方法论）：
      - 涨停家数 40~80 为活跃区间，过多（>110）反而不健康
      - 连板高度 >=5 视为强赚钱效应，>=7 进入亢奋
      - 炸板率 <0.15 强势，>0.35 转弱
    """
    lc = max(0, int(limit_count))
    mb = max(0, int(max_boards))
    br = max(0.0, min(1.0, float(break_rate)))
    s_lc = min(lc / 80.0, 1.0) - max(0.0, (lc - 110) / 200.0)
    s_mb = min(mb / 7.0, 1.0)
    s_br = 1.0 - min(br / 0.5, 1.0)
    score = round(max(0.0, min(1.0, 0.5 * s_lc + 0.3 * s_mb + 0.2 * s_br)), 3)
    stage = "平稳"
    for thr, label in EMOTION_BANDS:
        if score >= thr:
            stage = label
            break
    side = "bullish" if score >= 0.62 else ("bearish" if score < 0.30 else "neutral")
    return {"score": score, "stage": stage, "side": side}


# ───────────────────────── demo 确定性快照 ─────────────────────────
def synthesize_market_context() -> dict:
    """离线确定性市场快照（永不联网）。数值固定，保证测试与 CI 可复现。"""
    limit: dict[str, Any] = {"count": 46, "max_boards": 3, "board_dist": {"1": 28, "2": 12, "3": 4, "4": 2}, "pool": []}
    break_: dict[str, Any] = {"count": 11, "pool": []}
    br = break_["count"] / max(1, limit["count"] + break_["count"])
    emo = market_emotion(limit["count"], limit["max_boards"], br)
    return {
        "source": "demo",
        "as_of": date.today().isoformat(),
        "index": {
            "sh000001": {"name": "上证指数", "price": 3205.6, "change_pct": 0.003},
            "sz399001": {"name": "深证成指", "price": 10420.3, "change_pct": 0.005},
            "sz399006": {"name": "创业板指", "price": 2105.2, "change_pct": 0.008},
        },
        "limit_pool": limit,
        "break_pool": break_,
        "break_rate": round(br, 3),
        "emotion": emo,
        "sector_flow": [
            {"name": "半导体", "change_pct": 0.023, "net_inflow_yi": 12.4, "net_ratio": 0.05},
            {"name": "软件开发", "change_pct": 0.018, "net_inflow_yi": 8.7, "net_ratio": 0.04},
            {"name": "证券", "change_pct": 0.011, "net_inflow_yi": 6.2, "net_ratio": 0.03},
        ],
        "index_kline": _demo_index_kline(),
        "note": "离线演示市场快照，不代表真实行情。",
    }


def _demo_index_kline(days: int = 130) -> list[dict]:
    """确定性上证指数合成日 K（温和上行 + 小幅波动，供 RPS 离线计算）。"""
    from datetime import date, timedelta

    n = max(30, days)
    closes: list[float] = []
    v = 3100.0
    for _ in range(n):
        v += 0.8
        v *= 1.0004
        closes.append(round(v, 2))
    rows: list[dict] = []
    anchor = date(2024, 6, 1)
    for i in range(n):
        o = closes[i - 1] if i > 0 else closes[i] * 0.995
        c = closes[i]
        rows.append(
            {
                "date": (anchor + timedelta(days=(n - 1 - i))).isoformat(),
                "open": round(o, 2),
                "high": round(max(o, c) * 1.004, 2),
                "low": round(min(o, c) * 0.996, 2),
                "close": c,
                "volume": 3.5e7,
            }
        )
    rows.reverse()
    return rows


# ───────────────────────── 统一入口（TTL 缓存） ─────────────────────────
def _params_from_config() -> tuple[float, str]:
    """从配置取网络参数（跟随 tencent 的 timeout/proxy 设置）。"""
    try:
        from ..config_store import get_config

        cfg = get_config()
        t = cfg.get("providers", {}).get("tencent", {})
        return float(t.get("timeout", 8.0)), str(t.get("proxy", ""))
    except Exception:
        return 8.0, ""


def get_market_context(force_refresh: bool = False) -> dict:
    """拉取一次市场快照（TTL 缓存 60s）。失败返回确定性 demo 快照。

    尊重 ``AXIOM_DATA_SOURCE`` / 配置：data_source 为 demo 时直接返回合成快照
    （离线 / CI 确定性，不联网）。
    """
    try:
        from ..config_store import effective_data_source

        if effective_data_source().lower() == "demo":
            return synthesize_market_context()
    except Exception:
        pass

    now = time.time()
    with _lock:
        if not force_refresh and _cache["val"] is not None and (now - _cache["ts"]) < _CACHE_TTL:
            return _cache["val"]

    timeout, proxy = _params_from_config()
    try:
        limit = fetch_limit_pool(timeout, proxy)
        break_ = fetch_break_pool(timeout, proxy)
        br = break_["count"] / max(1, limit["count"] + break_["count"])
        emo = market_emotion(limit["count"], limit["max_boards"], br)
        mkt: dict[str, Any] = {
            "source": "live",
            "as_of": time.strftime("%Y-%m-%d %H:%M"),
            "limit_pool": limit,
            "break_pool": break_,
            "break_rate": round(br, 3),
            "emotion": emo,
        }
        try:
            mkt["index"] = fetch_index_quote(timeout, proxy)
        except ProviderError:
            mkt["index"] = {}
        try:
            mkt["sector_flow"] = fetch_sector_flow(timeout, proxy)
        except ProviderError:
            mkt["sector_flow"] = []
        mkt["index_kline"] = fetch_index_kline(timeout, proxy)
        if not mkt["limit_pool"]["pool"]:
            raise ProviderError("涨停池为空（可能非交易日）")
    except Exception:
        mkt = synthesize_market_context()

    with _lock:
        _cache["ts"] = time.time()
        _cache["val"] = mkt
    return mkt


def clear_cache() -> None:
    """清空市场快照缓存（配置变更后调用）。"""
    with _lock:
        _cache["ts"] = 0.0
        _cache["val"] = None
