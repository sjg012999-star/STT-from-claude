"""STT provider 팩토리."""

from __future__ import annotations

from .base import STTProvider
from .mock_provider import MockSTTProvider

_REGISTRY = {"mock", "openai"}


def get_provider(name: str, **kwargs) -> STTProvider:
    """이름으로 provider 를 생성한다.

    'openai' 는 키·SDK 가 필요하므로 lazy import (mock 만 쓰는 환경에서
    openai 미설치여도 동작하도록).
    """
    name = (name or "mock").lower()
    if name == "mock":
        return MockSTTProvider()
    if name == "openai":
        from .openai_provider import OpenAISTTProvider

        return OpenAISTTProvider(**kwargs)
    raise ValueError(
        f"알 수 없는 STT provider: '{name}'. 사용 가능: {', '.join(sorted(_REGISTRY))}"
    )


__all__ = ["STTProvider", "MockSTTProvider", "get_provider"]
