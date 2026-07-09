from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable

from stt_pipeline.correct import CorrectionReport
from stt_pipeline.llm_provider import build_openai_config_from_env
from stt_pipeline.materials import MaterialPack
from stt_pipeline.pdf_tools import PdfExtractionResult
from stt_pipeline.reference_lookup import ReferenceLookupPlan, ReferenceLookupResult
from stt_pipeline.transcript import TranscriptResult


ALLOWED_SOURCE_LABELS = {
    "speaker_transcript",
    "slide_text",
    "reference_pdf",
    "additional_research",
}


@dataclass(frozen=True)
class RichSummaryItem:
    text: str
    source_label: str
    evidence: str


@dataclass(frozen=True)
class RichSummarySection:
    title: str
    items: tuple[RichSummaryItem, ...]


@dataclass(frozen=True)
class RichSummaryResult:
    markdown: str
    section_count: int
    item_count: int


class OpenAiRichSummarizer:
    def __init__(self, client: Any | None = None, model: str | None = None):
        self._client = client
        self._model = model

    def summarize(
        self,
        result: TranscriptResult,
        *,
        prompt_terms: Iterable[str] = (),
        material_pack: MaterialPack | None = None,
        pdf_results: tuple[PdfExtractionResult, ...] = (),
        reference_lookup_plans: tuple[ReferenceLookupPlan, ...] = (),
        reference_lookup_results: tuple[ReferenceLookupResult, ...] = (),
        correction_report: CorrectionReport | None = None,
    ) -> RichSummaryResult:
        client = self._client or _build_default_openai_client()
        model = self._model or build_openai_config_from_env().text_model
        response = client.responses.create(
            model=model,
            input=_build_summary_input(
                result,
                prompt_terms=prompt_terms,
                material_pack=material_pack,
                pdf_results=pdf_results,
                reference_lookup_plans=reference_lookup_plans,
                reference_lookup_results=reference_lookup_results,
                correction_report=correction_report,
            ),
            text={"format": _rich_summary_json_schema()},
        )
        sections = _parse_sections(json.loads(_response_output_text(response)))
        return _render_rich_summary(sections)


def _build_summary_input(
    result: TranscriptResult,
    *,
    prompt_terms: Iterable[str],
    material_pack: MaterialPack | None,
    pdf_results: tuple[PdfExtractionResult, ...],
    reference_lookup_plans: tuple[ReferenceLookupPlan, ...],
    reference_lookup_results: tuple[ReferenceLookupResult, ...],
    correction_report: CorrectionReport | None,
) -> list[dict[str, str]]:
    terms = ", ".join(_dedupe(prompt_terms)) or "none"
    transcript = "\n".join(
        "{segment_id} {time} {speaker}{text}".format(
            segment_id=segment.segment_id,
            time=_segment_time(segment.start_seconds, segment.end_seconds),
            speaker=f"{segment.speaker}: " if segment.speaker else "",
            text=segment.text,
        )
        for segment in result.segments
    )
    slide_context = _slide_context(material_pack)
    pdf_context = _pdf_context(pdf_results)
    lookup_context = _lookup_context(reference_lookup_plans)
    lookup_result_context = _lookup_result_context(reference_lookup_results)
    correction_context = _correction_context(correction_report)
    return [
        {
            "role": "system",
            "content": (
                "Build a concise source-labeled rich summary. Every item must use one "
                "source_label from: speaker_transcript, slide_text, reference_pdf, "
                "additional_research. Do not invent findings. Use additional_research "
                "only for provided lookup or external evidence, not guesses."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Profile: {result.profile}\n"
                f"Relevant terms: {terms}\n\n"
                "Speaker transcript:\n"
                f"{transcript}\n\n"
                "Slide-derived context:\n"
                f"{slide_context}\n\n"
                "Reference PDF context:\n"
                f"{pdf_context}\n\n"
                "Reference lookup plans:\n"
                f"{lookup_context}\n\n"
                "Reference lookup results:\n"
                f"{lookup_result_context}\n\n"
                "Transcript correction context:\n"
                f"{correction_context}\n\n"
                "Return sections with title and items. Each item needs text, "
                "source_label, and evidence."
            ),
        },
    ]


