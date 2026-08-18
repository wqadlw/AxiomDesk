"""信号胜率回测服务测试（demo 模式，确定性）。"""

import pytest

pytestmark = pytest.mark.usefixtures("client")


def test_backtest_runs_in_demo(monkeypatch):
    monkeypatch.setenv("AXIOM_DATA_SOURCE", "demo")
    from server.services import backtest_runner as BR

    d = BR.run_backtest("600519")
    assert d["available"] is True
    assert d["ticker"] == "600519"
    assert d["signal_stats"], "应有可回测信号"
    assert d["summary"] is not None
    eq = d["equity"]
    assert eq["curve"] and len(eq["curve"]) > 60
    # 净值曲线从 1.0 起
    assert abs(eq["curve"][0] - 1.0) < 1e-6
    # 净值统计字段存在
    for k in ("total_return", "max_drawdown", "sharpe", "bars"):
        assert k in eq


def test_backtest_signal_stats_fields(monkeypatch):
    monkeypatch.setenv("AXIOM_DATA_SOURCE", "demo")
    from server.services import backtest_runner as BR

    d = BR.run_backtest("300750")
    for x in d["signal_stats"]:
        assert "signal_id" in x
        assert "samples" in x
        # 回测结果含 1/5/20 日分桶
        assert "horizons" in x


def test_backtest_endpoint(client, monkeypatch):
    monkeypatch.setenv("AXIOM_DATA_SOURCE", "demo")
    r = client.get("/api/backtest?ticker=600519")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "3.6.0"
    assert body["available"] is True
