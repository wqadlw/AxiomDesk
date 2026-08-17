"""LLM 工厂 · 单例 + 自动降级。

优先级：配置了 AXIOM_DEEPSEEK_API_KEY → DeepSeekProvider（真实大模型推理）；
否则 → TemplateProvider（离线确定性回退）。
两个 Provider 产出同一份 schema，调用方无需关心底层是谁。
"""

from __future__ import annotations

import os

from .base import LLMProvider
from .deepseek import DeepSeekProvider
from .template import TemplateProvider

_LLM: LLMProvider | None = None


def get_llm(force_reload: bool = False) -> LLMProvider:
    global _LLM
    if _LLM is not None and not force_reload:
        return _LLM
    # 配置页的 llm 设置优先于默认值，但环境变量可覆盖（便于容器注入密钥）
    llm_cfg = {}
    try:
        from ..config_store import get_config

        llm_cfg = get_config().get("llm", {})
    except Exception:
        llm_cfg = {}
    ds = DeepSeekProvider(
        api_key=os.environ.get("AXIOM_DEEPSEEK_API_KEY") or llm_cfg.get("api_key", ""),
        base_url=os.environ.get("AXIOM_DEEPSEEK_BASE_URL") or llm_cfg.get("base_url", ""),
        model=os.environ.get("AXIOM_DEEPSEEK_MODEL") or llm_cfg.get("model", ""),
    )
    if ds.is_available():
        _LLM = ds
    else:
        _LLM = TemplateProvider()
    return _LLM


def set_llm(provider: LLMProvider) -> None:
    """测试或特殊场景注入指定 Provider。"""
    global _LLM
    _LLM = provider


def reload_llm() -> None:
    """配置变更（如填入 DeepSeek key）后重建 LLM 实例。"""
    global _LLM
    _LLM = None
