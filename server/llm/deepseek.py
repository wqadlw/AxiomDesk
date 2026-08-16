"""DeepSeek Provider · OpenAI 兼容 chat/completions，纯 stdlib 实现（零外部依赖）。

官方接入要点（2026）：
  - base_url 默认 https://api.deepseek.com  （已含 /v1 路由，无需再拼 /v1）
  - 模型：deepseek-chat（V3，默认，性价比高）/ deepseek-reasoner（R1，带推理链）
  - 鉴权：Authorization: Bearer <key>
  - 用 response_format={"type":"json_object"} 强制 JSON 输出，便于结构化解析
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from .base import LLMProvider


class DeepSeekError(RuntimeError):
    pass


class DeepSeekProvider(LLMProvider):
    name = "deepseek"
    online = True

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ):
        self.api_key = (api_key or os.environ.get("UZI_DEEPSEEK_API_KEY") or "").strip()
        self.base_url = (base_url or os.environ.get("UZI_DEEPSEEK_BASE_URL") or "https://api.deepseek.com").rstrip("/")
        self.model = (model or os.environ.get("UZI_DEEPSEEK_MODEL") or "deepseek-chat").strip()
        self.timeout = float(timeout if timeout is not None else os.environ.get("UZI_DEEPSEEK_TIMEOUT", "60"))

    def is_available(self) -> bool:
        return bool(self.api_key)

    def complete(
        self, system: str, user: str, *, max_tokens: int = 2000, temperature: float = 0.3, timeout: float | None = None
    ) -> str:
        if not self.api_key:
            raise DeepSeekError("未配置 UZI_DEEPSEEK_API_KEY，无法调用 DeepSeek")

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")
            except Exception:
                pass
            raise DeepSeekError(f"DeepSeek HTTP {e.code}: {body[:500]}") from e
        except urllib.error.URLError as e:
            raise DeepSeekError(f"DeepSeek 网络不可达: {e.reason}") from e

        try:
            obj = json.loads(raw)
            return obj["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as e:
            raise DeepSeekError(f"DeepSeek 响应解析失败: {raw[:300]}") from e

    def meta(self) -> dict[str, Any]:
        return {"name": self.name, "online": True, "model": self.model, "base_url": self.base_url}
