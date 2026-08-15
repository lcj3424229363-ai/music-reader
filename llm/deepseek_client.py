"""DeepSeek API 客户端。

DeepSeek API 兼容 OpenAI 协议，用 chat/completions 端点。

API: https://api.deepseek.com/v1/chat/completions
参考: https://platform.deepseek.com/api-docs/

设计：
- 同步调用（server 是 FastAPI 同步端点）
- 30s 默认超时
- 自动 retry 一次（网络抖动）
- 所有错误抛 DeepSeekError，前端不会看到
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

# 可选 dotenv 支持（项目里已装，但不强制）
try:
    from dotenv import load_dotenv  # type: ignore

    _ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH)
except ImportError:  # pragma: no cover
    pass


class DeepSeekError(Exception):
    """DeepSeek 调用失败的统一错误类型。"""


@dataclass
class DeepSeekConfig:
    """DeepSeek 客户端配置，从 .env 读。"""

    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    timeout_sec: int = 30
    max_tokens: int = 1500
    temperature: float = 0.4

    @classmethod
    def from_env(cls) -> "DeepSeekConfig":
        api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise DeepSeekError("DEEPSEEK_API_KEY not set in environment")
        return cls(
            api_key=api_key,
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip(),
            model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat").strip(),
            timeout_sec=int(os.environ.get("LLM_TIMEOUT_SEC", "30")),
            max_tokens=int(os.environ.get("LLM_MAX_TOKENS", "1500")),
            temperature=float(os.environ.get("LLM_TEMPERATURE", "0.4")),
        )

    @property
    def enabled(self) -> bool:
        """环境变量 LLM_ENABLED 关闭就当 disabled。"""
        flag = os.environ.get("LLM_ENABLED", "true").strip().lower()
        return flag in ("1", "true", "yes", "on")


class DeepSeekClient:
    """DeepSeek Chat Completions 客户端。"""

    def __init__(self, config: DeepSeekConfig | None = None) -> None:
        self.config = config or DeepSeekConfig.from_env()
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            }
        )

    @property
    def url(self) -> str:
        return f"{self.config.base_url.rstrip('/')}/v1/chat/completions"

    def chat(
        self,
        system: str,
        user: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """发一次 chat completion 请求，返回 assistant 文本。

        自动 retry 一次（429/5xx/网络错误）。
        """
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature if temperature is not None else self.config.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.config.max_tokens,
            "stream": False,
        }
        last_error: Exception | None = None
        for attempt in range(2):  # 最多 2 次
            try:
                resp = self._session.post(
                    self.url,
                    data=json.dumps(payload),
                    timeout=self.config.timeout_sec,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices") or []
                    if not choices:
                        raise DeepSeekError("empty choices in response")
                    content = choices[0].get("message", {}).get("content", "")
                    if not content:
                        raise DeepSeekError("empty content in response")
                    return content
                # 4xx 非 429 直接抛（不要 retry bad request）
                if 400 <= resp.status_code < 500 and resp.status_code != 429:
                    raise DeepSeekError(
                        f"deepseek http {resp.status_code}: {resp.text[:300]}"
                    )
                last_error = DeepSeekError(f"deepseek http {resp.status_code}: {resp.text[:200]}")
            except requests.RequestException as e:
                last_error = DeepSeekError(f"deepseek network error: {e}")
            time.sleep(0.5 * (attempt + 1))  # 0.5s, 1s
        raise DeepSeekError(f"deepseek call failed after retries: {last_error}")
