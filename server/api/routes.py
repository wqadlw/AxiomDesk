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
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel, Field

from ..config_store import (
    effective_data_source,
    get_config,
    provider_status,
    reset_config,
    set_config,
)
from ..engine import data_provider as DP
from ..engine import engine
from ..engine import investors as INV
from ..jobs import get_store
from ..llm.factory import reload_llm
from ..providers.base import ProviderError
from ..providers.factory import reload_provider
from ..providers.registry import PROVIDER_META, class_for
from ..services import capital_flow as CF
from ..services import daily_digest as DD
from ..services import event_calendar as EC
from ..services import market_sentiment as MS
from ..services import memory as MEM
from ..services import monitor as MN
from ..services import plan as PL
from ..services import research_report as RR
from ..services import risk_watch as RW
from ..services import screener as SC
from ..services import signal_quality as SQ
from ..services import stock_diagnosis as DX
from ..services import watchlist as WL
from .errors import BadRequestError, NotFoundError
from .schemas import AnalyzeParams

API_VERSION = "3.7.0"

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
        report = engine.analyze(params.ticker, keyword_boost=params.boost, depth=params.depth, use_ai=params.use_ai)
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
    return {
        "job_id": jid,
        "status": "pending",
        "ticker": req.ticker.strip().upper(),
        "depth": req.depth,
        "version": API_VERSION,
    }


def _get_job(job_id: str):
    store = get_store()
    row = store.get(job_id)
    if not row:
        raise NotFoundError(f"任务不存在：{job_id}")
    out = {
        "job_id": row["id"],
        "ticker": row["ticker"],
        "depth": row["depth"],
        "boost": row["boost"],
        "status": row["status"],
        "created_at": row["created_at"],
        "finished_at": row["finished_at"],
        "source": row.get("source"),
        "overall": row.get("overall"),
        "verdict": row.get("verdict"),
    }
    if row["status"] == "done":
        out["result"] = store.get_result(job_id)
    elif row["status"] == "error":
        out["error"] = (store.get_result(job_id) or {}).get("error")
    return out


def _history(limit: int = Query(50, ge=1, le=500), ticker: str | None = Query(None)):
    return {"version": API_VERSION, "items": get_store().summary_rows(limit=limit, ticker=ticker)}


def _compare(
    tickers: str = Query(..., description="逗号分隔，最多 5 只，如 600519,300750,000001"),
    depth: str = Query("medium", pattern="^(lite|medium|deep)$"),
    boost: int = Query(0, ge=0, le=4),
):
    raw = [t.strip() for t in (tickers or "").split(",") if t.strip()]
    if not raw:
        raise BadRequestError("tickers 不能为空")
    if len(raw) > 5:
        raise BadRequestError("对比最多支持 5 只标的")
    out: list[dict[str, Any]] = []
    for t in raw:
        try:
            r = engine.analyze(t, keyword_boost=boost, depth=depth, use_ai=True)
        except Exception as e:
            out.append({"ticker": t, "error": str(e)})
            continue
        m = r["meta"]
        out.append(
            {
                "ticker": t,
                "name": m.get("name"),
                "market": m.get("market"),
                "industry": m.get("industry"),
                "price": m.get("price"),
                "mcap": m.get("mcap"),
                "mcap_unit": m.get("mcap_unit"),
                "pe": m.get("pe"),
                "pb": m.get("pb"),
                "roe": m.get("roe"),
                "rev_growth": m.get("revenue_growth"),
                "overall_score": r.get("overall_score"),
                "verdict": r.get("verdict"),
                "fair_price": r.get("valuation", {}).get("fair_price"),
                "consensus": r.get("panel_summary", {}).get("panel_consensus"),
                "bullish": r.get("panel_summary", {}).get("bullish"),
                "bearish": r.get("panel_summary", {}).get("bearish"),
                "trap_level": r.get("trap", {}).get("trap_level"),
                "source": r.get("ai", {}).get("_source"),
            }
        )
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

    result = {
        "provider": pid,
        "name": PROVIDER_META[pid]["name"],
        "status": "fail",
        "latency_ms": None,
        "error": None,
        "sample": None,
    }
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
            "name": prof.get("name"),
            "price": prof.get("price"),
            "mcap_yi": prof.get("mcap_yi"),
            "pe": prof.get("pe"),
            "pb": prof.get("pb"),
            "source": prof.get("source"),
        }
    except ProviderError as e:
        result["error"] = f"数据获取失败: {e}"
    except Exception as e:
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


