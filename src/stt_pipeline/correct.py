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
    }


class OpenAiTranscriptCorrector:
    def __init__(self, client: Any | None = None, model: str | None = None):
        self._client = client
        self._model = model

    def correct(
        self,
        result: TranscriptResult,
        *,
        prompt_terms: Iterable[str] = (),
    ) -> CorrectionReport:
        client = self._client or _build_default_openai_client()
        model = self._model or build_openai_config_from_env().text_model
        response = client.responses.create(
            model=model,
            input=_build_correction_input(result, prompt_terms),
            text={"format": _correction_json_schema()},
        )
        return apply_declared_corrections(
            result,
            _parse_corrections(json.loads(_response_output_text(response))),
        )


def _build_correction_input(
    result: TranscriptResult,
    prompt_terms: Iterable[str],
) -> list[dict[str, str]]:
    terms = ", ".join(_dedupe_terms(prompt_terms)) or "none"
    segments = "\n".join(
        f"{segment.segment_id}: {segment.text}" for segment in result.segments
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
                "Transcript segments:\n"
                f"{segments}\n\n"
                "Return corrections with segment_id, original, corrected, reason, confidence."
            ),
        },
    ]


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
