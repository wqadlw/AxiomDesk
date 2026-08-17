"""策略信号 / 指标 / K 线 provider 的单元测试。

锁定解析逻辑，不触发真实网络：provider.get_kline 用 demo 合成或自定义 K 线序列，
指标与信号均为纯函数、确定性、可复现。
"""

from __future__ import annotations

import pytest

from server.engine import indicators as IND
from server.engine import strategy_signals as SIG
from server.engine.strategy import build_strategy_map


def _kline(closes, vols=None, start="2024-01-01"):
    from datetime import date, timedelta

    rows = []
    for i, c in enumerate(closes):
        o = closes[i - 1] if i > 0 else c * 0.99
        rows.append(
            {
                "date": (date.fromisoformat(start) + timedelta(days=i)).isoformat(),
                "open": round(o, 2),
                "high": round(max(o, c) * 1.01, 2),
                "low": round(min(o, c) * 0.99, 2),
                "close": round(c, 2),
                "volume": float(vols[i]) if vols else 1e6,
            }
        )
    return rows


def _tech(closes, vols=None):
    return IND.compute_all(_kline(closes, vols))


# ───────────────────────── 指标层 ─────────────────────────
def test_sma_ema_basic():
    assert IND.sma([1, 2, 3, 4, 5], 3)[-1] == pytest.approx(4.0)
    assert IND.ema([1, 1, 1, 1], 3) == [1, 1, 1, 1]


def test_macd_golden_detection():
    # 持续上涨 → DIF 应在 DEA 上方（金叉状态）
    closes = [10 + i * 0.3 for i in range(40)]
    dif, dea, _ = IND.macd(closes)
    assert dif[-1] > dea[-1]


def test_atr_positive():
    highs = [11, 12, 13, 12, 14]
    lows = [9, 10, 11, 9, 12]
    closes = [10, 11, 12, 10.5, 13]
    a = IND.atr(highs, lows, closes, 3)
    assert all(x >= 0 for x in a)
    assert a[-1] > 0


def test_vol_ratio():
    vols = [100, 100, 100, 100, 100, 300]
    vr = IND.vol_ratio(vols, 5)
    assert vr[-1] == pytest.approx(3.0, abs=0.01)


def test_pivot_points():
    p = IND.pivot_points(11, 9, 10)
    assert p["P"] == pytest.approx(10.0)
    assert p["R1"] == pytest.approx(11.0)
    assert p["S1"] == pytest.approx(9.0)


def test_chip_poc():
    # 多数成交量堆积在 12 元附近 → POC 接近 12
    rows = []
    for i in range(40):
        c = 12 + (i % 3) * 0.1
        rows.append(
            {"date": "2024-01-%02d" % (i + 1), "open": c, "high": c + 0.2, "low": c - 0.2, "close": c, "volume": 1e6}
        )
    poc = IND.chip_poc(rows)
    assert poc is not None
    assert 11.5 < poc < 12.5


def test_consecutive_limit_ups():
    closes = [10, 11, 12.1, 13.31, 14.64]  # 连续 ~10%
    r = IND.consecutive_limit_ups(closes)
    assert r["boards"] == 4
    assert r["is_limit_up"] is True


# ───────────────────────── 信号层 ─────────────────────────
def test_ma_golden_cross_fires_on_uptrend():
    closes = [10] * 15 + [
        10.2,
        10.5,
        11,
        11.5,
        12,
        12.6,
        13.3,
        14,
        14.8,
        15.7,
        16.7,
        17.8,
        19,
        20.2,
        21.5,
        23,
        24.5,
        26.1,
    ]
    vols = [1e6] * 15 + [2.5e6] * 18
    tech = _tech(closes, vols)
    sig = SIG.ma_golden_cross(_kline(closes, vols), tech, {"momentum": 0.5})
    assert sig["fired"] is True
    assert sig["side"] == "bullish"


def test_breakout_requires_volume_and_high():
    closes = [10] * 60 + [11, 12, 13, 14, 15, 16, 17, 18, 19, 20]  # 60 平台 + 创阶段新高
    vols = [1e6] * 60 + [2e6, 3e6, 4e6, 5e6, 6e6, 7e6, 8e6, 9e6, 1e7, 5e7]  # 末根大幅放量(量比≥2)
    tech = _tech(closes, vols)
    sig = SIG.trend_breakout(_kline(closes, vols), tech, {})
    assert sig["fired"] is True


def test_consecutive_limit_ups_signal():
    closes = [10, 11, 12.1, 13.31, 14.64]
    tech = _tech(closes)
    sig = SIG.consecutive_limit_ups(_kline(closes), tech, {})
    assert sig["fired"] is True
    assert sig["strength"] >= 0.6


def test_oversold_reversal_on_decline():
    closes = [20 - i * 0.5 for i in range(40)]  # 持续下跌
    tech = _tech(closes)
    sig = SIG.oversold_reversal(_kline(closes), tech, {"momentum": -0.2})
    assert sig["fired"] is True


def test_detect_all_structure_and_keys():
    closes = [10] * 10 + [10.5, 11, 11.6, 12.3, 13.1, 14.0, 14.9, 15.9, 17.0, 18.2]
    kline = _kline(closes)
    tech = IND.compute_all(kline)
    feats = {"momentum": 0.4, "is_hot_theme": True}
    sigs = SIG.detect_all(kline, tech, feats)
    assert len(sigs) == 12
    for s in sigs:
        assert {"id", "name", "fired", "strength", "side", "evidence"}.issubset(s.keys())
        assert 0.0 <= s["strength"] <= 1.0


def test_detect_all_no_kline_returns_placeholders():
    sigs = SIG.detect_all([], {"valid": False}, {})
    assert len(sigs) == 12
    assert all(not s["fired"] for s in sigs)


# ───────────────────────── 策略图谱 ─────────────────────────
def test_strategy_map_kline_driven():
    closes = [10] * 15 + [10.2, 10.5, 11, 11.5, 12, 12.6, 13.3, 14]
    kline = _kline(closes)
    tech = IND.compute_all(kline)
    sigs = SIG.detect_all(kline, tech, {"momentum": 0.4, "is_hot_theme": True})
    sm = build_strategy_map({"momentum": 0.4, "is_hot_theme": True}, kline, sigs)
    assert sm["kline_driven"] is True
    assert sm["fired_count"] >= 1
    assert "trend_following" in sm["scores"]
    assert sm["top_evidence"]  # 有真实证据句


def test_strategy_map_fallback_no_kline():
    sm = build_strategy_map({"momentum": 0.1, "volatility": 0.3, "beta": 1.0})
    assert sm["kline_driven"] is False
    assert "trend_following" in sm["scores"]


# ───────────────────────── provider K 线 ─────────────────────────
def test_demo_provider_get_kline():
    from server.providers.demo import DemoDataProvider

    dp = DemoDataProvider()
    kl = dp.get_kline("600519", days=60)
    assert len(kl) > 0
    for r in kl:
        assert {"date", "open", "high", "low", "close", "volume"}.issubset(r.keys())


def test_engine_analyze_includes_kline_strategy():
    from server.engine.engine import analyze

    res = analyze("600519", use_ai=False)
    strat = res["strategy"]
    assert strat["kline_driven"] is True
    assert len(res.get("signals", [])) == 12
    # d2(K线技术) 维度应被真实技术面驱动
    d2 = next((d for d in res["dimensions"] if d["key"] == "2_kline"), None)
    assert d2 is not None
    assert isinstance(d2["score"], (int, float))
