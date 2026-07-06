"""④ 정리·요약 — 프로필별 템플릿 요약 (Claude, mock 가능).

교정 완료된 전사 전체를 입력으로 프로필 템플릿 요약을 생성한다.
요약은 🔍(AI 해설)가 아니라 전사 사실의 재구성이지만, 출력에서는 전사 본문과
별도 섹션으로만 배치된다 (report.py). mock LLM 으로도 동작한다.
"""

from __future__ import annotations

from .llm.base import LLMClient
from .models import Segment


def segments_to_text(segments: list[Segment]) -> str:
    """요약 입력용 평문 전사(타임스탬프 포함)."""
    lines = []
    for s in segments:
        ts = _fmt_ts(s.start)
        spk = f"{s.speaker}: " if s.speaker else ""
        lines.append(f"[{ts}] {spk}{s.text}")
    return "\n".join(lines)


def summarize(segments: list[Segment], profile: dict, llm: LLMClient) -> str:
    transcript_text = segments_to_text(segments)
    return llm.summarize(transcript_text, profile)


def _fmt_ts(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
