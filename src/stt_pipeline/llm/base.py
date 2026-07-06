"""LLM 클라이언트 인터페이스 (교정·요약·비전).

Claude API 호출을 추상화한다. 실제 구현(AnthropicClient)은 키가 있을 때만,
테스트/오프라인은 MockLLMClient 로 대체 가능하게 한다 (CLAUDE.md 구현 규칙).

교정 계약(correct_chunk)은 structured outputs 스키마를 따른다:
  {
    "corrected_segments": [{"id": ..., "text": ...}, ...],
    "corrections": [{"segment_id", "original", "corrected", "reason", "confidence"}, ...]
  }
반환된 corrected_segments 는 그대로 신뢰되지 않는다 — 상위(correct.py)의
difflib 검증을 반드시 통과해야 본문에 반영된다.
"""

from __future__ import annotations

import abc

from ..models import Segment


class LLMClient(abc.ABC):
    @abc.abstractmethod
    def correct_chunk(
        self,
        segments: list[Segment],
        glossary_terms: list[str],
        aliases: dict[str, str] | None = None,
    ) -> dict:
        """청크(세그먼트 묶음)를 교정하고 structured 결과를 반환한다."""
        raise NotImplementedError

    @abc.abstractmethod
    def summarize(self, transcript_text: str, profile: dict) -> str:
        """교정된 전사 전체를 프로필 템플릿으로 요약(markdown)한다."""
        raise NotImplementedError

    @abc.abstractmethod
    def describe_slide_image(self, image_path: str) -> dict:
        """슬라이드 사진을 비전으로 읽어 3레이어 추출 결과를 반환한다.

        반환: {"raw_extract", "glossary_terms", "slide_only_facts"}
        (🔍 enrichment 는 Phase 3.)
        """
        raise NotImplementedError
