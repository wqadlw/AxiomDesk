# -*- coding: utf-8 -*-
"""API 路由。

同时挂在 /api 与 /api/v1 两个前缀下，便于平滑演进版本。
所有响应自动携带 X-Request-ID；异常由 errors.py 统一处理。

新增（企业级）：
  - POST /api/jobs        异步分析任务（后台跑 engine，结果落库）
  - GET  /api/jobs/{id}   任务状态 + 结果
  - GET  /api/history     历史分析（SQLite 持久化，可筛选）
  - GET  /api/compare     多标的横向对比（同步，限 5 只）
  - GET  /api/analyze     同步分析（原接口，结果同步落库以便回看）
"""
from __future__ import annotations

import time

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel, Field

from ..engine import engine, investors as INV
from ..jobs import get_store
from ..config_store import (
    get_config, set_config, reset_config, provider_status, effective_data_source,
)
from ..providers.registry import class_for, PROVIDER_META
from ..providers.base import ProviderError
from ..providers.factory import reload_provider
from ..llm.factory import reload_llm
from .errors import BadRequestError
from .schemas import AnalyzeParams

API_VERSION = "2.0.0"

# 无前缀路由，由 app 分别 include 到 /api 与 /api/v1
router = APIRouter()
router_v1 = APIRouter()


# ── 请求体 ──
class JobRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20, description="股票代码 / 名称")
    depth: str = Field("deep", pattern="^(lite|medium|deep)$")
    boost: int = Field(0, ge=0, le=4)
    use_ai: bool = Field(True)


# ── 基础 ──
def _health():
    return {
        "status": "ok",
        "version": API_VERSION,
        "investors": len(INV.INVESTORS),
        "groups": len(INV.GROUPS),
        "dimensions": len(INV.DIM_SCORERS),
    }


def _meta():
    return {
        "version": API_VERSION,
        "groups": INV.GROUPS,
        "investors": [
            {"id": i["id"], "name": i["name"], "group": i["group"], "fields": i.get("fields", [])}
            for i in INV.INVESTORS
        ],
        "dimension_keys": list(INV.DIM_SCORERS.keys()),
        "data_source": _current_data_source(),
    }


def _current_data_source() -> str:
    try:
        return effective_data_source()
    except Exception:
        return "unknown"


# ── 同步分析（落库）──
def _analyze(params: AnalyzeParams = Depends()):
    if not params.ticker or not params.ticker.strip():
        raise BadRequestError("ticker 不能为空")
    try:
        report = engine.analyze(params.ticker, keyword_boost=params.boost,
                                depth=params.depth, use_ai=params.use_ai)
    except ValueError as e:
        raise BadRequestError(str(e))
    except Exception as e:
        raise BadRequestError(f"分析失败：{e}")
    report["version"] = API_VERSION
    report["llm_source"] = report.get("ai", {}).get("_source", "none")
    # 同步分析也落库，便于历史回看
    try:
        get_store().record_sync(params.ticker, params.depth, params.boost, report)
    except Exception:
        pass
    return report


# ── 异步任务 ──
def _create_job(req: JobRequest, bg: BackgroundTasks):
    if not req.ticker or not req.ticker.strip():
        raise BadRequestError("ticker 不能为空")
    store = get_store()
    jid = store.create(req.ticker, req.depth, req.boost)
    bg.add_task(store.run, jid)
    return {"job_id": jid, "status": "pending", "ticker": req.ticker.strip().upper(),
            "depth": req.depth, "version": API_VERSION}


def _get_job(job_id: str):
    store = get_store()
    row = store.get(job_id)
    if not row:
        raise BadRequestError(f"任务不存在：{job_id}")
    out = {
        "job_id": row["id"], "ticker": row["ticker"], "depth": row["depth"],
        "boost": row["boost"], "status": row["status"],
        "created_at": row["created_at"], "finished_at": row["finished_at"],
        "source": row.get("source"), "overall": row.get("overall"), "verdict": row.get("verdict"),
    }
    if row["status"] == "done":
        out["result"] = store.get_result(job_id)
    elif row["status"] == "error":
        out["error"] = (store.get_result(job_id) or {}).get("error")
    return out


def _history(limit: int = Query(50, ge=1, le=500), ticker: str | None = Query(None)):
    return {"version": API_VERSION, "items": get_store().summary_rows(limit=limit, ticker=ticker)}