# ── 执行层：自选股 ──
class WatchAdd(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20, description="股票代码 / 名称")
    cost: float | None = Field(None, ge=0, description="成本价；缺省用现价")
    stop_loss: float | None = Field(None, ge=0)
    target: float | None = Field(None, ge=0)
    note: str = Field("", max_length=200)


def _watch_list():
    return {"version": API_VERSION, "count": WL.watch_count(), "items": WL.list_watch()}


def _watch_add(body: WatchAdd):
    if not body.ticker.strip():
        raise BadRequestError("ticker 不能为空")
    try:
        item = WL.add_watch(body.ticker.strip().upper(), body.cost, body.stop_loss, body.target, body.note)
    except ValueError as e:
        raise BadRequestError(str(e))
    return {"version": API_VERSION, "ok": True, "item": item}


def _watch_get(ticker: str):
    row = WL.get_store().watchlist_get(ticker)
    if not row:
        raise NotFoundError(f"自选不存在：{ticker}")
    return {"version": API_VERSION, "item": WL.snapshot_one(ticker, cached=row)}


def _watch_delete(ticker: str):
    WL.remove_watch(ticker)
    return {"version": API_VERSION, "ok": True}


# ── 执行层：盘中预警事件 ──
def _events_recent(limit: int = Query(50, ge=1, le=500), unack: bool = Query(False, alias="unacknowledged")):
    return {
        "version": API_VERSION,
        "items": MN.events(limit=limit, unacknowledged_only=unack),
        "stats": MN.alert_stats(),
    }


def _events_ack(event_id: int):
    MN.acknowledge(event_id)
    return {"version": API_VERSION, "ok": True}


def _events_clear():
    MN.clear()
    return {"version": API_VERSION, "ok": True}


def _monitor_check():
    new_events = MN.check_watchlist()
    return {"version": API_VERSION, "new_events": new_events, "stats": MN.alert_stats()}


# ── 执行层：操作计划 ──
def _plan_list():
    return {"version": API_VERSION, "count": len(PL.list_plans()), "items": PL.list_plans()}


def _plan_get(ticker: str):
    p = PL.get_plan(ticker)
    if not p:
        raise NotFoundError(f"暂无操作计划：{ticker}（可 POST /api/plans/{ticker} 生成）")
    return {"version": API_VERSION, "plan": p}


def _plan_build(ticker: str, depth: str = Query("deep", pattern="^(lite|medium|deep)$")):
    try:
        plan = PL.build_plan(ticker, depth=depth)
    except Exception as e:
        raise BadRequestError(f"计划生成失败：{e}")
    return {"version": API_VERSION, "ok": True, "plan": plan}


def _plan_delete(ticker: str):
    PL.remove_plan(ticker)
    return {"version": API_VERSION, "ok": True}


# ── 执行层：跨会话记忆 ──
class RememberRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)
    kind: str = Field("fact", pattern="^(fact|view|decision)$")
    weight: float = Field(1.0, ge=0.1, le=10.0)


class SummaryRequest(BaseModel):
    summary: str = Field(..., min_length=1, max_length=2000)


def _mem_recall(ticker: str, query: str = Query("", max_length=100)):
    return {
        "version": API_VERSION,
        "context": MEM.recall_context(ticker, query=query),
        "items": MEM.recall(ticker, query=query),
    }


def _mem_remember(ticker: str, body: RememberRequest):
    MEM.remember(ticker, body.content, kind=body.kind, weight=body.weight)
    return {"version": API_VERSION, "ok": True}


def _mem_summary_get(ticker: str):
    return {"version": API_VERSION, "summary": MEM.get_summary(ticker)}


def _mem_summary_set(ticker: str, body: SummaryRequest):
    MEM.summarize_and_store(ticker, body.summary)
    return {"version": API_VERSION, "ok": True}


def _mem_rounds(ticker: str):
    return {"version": API_VERSION, "rounds": MEM.recent_rounds(ticker)}


def _limit_ladder(date_s: str | None = Query(None, description="可选：指定日期 YYYYMMDD（默认当日）")):
    """连板梯队 + 涨停异动监控（融合 a-stock-data / tickflow-stock-panel）。

    由 providers.market 的统一市场快照派生，任意网络失败都回退到确定性 demo，永不中断。
    """
    from ..services import limit_ladder as LL

    return {"version": API_VERSION, **LL.build_limit_ladder(date_s=date_s)}


