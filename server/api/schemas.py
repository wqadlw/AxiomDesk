# -*- coding: utf-8 -*-
"""请求/响应 schema · 用于入参校验与 OpenAPI 文档。"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AnalyzeParams(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20, description="股票代码或名称，如 600519 / 宁德时代 / TSLA")
    boost: int = Field(0, ge=0, le=4, description="杀猪盘语境加权 0-4（朋友推荐/老师/内幕/翻倍等）")
    depth: Literal["lite", "medium", "deep"] = Field("deep", description="lite=快速(10评委) / medium=标准(51) / deep=深度(66+多空辩论)")
    use_ai: bool = Field(True, description="是否调用大模型补全研判叙述（维度评语/多空辩论/核心结论/风险/买入区间）。关闭则走离线模板，响应更快。")


class AnalyzeResponse(BaseModel):
    # 引擎返回结构较复杂，这里做宽松声明（实际为 dict）
    meta: dict[str, Any] = Field(default_factory=dict)
    overall_score: float = 0.0
    verdict: str = ""
    dimensions: list[dict[str, Any]] = Field(default_factory=list)
    valuation: dict[str, Any] = Field(default_factory=dict)
    panel_summary: dict[str, Any] = Field(default_factory=dict)
    panel_by_group: list[dict[str, Any]] = Field(default_factory=list)
    panel: list[dict[str, Any]] = Field(default_factory=list)
    trap: dict[str, Any] = Field(default_factory=dict)
    great_divide: dict[str, Any] = Field(default_factory=dict)
    depth: str = "deep"

    model_config = {"extra": "allow"}
