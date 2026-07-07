from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from stt_pipeline.transcript import TranscriptResult, TranscriptSegment


PROFILE_DEFAULTS = {
    "seminar": "gpt-4o",
    "lecture": "gpt-4o",
    "meeting": "diarize",
}

PROVIDER_MODELS = {
    "gpt-4o": "gpt-4o-transcribe",
    "gpt-4o-mini": "gpt-4o-mini-transcribe",
    "whisper-1": "whisper-1",
    "diarize": "gpt-4o-transcribe-diarize",
}


@dataclass(frozen=True)
class OpenAiSttRequest:
    provider: str
    profile: str
    model: str
    response_format: str
    prompt: str | None = None
    chunking_strategy: str | None = None


def default_provider_for_profile(profile: str) -> str:
    return PROFILE_DEFAULTS.get(profile, "gpt-4o")


def build_openai_stt_request(
    *,
    provider: str,
    profile: str,
    prompt_terms: Iterable[str] = (),
) -> OpenAiSttRequest:
    if provider not in PROVIDER_MODELS:
        supported = ", ".join(sorted(PROVIDER_MODELS))
        raise ValueError(f"unsupported STT provider '{provider}'. Supported: {supported}")

    if provider == "diarize":
        return OpenAiSttRequest(
            provider=provider,
            profile=profile,
            model=PROVIDER_MODELS[provider],
            response_format="diarized_json",
            chunking_strategy="auto",
        )

    return OpenAiSttRequest(
        provider=provider,
        profile=profile,
        model=PROVIDER_MODELS[provider],
        response_format="json",
        prompt=(
            _build_prompt(prompt_terms)
            if provider in {"gpt-4o", "gpt-4o-mini"}
            else None
        ),
    )


class OpenAiSttTranscriber:
    def __init__(self, client: Any | None = None):
        self._client = client

    def transcribe(
        self,
        audio_path: str | Path,
        *,
        provider: str | None = None,
        profile: str = "seminar",
        prompt_terms: Iterable[str] = (),
    ) -> TranscriptResult:
        selected_provider = provider or default_provider_for_profile(profile)
        request = build_openai_stt_request(
            provider=selected_provider,
            profile=profile,
            prompt_terms=prompt_terms,
        )
        client = self._client or _build_default_openai_client()

        with Path(audio_path).open("rb") as audio_file:
            kwargs: dict[str, Any] = {
                "model": request.model,
                "file": audio_file,
                "response_format": request.response_format,
            }
            if request.prompt:
                kwargs["prompt"] = request.prompt
            if request.chunking_strategy:
                kwargs["chunking_strategy"] = request.chunking_strategy

            response = client.audio.transcriptions.create(**kwargs)

        return _normalize_response(
            response,
            provider=request.provider,
            profile=request.profile,
            model=request.model,
        )


def _build_prompt(prompt_terms: Iterable[str]) -> str | None:
    cleaned = (_clean_term(term) for term in prompt_terms)
    terms = tuple(_dedupe(term for term in cleaned if term))
    if not terms:
        return None
    return "Relevant terms that may appear in the audio: " + ", ".join(terms)


def _normalize_response(
    response: Any,
    *,
    provider: str,
    profile: str,
    model: str,
) -> TranscriptResult:
    text = str(_get_value(response, "text", "") or "")
    raw_segments = _get_value(response, "segments", None) or []
    segments = tuple(
        _normalize_segment(index, segment) for index, segment in enumerate(raw_segments)
    )
    if not segments:
        segments = (
            TranscriptSegment(
                segment_id="seg_001",
                text=text,
            ),
        )

    return TranscriptResult(
        provider=provider,
        model=model,
        profile=profile,
        text=text,
        segments=segments,
        usage_seconds=_optional_float(_get_value(response, "duration", None)),
    )


def _normalize_segment(index: int, segment: Any) -> TranscriptSegment:
    raw_id = _get_value(segment, "id", index)
    if isinstance(raw_id, str) and raw_id.startswith("seg_"):
        segment_id = raw_id
    else:
        segment_id = (
            f"seg_{int(raw_id):03d}"
            if isinstance(raw_id, int)
            else f"seg_{index:03d}"
        )

    return TranscriptSegment(
        segment_id=segment_id,
        text=str(_get_value(segment, "text", "") or ""),
        start_seconds=_optional_float(_get_value(segment, "start", None)),
        end_seconds=_optional_float(_get_value(segment, "end", None)),
        speaker=_optional_str(
            _get_value(segment, "speaker", None)
            or _get_value(segment, "speaker_label", None)
        ),
    )


def _get_value(source: Any, key: str, default: Any) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _clean_term(value: str) -> str:
    return " ".join(str(value).split())


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    seen = set()
    deduped = []
    for value in values:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            deduped.append(value)
    return tuple(deduped)


def _build_default_openai_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Install the openai package to use live STT transcription") from exc
    return OpenAI()