def _sector_rotation(top_n: int = Query(30, description="每个维度返回的板块数", ge=1, le=80)):
    """板块轮动矩阵（融合 tickflow-stock-panel 轮动矩阵 + a-stock-data 板块资金流）。

    返回行业 / 概念板块的今日、5日、10日涨跌幅与主力净流入；demo 或网络失败回退确定性数据。
    """
    from ..services import sector_rotation as SR

    return {"version": API_VERSION, **SR.build_sector_rotation(top_n=top_n)}


def _longhubang(
    date_s: str | None = Query(None, description="可选：指定日期 YYYYMMDD（默认当日）"),
    top_n: int = Query(20, description="返回条数", ge=1, le=50),
):
    """龙虎榜游资评分（融合 aiagents-stock longhubang_scoring 体系）。

    best-effort 拉取东财龙虎榜并给出游资参与度综合评分；失败回退确定性演示评分。
    """
    from ..services import longhubang as LH

    return {"version": API_VERSION, **LH.build_longhubang(date_s=date_s, top_n=top_n)}


def _backtest(
    ticker: str = Query(..., description="标的代码，如 600519"),
    days: int = Query(130, description="回测所用 K 线天数", ge=80, le=400),
):
    """信号胜率回测 + 净值模拟（融合 tickflow 回测可视化 + instock rate_stats）。

    复用 engine.backtest 的「信号历史胜率回放」并补一段演示净值曲线。
    """
    from ..services import backtest_runner as BR

    return {"version": API_VERSION, **BR.run_backtest(ticker=ticker, days=days)}


def _screener(
    universe: str = Query("demo", description="股票池：demo(演示池) | watchlist(自选) | 任意(配合 tickers)"),
    tickers: str | None = Query(None, description="逗号分隔的自定义代码列表，覆盖 universe"),
    min_score: float = Query(0.0, description="最低综合评分（0~100）", ge=0, le=100),
    min_signals: int = Query(0, description="最少命中多头信号数", ge=0, le=18),
    side: str = Query("bullish", description="方向过滤：bullish | bearish | any"),
    sort: str = Query("score", description="排序：score | rps | signals | momentum"),
    limit: int = Query(20, description="返回条数上限", ge=1, le=60),
):
    """选股引擎（融合 Sequoia-X RPS 相对强度 + InStock 因子扫描 + stock-master 形态选股）。

    复用 engine 的 compute_all(含 RPS) / detect_all(18 形态信号)，对股票池批量评分排序。
    """
    return {
        "version": API_VERSION,
        **SC.scan(
            universe=universe,
            tickers=tickers,
            min_score=min_score,
            min_signals=min_signals,
            side=side,
            sort=sort,
            limit=limit,
        ),
    }


def _daily_digest(date_s: str | None = Query(None, description="可选：指定日期 YYYYMMDD（默认当日）")):
    """盘后速览（融合 daily_stock_analysis 收盘复盘）：聚合情绪/连板/板块/龙虎榜为一页速览。"""
    return {"version": API_VERSION, **DD.build_digest(date_s=date_s)}


def _capital_flow(ticker: str = Query(..., description="标的代码，如 600519")):
    """个股五档资金流（融合 go-stock-dev 资金流面板 + adata 五档净流入）。

    返回超大/大/中/小单当日与 20 日净流入、主力净额与占流通比；demo 或网络失败回退确定性数据。
    """
    return {"version": API_VERSION, **CF.build_capital_flow(ticker=ticker)}


def _capital_flow_board(
    scope: str = Query("industry", description="板块范围：industry(行业) | concept(概念)"),
    days: int = Query(5, description="资金窗口（仅影响种子，使窗口结果稳定）", ge=1, le=10),
    topn: int = Query(20, description="返回条数", ge=1, le=40),
):
    """板块资金流榜（融合 a-stock-data 板块资金流）：行业/概念今日·5日·10日 主力净流入排行。"""
    return {"version": API_VERSION, **CF.build_board_flow(scope=scope, days=days, topn=topn)}


def _capital_flow_north():
    """北向资金（融合 adata 沪深港通净买卖）：沪股通/深股通/合计 当日与 5 日净流入。"""
    return {"version": API_VERSION, **CF.build_north_flow()}


def _sentiment():
    """市场情绪仪表盘（融合 aiagents-stock 恐惧贪婪指数 + 涨跌停统计 + 量能热度）。"""
    return {"version": API_VERSION, **MS.build_sentiment()}


def _risk_watch(ticker: str | None = Query(None, description="可选：指定标的则看个股级风险，缺省看市场级扫描")):
    """风险监控（融合 TradingAgents 解禁减持三条封杀线 + 估值异常扫描）。"""
    return {"version": API_VERSION, **RW.build_risk_watch(ticker=ticker)}