def _rich_summary_json_schema() -> dict[str, object]:
    item_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "source_label": {
                "type": "string",
                "enum": sorted(ALLOWED_SOURCE_LABELS),
            },
            "evidence": {"type": "string"},
        },
        "required": ["text", "source_label", "evidence"],
        "additionalProperties": False,
    }
    return {
        "type": "json_schema",
        "name": "rich_summary",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "items": {"type": "array", "items": item_schema},
                        },
                        "required": ["title", "items"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["sections"],
            "additionalProperties": False,
        },
    }


def _parse_sections(payload: dict[str, Any]) -> tuple[RichSummarySection, ...]:
    sections = []
    for raw_section in payload.get("sections", []):
        title = _clean(raw_section.get("title", ""))
        items = tuple(_parse_item(raw_item) for raw_item in raw_section.get("items", []))
        if title and items:
            sections.append(RichSummarySection(title=title, items=items))
    if not sections:
        raise ValueError("OpenAI rich summary response did not include any valid sections")
    return tuple(sections)


def _parse_item(raw_item: dict[str, Any]) -> RichSummaryItem:
    text = _clean(raw_item.get("text", ""))
    source_label = _clean(raw_item.get("source_label", ""))
    evidence = _clean(raw_item.get("evidence", ""))
    if source_label not in ALLOWED_SOURCE_LABELS:
        raise ValueError(f"unknown rich summary source label: {source_label}")
    if not text:
        raise ValueError("rich summary item text is required")
    if not evidence:
        raise ValueError("rich summary item evidence is required")
    return RichSummaryItem(text=text, source_label=source_label, evidence=evidence)


def _render_rich_summary(
    sections: tuple[RichSummarySection, ...],
) -> RichSummaryResult:
    lines = ["# Rich Summary", ""]
    item_count = 0
    for section in sections:
        lines.extend([f"## {section.title}", ""])
        for item in section.items:
            item_count += 1
            lines.append(f"- [{item.source_label}] {item.text} _(evidence: {item.evidence})_")
        lines.append("")
    return RichSummaryResult(
        markdown="\n".join(lines).rstrip() + "\n",
        section_count=len(sections),
        item_count=item_count,
    )


def _slide_context(material_pack: MaterialPack | None) -> str:
    if material_pack is None:
        return "none"
    lines = []
    for task in material_pack.knowledge_pack.research_tasks[:12]:
        slides = ", ".join(task.source_slide_ids) or "unknown"
        lines.append(f"{task.evidence_grade.name} | {slides} | {task.query}")
    return "\n".join(lines) or "none"


def _pdf_context(pdf_results: tuple[PdfExtractionResult, ...]) -> str:
    if not pdf_results:
        return "none"
    return "\n".join(
        f"{result.reference} | {result.pdf_path} | {result.out_dir} | {result.status}"
        for result in pdf_results
    )


def _lookup_context(reference_lookup_plans: tuple[ReferenceLookupPlan, ...]) -> str:
    if not reference_lookup_plans:
        return "none"
    return "\n".join(
        f"{plan.reference} | {plan.status} | {', '.join(plan.search_urls[:3])}"
        for plan in reference_lookup_plans
    )


def _lookup_result_context(
    reference_lookup_results: tuple[ReferenceLookupResult, ...],
) -> str:
    if not reference_lookup_results:
        return "none"
    return "\n".join(
        "{reference} | {status} | {source} | quality {quality} | {title} | {pdf} | review {review}".format(
            reference=result.reference,
            status=result.status,
            source=result.metadata_source or "unknown",
            quality=result.metadata_quality_score,
            title=result.title or "unknown",
            pdf=result.cached_pdf_path or result.pdf_url or "not found",
            review=", ".join(result.review_flags) or "none",
        )
        for result in reference_lookup_results
    )


def _correction_context(correction_report: CorrectionReport | None) -> str:
    if correction_report is None or not correction_report.applied_corrections:
        return "none"
    return "\n".join(
        f"{correction.segment_id}: {correction.original} -> {correction.corrected}"
        for correction in correction_report.applied_corrections
    )


def _segment_time(start: float | None, end: float | None) -> str:
    if start is None and end is None:
        return "[no timestamp]"
    return f"[{start if start is not None else '?'}-{end if end is not None else '?'}]"


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
    raise ValueError("OpenAI rich summary response did not include output_text")


def _get_value(source: Any, key: str, default: Any) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    result = []
    seen = set()
    for value in values:
        cleaned = _clean(value)
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return tuple(result)


def _clean(value: object) -> str:
    return " ".join(str(value).split())


def _build_default_openai_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Install the openai package to use OpenAI rich summaries") from exc
    return OpenAI()
