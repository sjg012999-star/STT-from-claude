"""Mock LLM 클라이언트 — 키 불필요. 결정론적으로 동작한다.

교정: 내장 phonetic 맵 + 용어집 alias 로 명백한 오인식만 복원하고,
모든 수정을 corrections 에 기록한다(= diff 검증을 통과하도록 well-behaved).
요약: 프로필 섹션을 채운 간단한 markdown 템플릿.
비전: 실제 OCR 없이 "미수행" 안내만 반환(내용 지어내지 않음 — 불변원칙 3).
"""

from __future__ import annotations

from ..models import Segment
from .base import LLMClient

# 내장 오인식 → 정식 표기 (원시 전사 mock 픽스처와 짝을 이룬다).
_BUILTIN_PHONETIC: dict[str, tuple[str, str, str]] = {
    # wrong: (right, reason, confidence)
    "크리스퍼 캐스나인": ("CRISPR-Cas9", "음성 오인식 — 유전자 편집 도구 명칭", "high"),
    "아이엘 써틴 알에이 투": ("IL13RA2", "음성 오인식 — 유전자 마커명", "high"),
    "스몰리": ("Smillie", "고유명사 — 저자명", "low"),
}


class MockLLMClient(LLMClient):
    def correct_chunk(
        self,
        segments: list[Segment],
        glossary_terms: list[str],
        aliases: dict[str, str] | None = None,
    ) -> dict:
        # alias(용어집) + 내장 맵을 합쳐 교정 규칙을 만든다.
        rules: dict[str, tuple[str, str, str]] = dict(_BUILTIN_PHONETIC)
        for wrong, right in (aliases or {}).items():
            rules[wrong] = (right, "용어집 alias 기반 교정", "high")

        corrected_segments: list[dict] = []
        corrections: list[dict] = []
        for seg in segments:
            text = seg.text
            for wrong, (right, reason, conf) in rules.items():
                if wrong in text:
                    text = text.replace(wrong, right)
                    corrections.append(
                        {
                            "segment_id": seg.id,
                            "original": wrong,
                            "corrected": right,
                            "reason": reason,
                            "confidence": conf,
                        }
                    )
            corrected_segments.append({"id": seg.id, "text": text})
        return {"corrected_segments": corrected_segments, "corrections": corrections}

    def summarize(self, transcript_text: str, profile: dict) -> str:
        summary_cfg = (profile or {}).get("summary", {}) or {}
        sections = summary_cfg.get("sections") or ["요약"]
        lines = ["## 요약 (mock)", ""]
        # mock 은 실제 이해를 하지 않으므로, 각 섹션에 안내 문구만 채운다.
        for s in sections:
            lines.append(f"### {s}")
            lines.append(
                "_(mock LLM: 실제 요약은 ANTHROPIC_API_KEY 설정 후 anthropic 클라이언트로 생성됩니다.)_"
            )
            lines.append("")
        preview = transcript_text.strip().splitlines()
        if preview:
            lines.append("전사 미리보기(첫 줄): " + preview[0][:200])
        return "\n".join(lines).rstrip() + "\n"

    def describe_slide_image(self, image_path: str) -> dict:
        # 불변원칙 3: 근거 없이 내용을 생성하지 않는다.
        return {
            "raw_extract": "",
            "glossary_terms": [],
            "slide_only_facts": [],
            "note": f"mock 비전: 슬라이드 판독 미수행 ({image_path}). "
            "실제 추출은 ANTHROPIC_API_KEY 필요.",
        }