def _event_calendar(
    ticker: str | None = Query(None, description="可选：指定标的则看个股级日历，缺省看市场级汇总"),
    days: int = Query(30, description="未来 N 日窗口", ge=1, le=120),
):
    """财经日历（融合 stock-master 解禁/分红/定增爬虫）：解禁/定增/分红/财报时间线。"""
    return {"version": API_VERSION, **EC.build_event_calendar(ticker=ticker, days=days)}


def _diagnosis(ticker: str = Query(..., description="标的代码，如 600519")):
    """个股全景诊断（融合 daily_stock_analysis decision_scale + TradingAgents 五级评级 + aiagents-stock 五维加权）。

    把技术/RPS/资金/情绪/估值/事件/风控/连板/龙虎榜融合为「综合研判卡」：
    六维评分 → 加权综合分 → 五档动作（强烈买入/买入/观望/减仓/卖出）+ 结论 + 风险提示。
    """
    return {"version": API_VERSION, **DX.build_diagnosis(ticker=ticker)}


def _signal_quality(
    tickers: str | None = Query(None, description="逗号分隔代码列表；缺省用内置演示池（跨标的统计更稳）"),
    days: int = Query(130, description="回测所用 K 线天数", ge=80, le=400),
):
    """信号胜率表（融合 tickflow factor.py + instock rate_stats）。

    遍历股票池逐 bar 回测 18 个形态信号，统计触发后 N=5/10/20 日胜率与平均收益，标注高可靠信号。
    """
    return {"version": API_VERSION, **SQ.build_signal_quality(tickers=tickers, days=days)}


def _research_report(
    ticker: str | None = Query(None, description="标的代码（如 600519）；缺省则生成市场日报"),
    fmt: str = Query("json", description="json=结构化+Markdown；markdown=仅返回 Markdown 文本"),
):
    """综合研报生成器（融合 daily_stock_analysis 报告结构 + TradingAgents research_report 范式）。

    给定 ticker 生成个股深度研报（六维诊断 + 资金 + 事件 + 风险 + 信号胜率聚合）；
    缺省生成市场日报（盘后速览 + 信号胜率亮点 + 财经日历）。支持 Markdown 导出。
    """
    return {"version": API_VERSION, **RR.build_research_report(ticker=ticker, fmt=fmt)}


