"""Anthropic(Claude) LLM 클라이언트 — 키가 있을 때만 동작.

모델: claude-opus-4-8 (CLAUDE.md 모델 라우팅). structured outputs + prompt
caching 을 지향한다. Phase 1 에서는 교정/요약 호출의 **기능적 골격**을 구현하고,
prompt caching / Batch API 최적화는 후속(Phase 2) TODO 로 둔다.

API 키·SDK 부재 시 명확한 에러. 키 없이 검증하려면 MockLLMClient 를 쓴다.
"""

from __future__ import annotations

import json
import os

from ..models import Segment
from .base import LLMClient

MODEL = "claude-opus-4-8"

# 교정 시스템 프롬프트 (고정 → prompt caching 대상).
_CORRECTION_SYSTEM = """당신은 학술 발표 음성 전사의 오인식을 교정하는 도구입니다.
규칙:
- 화자의 말투·어순·문체는 유지한다 (다듬기 금지, 오인식 복원만).
- 명백한 음성 오인식만 수정: 전문용어, 고유명사, 숫자/단위, 한영 혼용 표기.
- 확신이 없으면 원문을 유지하고 confidence 를 low 로 둔다.
- 모든 수정은 corrections 배열에 반드시 기록한다. 기록 없는 수정은 무효 처리된다.
반드시 아래 JSON 스키마로만 출력한다:
{"corrected_segments":[{"id":str,"text":str}],
 "corrections":[{"segment_id":str,"original":str,"corrected":str,"reason":str,"confidence":"high|medium|low"}]}
"""


class AnthropicClient(LLMClient):
    def __init__(self, model: str = MODEL) -> None:
        self.model = model
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY 환경변수가 없습니다. 교정·요약에는 키가 필요합니다.\n"
                "키 없이 검증하려면 mock LLM 을 사용하세요 (cli 는 키가 없으면 자동으로 mock)."
            )
        try:
            import anthropic  # lazy import
        except ImportError as e:  # pragma: no cover - 설치 환경 의존
            raise RuntimeError(
                "anthropic 패키지가 없습니다. `pip install 'stt-pipeline[anthropic]'`"
            ) from e
        self._client = anthropic.Anthropic(api_key=api_key)

    def correct_chunk(
        self,
        segments: list[Segment],
        glossary_terms: list[str],
        aliases: dict[str, str] | None = None,
    ) -> dict:
        glossary_block = ""
        if glossary_terms:
            glossary_block = "\n용어집(정식 표기): " + ", ".join(glossary_terms)
        if aliases:
            pairs = "; ".join(f"{k}→{v}" for k, v in aliases.items())
            glossary_block += "\n오인식 매핑: " + pairs
        payload = [{"id": s.id, "text": s.text} for s in segments]
        user = (
            "다음 세그먼트의 오인식을 교정하세요."
            + glossary_block
            + "\n세그먼트:\n"
            + json.dumps(payload, ensure_ascii=False)
        )
        # NOTE(phase2): system 블록에 cache_control 적용(prompt caching), Batch API 전환.
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=_CORRECTION_SYSTEM,
            messages=[{"role": "user", "content": user}],
        )
        return _parse_json_block(_text_of(resp))

    def summarize(self, transcript_text: str, profile: dict) -> str:
        summary_cfg = (profile or {}).get("summary", {}) or {}
        sections = summary_cfg.get("sections") or ["요약"]
        system = (
            "당신은 학술 발표 전사를 정리하는 요약 도구입니다. "
            "제공된 전사 사실에만 근거하고, 없는 내용을 지어내지 마세요. "
            "다음 섹션 구조의 markdown 으로 작성하세요: " + ", ".join(sections)
        )
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": transcript_text}],
        )
        return _text_of(resp)

    def describe_slide_image(self, image_path: str) -> dict:
        # TODO(phase1+): 이미지 base64 인코딩 + 비전 메시지. 3레이어(🔤/📊/🔍) 스키마로 반환.
        #   docs/knowledge_pack_example.md 참고. 지금은 인터페이스만 열어둔다.
        raise NotImplementedError(
            "Claude 비전 슬라이드 추출은 아직 미구현입니다 (TODO). "
            "Phase 1 에서는 PPT 텍스트 추출을 우선 사용하세요."
        )


def _text_of(resp) -> str:
    parts = []
    for block in getattr(resp, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "".join(parts)


def _parse_json_block(text: str) -> dict:
    text = text.strip()
    # 코드펜스 제거
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())
