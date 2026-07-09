from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from stt_pipeline.llm_provider import build_openai_config_from_env
from stt_pipeline.transcript import TranscriptResult, TranscriptSegment


@dataclass(frozen=True)
class Correction:
    segment_id: str
    original: str
    corrected: str
    reason: str
    confidence: str


@dataclass(frozen=True)
class CorrectionReport:
    corrected_result: TranscriptResult
    applied_corrections: tuple[Correction, ...]
    rejected_corrections: tuple[Correction, ...]
    chunks: tuple["CorrectionChunk", ...] = ()


@dataclass(frozen=True)
class CorrectionChunk:
    chunk_id: str
    target_segment_ids: tuple[str, ...]
    context_segment_ids: tuple[str, ...]


def apply_declared_corrections(
    result: TranscriptResult,
    corrections: Iterable[Correction],
) -> CorrectionReport:
    corrected_segments = []
    applied = []
    rejected = []

    corrections_by_segment: dict[str, list[Correction]] = {}
    for correction in corrections:
        corrections_by_segment.setdefault(correction.segment_id, []).append(correction)

    for segment in result.segments:
        text = segment.text
        for correction in corrections_by_segment.get(segment.segment_id, []):
            if correction.original not in text:
                rejected.append(correction)
                continue
            text = text.replace(correction.original, correction.corrected, 1)
            applied.append(correction)
        corrected_segments.append(
            TranscriptSegment(
                segment_id=segment.segment_id,
                text=text,
                start_seconds=segment.start_seconds,
                end_seconds=segment.end_seconds,
                speaker=segment.speaker,
            )
        )

    corrected_text = "\n".join(segment.text for segment in corrected_segments)
    return CorrectionReport(
        corrected_result=TranscriptResult(
            provider=result.provider,
            model=result.model,
            profile=result.profile,
            text=corrected_text,
            segments=tuple(corrected_segments),
            usage_seconds=result.usage_seconds,
        ),
        applied_corrections=tuple(applied),
        rejected_corrections=tuple(rejected),
    )


def correction_report_to_dict(report: CorrectionReport) -> dict[str, object]:
    return {
        "applied_corrections": [asdict(correction) for correction in report.applied_corrections],
        "rejected_corrections": [asdict(correction) for correction in report.rejected_corrections],
        "chunks": [asdict(chunk) for chunk in report.chunks],
    }


class OpenAiTranscriptCorrector:
    def __init__(
        self,
        client: Any | None = None,
        model: str | None = None,
        *,
        max_segments_per_request: int | None = None,
        overlap_segments: int = 1,
    ):
        self._client = client
        self._model = model
        self._max_segments_per_request = max_segments_per_request
        self._overlap_segments = overlap_segments

    def correct(
        self,
        result: TranscriptResult,
        *,
        prompt_terms: Iterable[str] = (),
    ) -> CorrectionReport:
        client = self._client or _build_default_openai_client()
        model = self._model or build_openai_config_from_env().text_model
        corrections = []
        chunks = _build_correction_chunks(
            result.segments,
            max_segments_per_request=self._max_segments_per_request,
            overlap_segments=self._overlap_segments,
        )
        for chunk in chunks:
            response = client.responses.create(
                model=model,
                input=_build_correction_input(result, prompt_terms, chunk=chunk),
                text={"format": _correction_json_schema()},
            )
            corrections.extend(
                _parse_corrections(json.loads(_response_output_text(response)))
            )

        report = apply_declared_corrections(result, corrections)
        return CorrectionReport(
            corrected_result=report.corrected_result,
            applied_corrections=report.applied_corrections,
            rejected_corrections=report.rejected_corrections,
            chunks=tuple(chunks),
        )


