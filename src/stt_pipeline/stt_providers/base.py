"""STT 어댑터 인터페이스.

계약: transcribe(audio_path, glossary_terms) -> list[Segment]
Segment = {id, start, end, text, confidence}

API를 교체 가능하게 하는 어댑터 패턴 (PLAN.md §2-②, CLAUDE.md 구현 규칙).
glossary_terms 는 Knowledge Pack 에서 추출한 용어로, 각 provider 가
자신의 메커니즘(prompt / keyword boosting / custom vocabulary)으로 주입한다.
"""

from __future__ import annotations

import abc
from pathlib import Path

from ..models import Segment


class STTProvider(abc.ABC):
    """모든 STT provider 가 구현해야 하는 최소 인터페이스."""

    name: str = "base"

    @abc.abstractmethod
    def transcribe(
        self,
        audio_path: str | Path,
        glossary_terms: list[str] | None = None,
    ) -> list[Segment]:
        """오디오를 전사해 세그먼트 목록을 반환한다.

        Args:
            audio_path: 전처리된(또는 원본) 오디오 경로.
            glossary_terms: STT 인식률 향상을 위해 주입할 용어 목록.

        Returns:
            시간순 정렬된 Segment 리스트.
        """
        raise NotImplementedError
