"""Mock STT provider — API 키 불필요. 픽스처 세그먼트를 반환한다.

오디오 내용과 무관하게 고정된 학회 세미나 전사 샘플을 돌려준다.
이 샘플에는 교정 계층이 복원해야 할 **의도적 오인식**이 포함되어 있어
mock LLM 교정과 결합하면 파이프라인 전체를 end-to-end 로 검증할 수 있다.

픽스처는 STT_MOCK_FIXTURE 환경변수(JSON 파일 경로)로 override 가능.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..models import Segment
from .base import STTProvider

# 억양 있는 학회 발표를 흉내낸 원시 전사 (한영 혼용 + 오인식 포함).
# "크리스퍼 캐스나인", "아이엘 써틴 알에이 투", "스몰리" 는 교정 대상.
_DEFAULT_FIXTURE: list[dict] = [
    {
        "id": "seg_000",
        "start": 0.0,
        "end": 4.2,
        "text": "안녕하세요 여러분, 오늘 발표를 맡은 발표자입니다.",
        "confidence": 0.97,
    },
    {
        "id": "seg_001",
        "start": 4.2,
        "end": 10.8,
        "text": "이 실험에서 저희는 크리스퍼 캐스나인을 사용해서 유전자를 편집했습니다.",
        "confidence": 0.71,
    },
    {
        "id": "seg_002",
        "start": 10.8,
        "end": 17.5,
        "text": "특히 아이엘 써틴 알에이 투 양성 섬유아세포가 염증 조직에서 증가했습니다.",
        "confidence": 0.64,
    },
    {
        "id": "seg_003",
        "start": 17.5,
        "end": 23.0,
        "text": "이 결과는 스몰리 연구팀의 2019년 논문과 일치합니다.",
        "confidence": 0.8,
    },
    {
        "id": "seg_004",
        "start": 23.0,
        "end": 27.4,
        "text": "질문 있으시면 말씀해 주세요. 감사합니다.",
        "confidence": 0.95,
    },
]


class MockSTTProvider(STTProvider):
    name = "mock"

    def transcribe(
        self,
        audio_path: str | Path,
        glossary_terms: list[str] | None = None,
    ) -> list[Segment]:
        fixture_path = os.environ.get("STT_MOCK_FIXTURE")
        if fixture_path:
            with Path(fixture_path).open("r", encoding="utf-8") as f:
                raw = json.load(f)
        else:
            raw = _DEFAULT_FIXTURE
        return [Segment.from_dict(d) for d in raw]
