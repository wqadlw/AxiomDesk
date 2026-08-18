"""信号胜率表 — demo 模式结构断言 + 双前缀路由。"""

from fastapi.testclient import TestClient

from server.app import create_app

client = TestClient(create_app())


def test_signal_quality_demo_structure():
    from server.services.signal_quality import build_signal_quality

    d = build_signal_quality()
    assert d["available"] is True
    assert d["source"] == "demo"
    assert d["universe_size"] > 0
    sigs = d["signals"]
    assert isinstance(sigs, list)
    assert len(sigs) > 0
    for s in sigs:
        assert "id" in s and "name" in s
        assert "win_rate_5" in s and "win_rate_10" in s and "win_rate_20" in s
        assert 0 <= s["win_rate_10"] <= 1.0
        assert isinstance(s["samples"], int) and s["samples"] >= 0
        assert isinstance(s["reliable"], bool)


def test_signal_quality_custom_tickers():
    from server.services.signal_quality import build_signal_quality

    d = build_signal_quality(tickers="600519,000858")
    assert d["available"] is True
    assert d["universe_size"] == 2


def test_signal_quality_api_dual_prefix():
    for prefix in ("/api", "/api/v1"):
        r = client.get(f"{prefix}/signal-quality")
        assert r.status_code == 200
        body = r.json()
        assert body["version"] == "3.5.0"
        assert body["available"] is True
        assert len(body["signals"]) > 0
