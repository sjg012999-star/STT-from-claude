"""OpenAI STT provider (gpt-4o-transcribe / whisper-1).

키가 있을 때만 동작한다 (OPENAI_API_KEY). openai SDK 미설치/키 부재 시
명확한 에러를 던진다. 25MB 초과 파일은 무음 경계 분할 업로드가 필요한데,
Phase 1 에서는 **최소 골격 + TODO** 로 남긴다.
"""

from __future__ import annotations

import os
from pathlib import Path

from ..models import Segment
from .base import STTProvider

# OpenAI 업로드 크기 상한 (25MB).
_MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class OpenAISTTProvider(STTProvider):
    name = "openai"

    def __init__(self, model: str = "gpt-4o-transcribe") -> None:
        self.model = model
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY 환경변수가 없습니다. openai provider 는 키가 필요합니다.\n"
                "키 없이 파이프라인을 검증하려면 --provider mock 를 사용하세요."
            )
        try:
            from openai import OpenAI  # lazy import
        except ImportError as e:  # pragma: no cover - 설치 환경 의존
            raise RuntimeError(
                "openai 패키지가 설치되어 있지 않습니다. `pip install 'stt-pipeline[openai]'`"
            ) from e
        self._client = OpenAI(api_key=api_key)

    def transcribe(
        self,
        audio_path: str | Path,
        glossary_terms: list[str] | None = None,
    ) -> list[Segment]:
        audio_path = Path(audio_path)
        prompt = self._build_prompt(glossary_terms or [])

        if audio_path.stat().st_size > _MAX_UPLOAD_BYTES:
            # TODO(phase1): 무음 경계 기준 분할 업로드 후 세그먼트 병합/오프셋 보정.
            #   PLAN.md §3-① — 문장 중간 절단 방지. 지금은 골격만 두고 미구현 안내.
            raise NotImplementedError(
                f"파일이 25MB를 초과합니다 ({audio_path.stat().st_size} bytes). "
                "무음 경계 분할 업로드는 아직 미구현입니다 (TODO)."
            )

        with audio_path.open("rb") as f:
            resp = self._client.audio.transcriptions.create(
                model=self.model,
                file=f,
                response_format="verbose_json",
                prompt=prompt or None,
            )
        return self._parse_response(resp)

    def _build_prompt(self, glossary_terms: list[str]) -> str:
        """용어 주입 — gpt-4o-transcribe 는 prompt 로 어휘 힌트를 받는다."""
        if not glossary_terms:
            return ""
        return "다음 전문용어·고유명사가 등장합니다: " + ", ".join(glossary_terms)

    def _parse_response(self, resp) -> list[Segment]:
        segments: list[Segment] = []
        raw_segments = getattr(resp, "segments", None) or []
        for i, s in enumerate(raw_segments):
            get = s.get if isinstance(s, dict) else lambda k, d=None: getattr(s, k, d)
            segments.append(
                Segment(
                    id=f"seg_{i:03d}",
                    start=float(get("start", 0.0) or 0.0),
                    end=float(get("end", 0.0) or 0.0),
                    text=str(get("text", "") or "").strip(),
                    confidence=None,  # verbose_json 은 단어 확률만 제공 — 세그먼트 신뢰도 근사 생략
                )
            )
        if not segments:
            # segments 미제공 응답(예: 일부 모델) → 전체를 단일 세그먼트로.
            text = str(getattr(resp, "text", "") or "").strip()
            segments.append(Segment(id="seg_000", start=0.0, end=0.0, text=text))
        return segments
