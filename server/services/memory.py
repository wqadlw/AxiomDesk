"""跨会话股票记忆 · 移植 jcp-master ``memory/`` 的按股票隔离记忆设计。

能力（轻量版）：
  - 关键事实 / 观点 / 决策（kind: fact / view / decision）带权重落库
  - 每轮分析记录（round）自动追加，保持上下文连续性
  - 关键词召回：query 与记忆内容做 token 重叠打分（纯 Python，无外部分词依赖）
  - 摘要：由 AI 研判层可写入压缩摘要（stock_summary），分析时回填给 LLM

用法：
  - analyze 前：``recall_context(ticker)`` 取历史要点 → 注入 AI 研判 prompt
  - analyze 后：``remember_analysis(ticker, result)`` 自动沉淀关键事实
"""

from __future__ import annotations

from .store import get_store


def remember(ticker: str, content: str, kind: str = "fact", weight: float = 1.0) -> None:
    """写入一条记忆（fact / view / decision）。"""
    get_store().memory_add(ticker, kind, content, weight)


def recall(ticker: str, query: str = "", limit: int = 8) -> list[dict]:
    """按关键词召回该股票的历史记忆（按相关性 + 权重排序）。"""
    return get_store().memory_recall(ticker, query=query, limit=limit)


def recall_context(ticker: str, query: str = "", limit: int = 6) -> str:
    """召回并格式化成供 LLM 引用的上下文文本。"""
    items = recall(ticker, query=query, limit=limit)
    if not items:
        return ""
    lines = []
    for it in items:
        kind = it.get("kind", "fact")
        lines.append(f"- [{kind}] {it.get('content', '')}")
    return "\n".join(lines)


def set_summary(ticker: str, summary: str) -> None:
    get_store().memory_summary_set(ticker, summary)


def get_summary(ticker: str) -> str | None:
    return get_store().memory_summary_get(ticker)


def add_round(ticker: str, content: str) -> None:
    get_store().memory_round_add(ticker, content)


def recent_rounds(ticker: str, limit: int = 5) -> list[dict]:
    return get_store().memory_rounds(ticker, limit=limit)


def remember_analysis(ticker: str, result: dict) -> None:
    """分析完成后自动沉淀关键结论（判定 / 评级 / 策略 / 信号证据）。"""
    meta = result.get("meta") or {}
    name = meta.get("name") or ticker
    verdict = result.get("verdict", "")
    overall = result.get("overall_score")
    strat = result.get("strategy") or {}
    # 决策类记忆：评级
    remember(
        ticker,
        f"{name} 评级 {verdict}（综合分 {overall}/10），推荐风格 {strat.get('recommended', '?')}",
        kind="decision",
        weight=3.0,
    )
    # 事实类记忆：关键价位
    kl = result.get("key_levels") or {}
    poc = kl.get("poc")
    if poc:
        remember(ticker, f"{name} 成交密集区(POC) ≈ {poc}", kind="fact", weight=2.0)
    # 观点类记忆：最强信号
    ev = strat.get("top_evidence") or []
    for e in ev[:2]:
        remember(ticker, f"{name} 信号：{e}", kind="view", weight=1.5)
    # 记录本轮
    add_round(ticker, f"{name}：{verdict}，综合分 {overall}/10，推荐 {strat.get('recommended', '?')}")


def summarize_and_store(ticker: str, summary: str) -> None:
    """由 AI 研判层生成的压缩摘要落库（下次分析回填）。"""
    set_summary(ticker, summary)