def _compare(tickers: str = Query(..., description="逗号分隔，最多 5 只，如 600519,300750,000001"),
             depth: str = Query("medium", pattern="^(lite|medium|deep)$"),
             boost: int = Query(0, ge=0, le=4)):
    raw = [t.strip() for t in (tickers or "").split(",") if t.strip()]
    if not raw:
        raise BadRequestError("tickers 不能为空")
    if len(raw) > 5:
        raise BadRequestError("对比最多支持 5 只标的")
    out = []
    for t in raw:
        try:
            r = engine.analyze(t, keyword_boost=boost, depth=depth, use_ai=True)
        except Exception as e:
            out.append({"ticker": t, "error": str(e)})
            continue
        m = r["meta"]
        out.append({
            "ticker": t, "name": m.get("name"), "market": m.get("market"), "industry": m.get("industry"),
            "price": m.get("price"), "mcap": m.get("mcap"), "mcap_unit": m.get("mcap_unit"),
            "pe": m.get("pe"), "pb": m.get("pb"), "roe": m.get("roe"), "rev_growth": m.get("revenue_growth"),
            "overall_score": r.get("overall_score"), "verdict": r.get("verdict"),
            "fair_price": r.get("valuation", {}).get("fair_price"),
            "consensus": r.get("panel_summary", {}).get("panel_consensus"),
            "bullish": r.get("panel_summary", {}).get("bullish"),
            "bearish": r.get("panel_summary", {}).get("bearish"),
            "trap_level": r.get("trap", {}).get("trap_level"),
            "source": r.get("ai", {}).get("_source"),
        })
    return {"version": API_VERSION, "count": len(out), "items": out}


# ── 数据源 / 接口配置 ──
class ConfigUpdate(BaseModel):
    data_source: str | None = None
    cache_ttl: int | None = None
    providers: dict | None = None
    llm: dict | None = None


class ConfigTestRequest(BaseModel):
    provider: str = Field(..., description="要测试的 provider id，如 tencent / tushare")
    ticker: str = "600519"


def _config_get():
    cfg = get_config()
    return {
        "version": API_VERSION,
        "config": cfg,
        "providers": provider_status(),
        "data_source_effective": effective_data_source(),
    }


def _config_put(body: ConfigUpdate):
    cur = get_config()
    patch: dict = {}
    if body.data_source is not None:
        patch["data_source"] = body.data_source
    if body.cache_ttl is not None:
        patch["cache_ttl"] = body.cache_ttl
    if body.providers is not None:
        patch["providers"] = body.providers
    if body.llm is not None:
        patch["llm"] = body.llm
    merged = {**cur, **patch}
    saved = set_config(merged)
    # 重建数据链路与 LLM（使新配置立即生效）
    reload_provider()
    reload_llm()
    return {
        "version": API_VERSION,
        "ok": True,
        "config": saved,
        "providers": provider_status(),
        "data_source_effective": effective_data_source(),
    }


def _config_test(body: ConfigTestRequest):
    pid = body.provider
    if pid not in PROVIDER_META:
        raise BadRequestError(f"未知 provider: {pid}")
    cls = class_for(pid)
    if cls is None:
        raise BadRequestError(f"无法加载 provider: {pid}")
    cfg = get_config()["providers"].get(pid, {})
    try:
        inst = cls(
            timeout=cfg.get("timeout", 8),
            proxy=cfg.get("proxy", ""),
            **({"token": cfg.get("token", "")} if PROVIDER_META[pid]["requires_token"] else {}),
        )
    except Exception as e:
        raise BadRequestError(f"实例化失败: {e}")

    result = {"provider": pid, "name": PROVIDER_META[pid]["name"], "status": "fail",
              "latency_ms": None, "error": None, "sample": None}
    t0 = time.time()
    try:
        if not inst.is_available():
            result["error"] = "provider 当前不可用（库未安装 / 缺少 token）"
            return result
        # 优先 ping（轻量），失败再尝试完整 get_profile 以便回传样本
        try:
            lat = inst.ping()
            result["latency_ms"] = round(lat * 1000, 1)
        except Exception:
            pass
        prof = inst.get_profile(body.ticker)
        if result["latency_ms"] is None:
            result["latency_ms"] = round((time.time() - t0) * 1000, 1)
        result["status"] = "ok"
        result["sample"] = {
            "name": prof.get("name"), "price": prof.get("price"),
            "mcap_yi": prof.get("mcap_yi"), "pe": prof.get("pe"), "pb": prof.get("pb"),
            "source": prof.get("source"),
        }
    except ProviderError as e:
        result["error"] = f"数据获取失败: {e}"
    except Exception as e:  # noqa: BLE001
        result["error"] = f"异常: {e}"
    return result


def _config_reset():
    saved = reset_config()
    reload_provider()
    reload_llm()
    return {
        "version": API_VERSION,
        "ok": True,
        "config": saved,
        "providers": provider_status(),
        "data_source_effective": effective_data_source(),
    }


# 注册到两个路由对象
for _rtr in (router, router_v1):
    _rtr.add_api_route("/health", _health, methods=["GET"])
    _rtr.add_api_route("/meta", _meta, methods=["GET"])
    _rtr.add_api_route("/analyze", _analyze, methods=["GET"])
    _rtr.add_api_route("/jobs", _create_job, methods=["POST"])
    _rtr.add_api_route("/jobs/{job_id}", _get_job, methods=["GET"])
    _rtr.add_api_route("/history", _history, methods=["GET"])
    _rtr.add_api_route("/compare", _compare, methods=["GET"])
    # ── 数据源 / 接口配置 ──
    _rtr.add_api_route("/config", _config_get, methods=["GET"])
    _rtr.add_api_route("/config", _config_put, methods=["PUT"])
    _rtr.add_api_route("/config/test", _config_test, methods=["POST"])
    _rtr.add_api_route("/config/reset", _config_reset, methods=["POST"])
