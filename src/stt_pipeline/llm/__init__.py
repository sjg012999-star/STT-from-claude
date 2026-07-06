"""LLM 클라이언트 팩토리."""

from __future__ import annotations

import os

from .base import LLMClient
from .mock_client import MockLLMClient


def get_llm_client(kind: str | None = None) -> LLMClient:
    """LLM 클라이언트를 생성한다.

    kind:
      - "mock"      → MockLLMClient (키 불필요)
      - "anthropic" → AnthropicClient (ANTHROPIC_API_KEY 필요)
      - None/"auto" → ANTHROPIC_API_KEY 가 있으면 anthropic, 없으면 mock
    """
    kind = (kind or "auto").lower()
    if kind == "auto":
        kind = "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "mock"
    if kind == "mock":
        return MockLLMClient()
    if kind == "anthropic":
        from .anthropic_client import AnthropicClient

        return AnthropicClient()
    raise ValueError(f"알 수 없는 LLM 종류: '{kind}'. 사용 가능: mock, anthropic, auto")


__all__ = ["LLMClient", "MockLLMClient", "get_llm_client"]