def _kline(
    ticker: str = Query(..., description="标的代码，如 600519"),
    days: int = Query(120, description="K 线天数", ge=20, le=400),
):
    """个股日 K 线 OHLCV（融合 tickflow K 线可视化）：前复权日线 + 5/10/20 日均线，供前端绘制蜡烛图。

    任何网络失败都回退到确定性 demo K 线，永不中断。
    """
    raw = DP.get_kline(ticker, days=days)
    if not raw:
        return {
            "version": API_VERSION,
            "available": False,
            "ticker": ticker,
            "reason": "无 K 线数据",
            "kline": [],
            "ma": {"ma5": [], "ma10": [], "ma20": []},
        }
    # 统一保证时间升序（兼容各 provider 不同的返回顺序）
    raw = sorted(raw, key=lambda r: str(r.get("date", "")))

    def _num(v, default: float = 0.0) -> float:
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    kline = [
        {
            "date": str(r.get("date") or ""),
            "open": _num(r.get("open")),
            "high": _num(r.get("high")),
            "low": _num(r.get("low")),
            "close": _num(r.get("close")),
            "volume": _num(r.get("volume")),
        }
        for r in raw
    ]
    closes: list[float] = [_num(r["close"]) for r in kline]
    def _ma(n: int) -> list[float | None]:
        out: list[float | None] = []
        for i in range(len(closes)):
            if i + 1 < n:
                out.append(None)
            else:
                seg = closes[i + 1 - n : i + 1]
                out.append(round(sum(seg) / n, 2))
        return out

    prof: dict = {}
    try:
        prof = DP.get_profile(ticker) or {}
    except Exception:
        prof = {}
    return {
        "version": API_VERSION,
        "available": True,
        "ticker": ticker,
        "name": prof.get("name"),
        "price": prof.get("price"),
        "source": prof.get("source"),
        "days": days,
        "kline": kline,
        "ma": {"ma5": _ma(5), "ma10": _ma(10), "ma20": _ma(20)},
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
    # ── 执行层：自选股 ──
    _rtr.add_api_route("/watchlist", _watch_list, methods=["GET"])
    _rtr.add_api_route("/watchlist", _watch_add, methods=["POST"])
    _rtr.add_api_route("/watchlist/{ticker}", _watch_get, methods=["GET"])
    _rtr.add_api_route("/watchlist/{ticker}", _watch_delete, methods=["DELETE"])
    # ── 执行层：盘中预警事件 ──
    _rtr.add_api_route("/events", _events_recent, methods=["GET"])
    _rtr.add_api_route("/events/{event_id}/ack", _events_ack, methods=["POST"])
    _rtr.add_api_route("/events/clear", _events_clear, methods=["POST"])
    _rtr.add_api_route("/monitor/check", _monitor_check, methods=["POST"])
    # ── 执行层：操作计划 ──
    _rtr.add_api_route("/plans", _plan_list, methods=["GET"])
    _rtr.add_api_route("/plans/{ticker}", _plan_get, methods=["GET"])
    _rtr.add_api_route("/plans/{ticker}", _plan_build, methods=["POST"])
    _rtr.add_api_route("/plans/{ticker}", _plan_delete, methods=["DELETE"])
    # ── 执行层：跨会话记忆 ──
    _rtr.add_api_route("/memory/{ticker}", _mem_recall, methods=["GET"])
    _rtr.add_api_route("/memory/{ticker}", _mem_remember, methods=["POST"])
    _rtr.add_api_route("/memory/{ticker}/summary", _mem_summary_get, methods=["GET"])
    _rtr.add_api_route("/memory/{ticker}/summary", _mem_summary_set, methods=["POST"])
    _rtr.add_api_route("/memory/{ticker}/rounds", _mem_rounds, methods=["GET"])
    # ── 市场级：连板梯队 / 涨停异动（融合 a-stock-data / tickflow-stock-panel）──
    _rtr.add_api_route("/limit-ladder", _limit_ladder, methods=["GET"])
    # ── 市场级：板块轮动矩阵（融合 tickflow 轮动矩阵 + a-stock-data 板块资金流）──
    _rtr.add_api_route("/sector-rotation", _sector_rotation, methods=["GET"])
    # ── 市场级：龙虎榜游资评分（融合 aiagents-stock longhubang_scoring）──
    _rtr.add_api_route("/longhubang", _longhubang, methods=["GET"])
    # ── 个股级：信号胜率回测 + 净值模拟（融合 tickflow 回测 + instock rate_stats）──
    _rtr.add_api_route("/backtest", _backtest, methods=["GET"])
    # ── 市场级：选股引擎（融合 Sequoia-X RPS + InStock 因子 + stock-master 形态）──
    _rtr.add_api_route("/screener", _screener, methods=["GET"])
    # ── 市场级：盘后速览（融合 daily_stock_analysis 收盘复盘）──
    _rtr.add_api_route("/daily-digest", _daily_digest, methods=["GET"])
    # ── 资金面：个股五档资金流（融合 go-stock-dev 资金流面板 + adata 五档净流入）──
    _rtr.add_api_route("/capital-flow", _capital_flow, methods=["GET"])
    # ── 资金面：板块资金流榜（融合 a-stock-data 板块资金流）──
    _rtr.add_api_route("/capital-flow/board", _capital_flow_board, methods=["GET"])
    # ── 资金面：北向资金（融合 adata 沪深港通净买卖）──
    _rtr.add_api_route("/capital-flow/north", _capital_flow_north, methods=["GET"])
    # ── 情绪面：市场情绪仪表盘（融合 aiagents-stock 恐惧贪婪指数）──
    _rtr.add_api_route("/sentiment", _sentiment, methods=["GET"])
    # ── 风控面：风险监控（融合 TradingAgents 解禁减持三条封杀线）──
    _rtr.add_api_route("/risk-watch", _risk_watch, methods=["GET"])
    # ── 事件面：财经日历（融合 stock-master 解禁/分红/定增爬虫）──
    _rtr.add_api_route("/event-calendar", _event_calendar, methods=["GET"])
    # ── 融合贯通：个股全景诊断（六维综合研判卡）──
    _rtr.add_api_route("/diagnosis", _diagnosis, methods=["GET"])
    # ── 量化背书：信号历史胜率表（跨标的回测）──
    _rtr.add_api_route("/signal-quality", _signal_quality, methods=["GET"])
    # ── 融合贯通：综合研报生成器（个股深度研报 / 市场日报 + Markdown 导出）──
    _rtr.add_api_route("/research-report", _research_report, methods=["GET"])
    # ── 个股级：日 K 线 OHLCV + 均线（融合 tickflow K 线可视化）──
    _rtr.add_api_route("/kline", _kline, methods=["GET"])
