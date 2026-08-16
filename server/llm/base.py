"""LLM 抽象层 · 让分析终端的"判断层"可被真实大模型驱动。

设计原则（企业级）：
  - 不强制依赖任何第三方 SDK，DeepSeek 走标准 OpenAI 兼容的 chat/completions，用 stdlib urllib 直连。
  - 无 API key 时自动降级到 TemplateProvider（确定性、离线、可单测），应用永不因缺 key 而崩溃。
  - 所有 Provider 产出**同一份 schema**，前端只认一份结构，与底层是否联网无关。
"""

from __future__ import annotations

import abc
from typing import Any


class LLMProvider(abc.ABC):
    """所有大模型提供方的统一接口。"""

    name: str = "base"
    # 是否真的联网（False = 离线确定性回退）
    online: bool = False

    @abc.abstractmethod
    def complete(
        self, system: str, user: str, *, max_tokens: int = 2000, temperature: float = 0.3, timeout: float = 60
    ) -> str:
        """返回模型生成的纯文本。"""
        raise NotImplementedError

    def is_available(self) -> bool:
        return True

    def meta(self) -> dict[str, Any]:
        return {"name": self.name, "online": self.online}
