"""综合研报生成器 — demo 模式结构断言 + 双前缀路由。"""

from fastapi.testclient import TestClient

from server.app import create_app

client = TestClient(create_app())


def test_research_report_single_stock():
    from server.services.research_report import build_research_report

    d = build_research_report(ticker="600519")
    assert d["available"] is True
    assert d["type"] == "single_stock"
    assert "sections" in d and "markdown" in d
    assert len(d["markdown"]) > 100
    assert "综合研判" in d["markdown"]


def test_research_report_market_daily():
    from server.services.research_report import build_research_report

    d = build_research_report(ticker=None)
    assert d["available"] is True
    assert d["type"] == "market_daily"
    assert "markdown" in d


def test_research_report_markdown_format():
    from server.services.research_report import build_research_report

    d = build_research_report(ticker=None, fmt="markdown")
    assert d["format"] == "markdown"
    assert "content" in d and len(d["content"]) > 50


def test_research_report_api_dual_prefix():
    for prefix in ("/api", "/api/v1"):
        r = client.get(f"{prefix}/research-report?ticker=600519")
        assert r.status_code == 200
        body = r.json()
        assert body["version"] == "3.6.0"
        assert body["available"] is True
        assert len(body["markdown"]) > 0
