from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

from stt_pipeline.transcript import TranscriptResult, TranscriptSegment


DEFAULT_GEMINI_AUDIO_MODEL = "gemini-3.5-flash"

GEMINI_TRANSCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "start_seconds": {"type": "number"},
                    "end_seconds": {"type": "number"},
                    "speaker": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["id", "start_seconds", "end_seconds", "text"],
            },
        },
    },
    "required": ["text", "segments"],
}


class GeminiAudioTranscriber:
    def __init__(self, client: Any | None = None, *, model: str | None = None):
        self._client = client
        self._model = model or os.environ.get(
            "GEMINI_AUDIO_MODEL",
            DEFAULT_GEMINI_AUDIO_MODEL,
        )

    def transcribe(
        self,
        audio_path: str | Path,
        *,
        provider: str | None = None,
        profile: str = "seminar",
        prompt_terms: Iterable[str] = (),
    ) -> TranscriptResult:
        if provider not in {None, "gemini-audio"}:
            raise ValueError(f"GeminiAudioTranscriber only supports gemini-audio, got {provider}")

        client = self._client or _build_default_gemini_client()
        uploaded = client.files.upload(file=str(Path(audio_path)))
        try:
            response = client.models.generate_content(
                model=self._model,
                contents=[uploaded, _build_transcription_prompt(profile, prompt_terms)],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": GEMINI_TRANSCRIPT_SCHEMA,
                },
            )
            payload = _parse_response_payload(response)
            return _normalize_gemini_payload(
                payload,
                profile=profile,
                model=self._model,
            )
        finally:
            _delete_uploaded_file(client, uploaded)


def _build_transcription_prompt(profile: str, prompt_terms: Iterable[str]) -> str:
    terms = _dedupe_terms(prompt_terms)
    lines = [
        "Transcribe the complete audio faithfully and verbatim.",
        "Do not summarize, correct, translate, infer missing speech, or add facts.",
        "Preserve the spoken language, numbers, units, acronyms, and technical names.",
        "Split the transcript into chronological segments with numeric timestamps in seconds.",
        "Use stable speaker labels when voices are distinguishable; omit the speaker when uncertain.",
        f"Recording profile: {profile}.",
    ]
    if terms:
        lines.append(
            "Relevant terms that may appear in the audio: " + ", ".join(terms)
        )
    return "\n".join(lines)


def _parse_response_payload(response: Any) -> dict[str, Any]:
    text = str(getattr(response, "text", "") or "").strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```")
        text = text.removesuffix("```").strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Gemini audio response was not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Gemini audio response must be a JSON object")
    return payload


def _normalize_gemini_payload(
    payload: dict[str, Any],
    *,
    profile: str,
    model: str,
) -> TranscriptResult:
    text = str(payload.get("text") or "").strip()
    raw_segments = payload.get("segments") or []
    segments = tuple(
        _normalize_segment(index, segment)
        for index, segment in enumerate(raw_segments)
        if isinstance(segment, dict) and str(segment.get("text") or "").strip()
    )
    if not text and segments:
        text = " ".join(segment.text for segment in segments)
    if not text:
        raise ValueError("Gemini audio response did not contain transcript text")
    if not segments:
        segments = (TranscriptSegment(segment_id="seg_000", text=text),)

    usage_seconds = max(
        (segment.end_seconds or 0.0 for segment in segments),
        default=0.0,
    )
    return TranscriptResult(
        provider="gemini-audio",
        model=model,
        profile=profile,
        text=text,
        segments=segments,
        usage_seconds=usage_seconds or None,
    )


def _normalize_segment(index: int, segment: dict[str, Any]) -> TranscriptSegment:
    raw_id = str(segment.get("id") or "").strip()
    segment_id = raw_id if raw_id.startswith("seg_") else f"seg_{index:03d}"
    return TranscriptSegment(
        segment_id=segment_id,
        text=str(segment.get("text") or "").strip(),
        start_seconds=_parse_seconds(segment.get("start_seconds")),
        end_seconds=_parse_seconds(segment.get("end_seconds")),
        speaker=_optional_text(segment.get("speaker")),
    )


def _parse_seconds(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    parts = str(value).strip().split(":")
    try:
        total = 0.0
        for part in parts:
            total = total * 60 + float(part)
        return total
    except ValueError:
        return None


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _dedupe_terms(values: Iterable[str]) -> tuple[str, ...]:
    seen = set()
    terms = []
    for value in values:
        term = " ".join(str(value).split())
        key = term.casefold()
        if term and key not in seen:
            seen.add(key)
            terms.append(term)
    return tuple(terms)


def _delete_uploaded_file(client: Any, uploaded: Any) -> None:
    name = getattr(uploaded, "name", None)
    if not name:
        return
    try:
        client.files.delete(name=name)
    except Exception:
        pass


def _build_default_gemini_client() -> Any:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY to use the gemini-audio provider")
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError(
            "Install the gemini optional dependency with: pip install -e '.[gemini]'"
        ) from exc
    return genai.Client(api_key=api_key)
