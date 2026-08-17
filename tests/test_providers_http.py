"""实时数据源（腾讯/HTTP 基元）解析逻辑的离线测试。

通过 monkeypatch http_get 注入真实形态的响应，锁定「把网络文本解析成
结构化 profile」这条生产关键路径——它依赖真实 A 股接口字段，最易在线上出 bug。
不触发任何真实网络请求。
"""

from __future__ import annotations

import json

import pytest

from server.providers import tencent_provider as TENC
from server.providers.http_base import secid_for, to_float


# ─────────────── http_base 纯函数 ───────────────
def test_to_float_clean():
    assert to_float("3.14") == 3.14
    assert to_float("100") == 100.0


def test_to_float_dirty():
    assert to_float("1,234.5") == 1234.5
    assert to_float("12%") == 12.0
    assert to_float("500亿") == 500.0
    assert to_float("1,000万") == 1000.0


def test_to_float_invalid_defaults_zero():
    assert to_float(None) == 0.0
    assert to_float("--") == 0.0
    assert to_float("") == 0.0
    assert to_float("nan") == 0.0
    assert to_float("NaN") == 0.0


def test_secid_for_a_sh():
    assert secid_for("600519") == ("sh", "1.600519")


def test_secid_for_a_sz():
    assert secid_for("000001") == ("sz", "0.000001")
    assert secid_for("300750") == ("sz", "0.300750")


def test_secid_for_hk():
    assert secid_for("HK00700") == ("hk", "116.00700")
    assert secid_for("00700") == ("hk", "116.00700")


def test_secid_for_invalid():
    assert secid_for("ABC") is None
    assert secid_for("") is None


# ─────────────── 腾讯行情解析 ───────────────
def _quote_row(price="1685.00", pe="32.5", pb="9.8", mcap="21200.0"):
    """构造 47 字段的腾讯行情字符串（索引见 tencent_provider 注释）。"""
    f = ["0"] * 47
    f[0] = "1"
    f[1] = "贵州茅台"
    f[2] = "600519"
    f[3] = price
    f[4] = "1700.00"
    f[5] = "1690.00"
    f[32] = "-0.88"
    f[33] = "1710.00"
    f[34] = "1670.00"
    f[36] = "3456789"
    f[37] = "582134.5"
    f[38] = "0.28"
    f[39] = pe
    f[44] = mcap
    f[45] = mcap
    f[46] = pb
    return 'v_sh600519="' + "~".join(f) + '";'


def _kline_json(closes):
    rows = [[f"2024-01-{i:02d}", c * 0.99, c, c * 1.01, c * 0.98, 1000] for i, c in enumerate(closes, 1)]
    return json.dumps({"data": {"sh600519": {"qfqday": rows}}})


@pytest.fixture
def fake_http():
    """按 URL 区分：行情接口返回行情串，K线接口返回 JSON。"""

    def _http(url, **kw):
        if "qt.gtimg.cn" in url:
            return _quote_row()
        if "fqkline" in url:
            return _kline_json([100, 102, 101, 105, 108, 107, 110, 112, 115, 120])
        raise AssertionError("unexpected url: " + url)

    return _http


def test_tencent_quote_parsing(fake_http, monkeypatch):
    monkeypatch.setattr(TENC, "http_get", fake_http)
    p = TENC.TencentDataProvider()
    q = p._quote("sh", "600519")
    assert q["name"] == "贵州茅台"
    assert q["price"] == 1685.0
    assert q["pe"] == 32.5
    assert q["pb"] == 9.8
    assert q["mcap_yi"] == 21200.0
    assert q["change_pct"] == -0.0088


def test_tencent_quote_invalid_price(fake_http, monkeypatch):
    monkeypatch.setattr(TENC, "http_get", lambda url, **kw: _quote_row(price="0"))
    p = TENC.TencentDataProvider()
    with pytest.raises(Exception):
        p._quote("sh", "600519")


def test_tencent_kline_parsing(fake_http, monkeypatch):
    monkeypatch.setattr(TENC, "http_get", fake_http)
    p = TENC.TencentDataProvider()
    momentum, vol = p._kline("sh", "600519")
    assert momentum > 0  # 100 → 120
    assert 0.05 <= vol <= 1.5


def test_tencent_kline_too_short(monkeypatch):
    monkeypatch.setattr(
        TENC,
        "http_get",
        lambda url, **kw: json.dumps({"data": {"sh600519": {"qfqday": [["2024-01-01", 1, 2, 3, 4, 5]]}}}),
    )
    p = TENC.TencentDataProvider()
    assert p._kline("sh", "600519") == (0.0, 0.3)


def test_tencent_get_profile_merges_demo(fake_http, monkeypatch):
    monkeypatch.setattr(TENC, "http_get", fake_http)
    p = TENC.TencentDataProvider()
    prof = p.get_profile("600519")  # 600519 在内置 DEMO 表，应合并 ROE 等
    assert prof["name"] == "贵州茅台"
    assert prof["price"] == 1685.0
    assert prof["roe"] > 0  # 来自 DEMO 兜底
    assert prof["source"]  # 非空


def test_tencent_unsupported_ticker():
    p = TENC.TencentDataProvider()
    with pytest.raises(Exception):
        p.get_profile("USD")  # secid_for → None


def test_tencent_peers_unsupported():
    p = TENC.TencentDataProvider()
    with pytest.raises(Exception):
        p.get_peers("600519", {})
