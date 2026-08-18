"""执行层测试（v3.0 新增）：自选股 / 操作计划 / 盘中预警 / 跨会话记忆。

覆盖 go-stock-dev（自选盈亏监控、多情景计划、30 分钟预警去重）与
jcp-master（按股票隔离记忆）移植出来的 services 层 + REST 端点。
所有测试走 conftest 的 demo 确定性数据源。
"""

from __future__ import annotations

import pytest

from server.services import memory as MEM
from server.services import monitor as MN
from server.services import plan as PL
from server.services import watchlist as WL
from server.services.store import get_store

TICKER = "600519"  # demo 数据：贵州茅台，price=1293.09，momentum≈-11.3%


@pytest.fixture(autouse=True)
def _clean_desk():
    """每个测试前后清理执行层存储，保证用例隔离。"""
    store = get_store()
    yield
    for w in store.watchlist_all():
        store.watchlist_delete(w["ticker"])
    store.events_clear()
    with store._conn() as c:
        c.execute("DELETE FROM stock_memory")
        c.execute("DELETE FROM stock_rounds")
        c.execute("DELETE FROM stock_summary")
        c.execute("DELETE FROM plans")


# ───────────────────────── 接口规范化：状态码 ─────────────────────────
def test_not_found_returns_404(client):
    """资源不存在应返回 404（而非 400），且错误体含 code/request_id。"""
    for url in ("/api/jobs/nope", f"/api/watchlist/{TICKER}X", f"/api/plans/{TICKER}X"):
        r = client.get(url)
        assert r.status_code == 404, url
        body = r.json()
        assert body["code"] == "not_found"
        assert "request_id" in body


def test_validation_error_returns_422(client):
    """schema 校验失败（空 ticker / 非法 depth）应返回 422 Unprocessable Entity。"""
    assert client.post("/api/jobs", json={"ticker": "", "depth": "deep"}).status_code == 422
    assert client.post("/api/jobs", json={"ticker": "x", "depth": "ultra"}).status_code == 422


# ───────────────────────── 自选股 watchlist ─────────────────────────
def test_watch_add_returns_snapshot():
    snap = WL.add_watch(TICKER, cost=1300.0, stop_loss=1200.0, target=1500.0, note="底仓")
    assert snap["ticker"] == TICKER
    assert snap["name"] == "贵州茅台"
    assert snap["cost"] == 1300.0
    assert snap["stop_loss"] == 1200.0
    assert snap["target"] == 1500.0
    assert snap["live"] is True
    assert isinstance(snap["pnl_pct"], float)
    assert "stop_gap_pct" in snap and "target_gap_pct" in snap


def test_watch_list_and_remove():
    WL.add_watch(TICKER)
    items = WL.list_watch()
    assert any(i["ticker"] == TICKER for i in items)
    assert WL.remove_watch(TICKER) is True
    assert all(i["ticker"] != TICKER for i in WL.list_watch())


def test_watch_check_alerts_produces_events_with_dedup():
    # 止损位设得比现价高 → 必触发 stop_loss；demo momentum -11.3% → 触发 big_move
    WL.add_watch(TICKER, cost=1300.0, stop_loss=99999.0)
    events = WL.check_alerts()
    kinds = {e["kind"] for e in events}
    assert "stop_loss" in kinds
    assert "big_move" in kinds
    # 30 分钟去重：立即再查一次，不应重复产生
    again = WL.check_alerts()
    assert len(again) == 0


def test_watch_snapshot_falls_back_on_unknown():
    snap = WL.add_watch("999999")  # 未知代码：demo 兜底仍返回快照
    assert snap["ticker"] == "999999"


# ───────────────────────── 操作计划 plan ─────────────────────────
def test_plan_build_full_structure():
    plan = PL.build_plan(TICKER)
    assert plan["ticker"] == TICKER
    assert plan["name"] == "贵州茅台"
    assert {"min", "max"} == set(plan["entry_zone"].keys())
    assert plan["stop_loss"] and plan["stop_loss"] < plan["price"]
    assert plan["target_1"] and plan["target_1"] > plan["price"]
    assert plan["risk_reward"] >= 0
    assert 10 <= plan["position_pct"] <= 80
    assert len(plan["scenarios"]) == 3
    for sc in plan["scenarios"]:
        assert {"name", "condition", "action", "trigger"}.issubset(sc.keys())
    # 落库后可见
    assert PL.get_plan(TICKER)["ticker"] == TICKER


def test_plan_list_and_delete():
    PL.build_plan(TICKER)
    assert any(p["ticker"] == TICKER for p in PL.list_plans())
    assert PL.remove_plan(TICKER) is True
    assert PL.get_plan(TICKER) is None


# ───────────────────────── 盘中预警 monitor ─────────────────────────
def test_monitor_check_watchlist_and_plan():
    WL.add_watch(TICKER, stop_loss=99999.0)
    PL.build_plan(TICKER)
    events = MN.check_watchlist()
    kinds = {e["kind"] for e in events}
    assert "stop_loss" in kinds  # 自选级：跌破止损
    assert "big_move" in kinds  # 自选级：异动
    assert "entry" in kinds  # 计划级：进入入场区（现价大概率在区间内）
    # 去重：第二次不重复
    assert MN.check_watchlist() == []