def _build_correction_input(
    result: TranscriptResult,
    prompt_terms: Iterable[str],
    *,
    chunk: CorrectionChunk | None = None,
) -> list[dict[str, str]]:
    terms = ", ".join(_dedupe_terms(prompt_terms)) or "none"
    context_segments, target_segments = _split_segments_for_prompt(result, chunk)
    context_text = "\n".join(
        f"{segment.segment_id}: {segment.text}" for segment in context_segments
    ) or "none"
    target_text = "\n".join(
        f"{segment.segment_id}: {segment.text}" for segment in target_segments
    )
    return [
        {
            "role": "system",
            "content": (
                "Correct only clear speech-recognition errors. Preserve speaker wording, "
                "word order, and meaning. Return only declared corrections; do not rewrite "
                "style or add facts. If uncertain, leave the text unchanged."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Relevant terms: {terms}\n\n"
                "Context-only segments, do not correct these:\n"
                f"{context_text}\n\n"
                "Target segments, corrections may only refer to these segment IDs:\n"
                f"{target_text}\n\n"
                "Return corrections with segment_id, original, corrected, reason, confidence."
            ),
        },
    ]


def _build_correction_chunks(
    segments: tuple[TranscriptSegment, ...],
    *,
    max_segments_per_request: int | None,
    overlap_segments: int,
) -> tuple[CorrectionChunk, ...]:
    if not segments:
        return ()
    if max_segments_per_request is None or max_segments_per_request <= 0:
        return (
            CorrectionChunk(
                chunk_id="chunk_001",
                target_segment_ids=tuple(segment.segment_id for segment in segments),
                context_segment_ids=(),
            ),
        )

    chunks = []
    safe_overlap = max(0, overlap_segments)
    for start in range(0, len(segments), max_segments_per_request):
        target = segments[start : start + max_segments_per_request]
        context_start = max(0, start - safe_overlap)
        context = segments[context_start:start]
        chunks.append(
            CorrectionChunk(
                chunk_id=f"chunk_{len(chunks) + 1:03d}",
                target_segment_ids=tuple(segment.segment_id for segment in target),
                context_segment_ids=tuple(segment.segment_id for segment in context),
            )
        )
    return tuple(chunks)


def _split_segments_for_prompt(
    result: TranscriptResult,
    chunk: CorrectionChunk | None,
) -> tuple[tuple[TranscriptSegment, ...], tuple[TranscriptSegment, ...]]:
    if chunk is None:
        return (), result.segments
    by_id = {segment.segment_id: segment for segment in result.segments}
    context = tuple(
        by_id[segment_id]
        for segment_id in chunk.context_segment_ids
        if segment_id in by_id
    )
    target = tuple(
        by_id[segment_id]
        for segment_id in chunk.target_segment_ids
        if segment_id in by_id
    )
    return context, target


def _correction_json_schema() -> dict[str, object]:
    correction_schema = {
        "type": "object",
        "properties": {
            "segment_id": {"type": "string"},
            "original": {"type": "string"},
            "corrected": {"type": "string"},
            "reason": {"type": "string"},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        },
        "required": ["segment_id", "original", "corrected", "reason", "confidence"],
        "additionalProperties": False,
    }
    return {
        "type": "json_schema",
        "name": "transcript_corrections",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "corrections": {
                    "type": "array",
                    "items": correction_schema,
                }
            },
            "required": ["corrections"],
            "additionalProperties": False,
        },
    }


def _parse_corrections(payload: dict[str, Any]) -> tuple[Correction, ...]:
    corrections = []
    for raw in payload.get("corrections", []):
        corrections.append(
            Correction(
                segment_id=str(raw.get("segment_id", "")),
                original=str(raw.get("original", "")),
                corrected=str(raw.get("corrected", "")),
                reason=str(raw.get("reason", "")),
                confidence=str(raw.get("confidence", "low")),
            )
        )
    return tuple(corrections)


def _response_output_text(response: Any) -> str:
    if isinstance(response, dict):
        if "output_text" in response:
            return str(response["output_text"])
        output = response.get("output") or []
    else:
        output_text = getattr(response, "output_text", None)
        if output_text is not None:
            return str(output_text)
        output = getattr(response, "output", None) or []

    for item in output:
        content = _get_value(item, "content", []) or []
        for part in content:
            if _get_value(part, "type", "") == "output_text":
                return str(_get_value(part, "text", ""))
    raise ValueError("OpenAI correction response did not include output_text")


def _get_value(source: Any, key: str, default: Any) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _dedupe_terms(terms: Iterable[str]) -> tuple[str, ...]:
    seen = set()
    result = []
    for term in terms:
        cleaned = " ".join(str(term).split())
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return tuple(result)


def _build_default_openai_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Install the openai package to use OpenAI correction") from exc
    return OpenAI()
