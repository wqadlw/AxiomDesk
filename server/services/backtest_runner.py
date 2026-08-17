"""信号胜率回测 API 服务（融合自经验学习项目 tickflow-stock-panel 回测可视化 + instock rate_stats）。

把 ``engine.backtest`` 已有的「信号历史胜率回放」能力暴露成独立端点，并补一段
简单的多头净值模拟，让前端能直接画出：

  - 每个技术信号在历史上触发后的 1 / 5 / 20 日胜率与平均收益（信号可信度锚点）
  - 一条由「强多头信号触发买入、强空头/持仓到期卖出」规则驱动的演示净值曲线

设计原则：
  - 纯 Python，复用 engine.indicators / engine.strategy_signals / engine.backtest，零新依赖；
  - ``AXIOM_DATA_SOURCE=demo`` 或网络失败 → 由 provider 返回确定性 demo K 线，结果可复现；
  - 净值模拟是「演示策略」，仅用于直观呈现信号组合的历史表现，非投资建议。
"""

from __future__ import annotations

from typing import Any

from ..engine import backtest as BT
from ..engine import data_provider as DP
from ..engine import indicators as IND
from ..engine import strategy_signals as SIG

_MIN_BARS = 60
_MAX_HOLD = 20
_ENTRY_THRESHOLD = 0.45


def _features(kline: list[dict]) -> dict[str, Any]:
    """回放用的轻量 features（与 engine.backtest._minimal_features 同义，保持离线确定性）。"""
    closes = [IND._f(r.get("close")) for r in kline]
    mom = (closes[-1] - closes[0]) / closes[0] if len(closes) > 1 and closes[0] else 0.0
    return {
        "momentum": mom,
        "is_hot_theme": False,
        "mkt_source": "demo",
        "mkt_emotion_score": 0.45,
        "mkt_emotion_stage": "平稳",
        "mkt_limit_count": 0,
        "mkt_max_boards": 0,
        "mkt_break_rate": 0.0,
    }


def _simulate_equity(kline: list[dict]) -> dict[str, Any]:
    """简单的多头净值模拟。

    规则（演示用，非投资建议）：
      - 从第 ``_MIN_BARS`` 根 K 线起，逐根回放检测信号；
      - 多头信号强度之和 >= 阈值且无持仓 → 以当根收盘全仓买入；
      - 持仓后若出现空头信号(>=阈值*0.8)或持有达 ``_MAX_HOLD`` 根 → 以当根收盘清仓；
      - 净值归一化到起始 1.0，最终强制平仓。
    """
    n = len(kline)
    equity = [1.0] * n
    cash = 1.0
    shares = 0.0
    hold = 0
    for i in range(_MIN_BARS, n):
        prefix = kline[: i + 1]
        tech = IND.compute_all(prefix)
        price = IND._f(prefix[-1].get("close"))
        if not tech.get("valid") or not price:
            equity[i] = cash + shares * price if price else equity[i - 1]
            continue
        sigs = SIG.detect_all(prefix, tech, _features(prefix))
        bull = sum(s["strength"] for s in sigs if s.get("fired") and str(s.get("side")) in ("bullish", "buy"))
        bear = sum(s["strength"] for s in sigs if s.get("fired") and str(s.get("side")) in ("bearish", "sell"))
        if shares == 0.0 and bull >= _ENTRY_THRESHOLD and i < n - 1:
            shares = cash / price
            cash = 0.0
            hold = 0
        elif shares > 0.0:
            hold += 1
            if (bear >= _ENTRY_THRESHOLD * 0.8 or hold >= _MAX_HOLD) and i < n - 1:
                cash = shares * price
                shares = 0.0
                hold = 0
        equity[i] = cash + shares * price
    # 强制末根平仓
    last = kline[-1]
    last_p = IND._f(last.get("close"))
    if shares > 0.0 and last_p:
        cash = shares * last_p
        shares = 0.0
    if n > 0:
        equity[-1] = cash
    # 末段未交易区沿用 1.0（已初始化）

    # 净值统计
    rets = [(equity[i] - equity[i - 1]) / equity[i - 1] for i in range(1, n) if equity[i - 1]]
    total_return = equity[-1] - 1.0 if n else 0.0
    peak = 1.0
    max_dd = 0.0
    for v in equity:
        peak = max(peak, v)
        if peak > 0:
            max_dd = max(max_dd, (peak - v) / peak)
    import statistics

    mean_r = statistics.fmean(rets) if rets else 0.0
    std_r = statistics.pstdev(rets) if len(rets) > 1 else 0.0
    sharpe = (mean_r / std_r * (252**0.5)) if std_r > 1e-9 else 0.0
    return {
        "curve": [round(v, 4) for v in equity],
        "total_return": round(total_return, 4),
        "max_drawdown": round(max_dd, 4),
        "sharpe": round(sharpe, 2),
        "bars": n,
    }


def run_backtest(ticker: str, days: int = 130) -> dict[str, Any]:
    """对单只标的运行信号胜率回测 + 净值模拟，返回可直接序列化的视图。"""
    if not ticker:
        return {"available": False, "reason": "缺少 ticker"}
    try:
        profile = DP.get_profile(ticker)
        kline = DP.get_kline(ticker, days=days)
    except Exception as e:
        return {"available": False, "reason": f"数据获取失败：{e}"}

    if not kline or len(kline) < _MIN_BARS + 20:
        return {"available": False, "ticker": ticker, "reason": "K 线不足（需 >= 80 根）"}
    tech = IND.compute_all(kline)
    if not tech.get("valid"):
        return {"available": False, "ticker": ticker, "reason": "技术指标计算无效"}

    signals = SIG.detect_all(kline, tech, _features(kline))
    results = BT.backtest_fired(signals, kline)
    summary = BT.best_horizon_stats(results)
    equity = _simulate_equity(kline)

    return {
        "available": True,
        "ticker": ticker,
        "name": profile.get("name", ticker),
        "source": profile.get("source", "demo"),
        "signal_stats": results,
        "summary": summary,
        "equity": equity,
    }