def test_monitor_events_lifecycle():
    store = get_store()
    store.event_insert(
        {"ticker": TICKER, "name": "贵州茅台", "kind": "big_move", "price": 1293.09, "message": "测试事件"}
    )
    evs = MN.events(limit=10)
    assert len(evs) == 1
    assert MN.alert_stats()["unacknowledged"] == 1
    assert MN.acknowledge(evs[0]["id"]) is True
    assert MN.events(limit=10, unacknowledged_only=True) == []
    assert MN.clear() is True
    assert MN.events() == []


def test_monitor_dedup_within_30min():
    store = get_store()
    assert store.event_recent_same(TICKER, "big_move") is False
    store.event_insert({"ticker": TICKER, "name": "贵州茅台", "kind": "big_move", "price": 1293.09, "message": "x"})
    assert store.event_recent_same(TICKER, "big_move") is True
    assert store.event_recent_same(TICKER, "entry") is False  # 不同种类不互斥


# ───────────────────────── 跨会话记忆 memory ─────────────────────────
def test_memory_remember_recall_and_context():
    MEM.remember(TICKER, "机构连续两日净买入", kind="fact", weight=2.0)
    MEM.remember(TICKER, "建议回调至 1200 下方分批介入", kind="decision", weight=3.0)
    items = MEM.recall(TICKER, query="净买入")
    assert items and items[0]["kind"] == "fact"
    ctx = MEM.recall_context(TICKER, query="介入")
    assert "decision" in ctx and "分批介入" in ctx
    assert MEM.recall(TICKER, query="不存在的词xyz")  # 兜底返回最新


def test_memory_summary_rounds():
    assert MEM.get_summary(TICKER) is None
    MEM.set_summary(TICKER, "贵州茅台：需求韧性 + 提价预期")
    assert "需求韧性" in (MEM.get_summary(TICKER) or "")
    MEM.add_round(TICKER, "第一轮：买入，7.5/10")
    MEM.add_round(TICKER, "第二轮：持有，7.2/10")
    rounds = MEM.recent_rounds(TICKER)
    assert len(rounds) == 2
    assert any("第二轮" in r["content"] for r in rounds)


def test_memory_remember_analysis_auto_sediment():
    from server.engine import engine

    res = engine.analyze(TICKER, use_ai=False)
    MEM.remember_analysis(TICKER, res)
    items = MEM.recall(TICKER)
    kinds = {it["kind"] for it in items}
    # 决策（评级）+ 事实（POC）+ 观点（信号）+ 轮次
    assert "decision" in kinds
    assert MEM.recent_rounds(TICKER)


# ───────────────────────── API 执行层端点 ─────────────────────────
def test_api_watchlist_crud(client):
    r = client.post("/api/watchlist", json={"ticker": TICKER, "cost": 1300.0, "note": "t"})
    assert r.status_code == 200 and r.json()["item"]["ticker"] == TICKER
    assert client.get("/api/watchlist").json()["items"][0]["name"] == "贵州茅台"
    assert client.get(f"/api/watchlist/{TICKER}").json()["item"]["ticker"] == TICKER
    assert client.delete(f"/api/watchlist/{TICKER}").json()["ok"] is True
    assert client.get("/api/watchlist").json()["items"] == []


def test_api_plan_and_events(client):
    assert client.post(f"/api/plans/{TICKER}").status_code == 200
    plan = client.get(f"/api/plans/{TICKER}").json()["plan"]
    assert plan["entry_zone"]["min"] > 0
    assert client.get("/api/plans").json()["items"][0]["ticker"] == TICKER
    # 监控巡检
    client.post("/api/watchlist", json={"ticker": TICKER, "stop_loss": 99999.0})
    r = client.post("/api/monitor/check").json()
    assert r["new_events"]  # 至少一条事件
    assert r["stats"]["unacknowledged"] >= 1
    # 事件确认与清空
    ev = client.get("/api/events").json()["items"][0]
    assert client.post(f"/api/events/{ev['id']}/ack").json()["ok"] is True
    assert client.post("/api/events/clear").json()["ok"] is True
    assert client.get("/api/events").json()["items"] == []
    assert client.delete(f"/api/plans/{TICKER}").json()["ok"] is True


def test_api_memory_endpoints(client):
    r = client.post(f"/api/memory/{TICKER}", json={"content": "游资接力迹象", "kind": "view", "weight": 2.0})
    assert r.json()["ok"] is True
    items = client.get(f"/api/memory/{TICKER}", params={"query": "游资"}).json()["items"]
    assert items and items[0]["content"] == "游资接力迹象"
    assert client.post(f"/api/memory/{TICKER}/summary", json={"summary": "茅台：需求韧性"}).json()["ok"] is True
    assert client.get(f"/api/memory/{TICKER}/summary").json()["summary"] == "茅台：需求韧性"
    assert client.get(f"/api/memory/{TICKER}/rounds").json()["rounds"] == []


def test_api_version_is_340(client):
    assert client.get("/api/health").json()["version"] == "3.5.0"
