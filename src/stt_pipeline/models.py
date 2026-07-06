"""핵심 데이터 모델.

전사(Segment) 레이어와 교정 기록(Correction) 레이어는 의도적으로 분리되어 있다.
전사 본문은 불가침이며, 교정/보강은 별도 구조로만 표현한다 (설계 불변 원칙 1·4).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Segment:
    """전사 세그먼트 — 🎤 사실 레이어. STT provider가 반환하는 최소 단위."""

    id: str
    start: float  # 초
    end: float  # 초
    text: str
    confidence: Optional[float] = None  # 0.0~1.0, None이면 미제공
    speaker: Optional[str] = None  # 화자 라벨 (diarization, Phase 2)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Segment":
        return cls(
            id=str(d["id"]),
            start=float(d.get("start", 0.0)),
            end=float(d.get("end", 0.0)),
            text=str(d.get("text", "")),
            confidence=d.get("confidence"),
            speaker=d.get("speaker"),
        )


@dataclass
class Correction:
    """교정 기록 — 전사와 분리된 감사(audit) 레이어.

    diff 검증을 통과한(=corrections에 근거가 있는) 수정만 본문에 반영된다.
    rolled_back=True 는 무단 수정으로 판정되어 원문으로 되돌린 항목.
    """

    segment_id: str
    original: str
    corrected: str
    reason: str = ""
    confidence: str = "medium"  # high | medium | low
    rolled_back: bool = False  # diff 검증 실패 → 원문 롤백됨
    uncertain: bool = False  # confidence == low → ⚠️ 사람 확인 유도

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SlideFact:
    """Knowledge Pack 슬라이드 1장의 3레이어 추출 결과.

    docs/knowledge_pack_example.md 스펙 준수:
      🔤 glossary_terms   → STT/교정 주입 (Phase 1)
      📊 slide_only_facts → 슬라이드 전용 사실 (발화 안 해도 기록)
      🔍 enrichment       → 추가 조사·보강 대상 (Phase 3, 출처 필수)
    이 세 레이어는 절대 병합하지 않는다.
    """

    source: str  # 파일명/슬라이드 식별자
    raw_extract: str = ""  # OCR/비전 원시 추출 텍스트
    glossary_terms: list[str] = field(default_factory=list)  # 🔤
    slide_only_facts: list[str] = field(default_factory=list)  # 📊
    enrichment_targets: list[dict] = field(default_factory=list)  # 🔍 (Phase 3)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class KnowledgePack:
    """자료 추출 산출물. glossary_terms 는 파이프라인 전체에 주입된다."""

    glossary_terms: list[str] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)  # 오인식 발음 → 정식 표기
    slide_facts: list[SlideFact] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "glossary_terms": self.glossary_terms,
            "aliases": self.aliases,
            "slide_facts": [s.to_dict() for s in self.slide_facts],
        }
