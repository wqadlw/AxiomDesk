# -*- coding: utf-8 -*-
"""LLM 抽象层入口。"""
from __future__ import annotations

from .base import LLMProvider
from .deepseek import DeepSeekError, DeepSeekProvider
from .factory import get_llm, set_llm
from .template import TemplateProvider

__all__ = [
    "LLMProvider",
    "DeepSeekProvider",
    "DeepSeekError",
    "TemplateProvider",
    "get_llm",
    "set_llm",
]
