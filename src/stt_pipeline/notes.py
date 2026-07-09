from __future__ import annotations

from dataclasses import dataclass

from stt_pipeline.materials import MaterialPack
from stt_pipeline.pdf_tools import PdfExtractionResult
from stt_pipeline.reference_lookup import ReferenceLookupPlan, ReferenceLookupResult
from stt_pipeline.transcript import TranscriptResult


@dataclass(frozen=True)
class EnrichedNotes:
    markdown: str


def build_enriched_notes(
    transcript: TranscriptResult,
    *,
    material_pack: MaterialPack | None = None,
    pdf_results: tuple[PdfExtractionResult, ...] = (),
    reference_lookup_plans: tuple[ReferenceLookupPlan, ...] = (),
    reference_lookup_results: tuple[ReferenceLookupResult, ...] = (),
) -> EnrichedNotes:
    lines = [
        "# Enriched Notes",
        "",
        "## Speaker Transcript",
        "",
        "_source: speaker_transcript_",
        "",
        *_speaker_lines(transcript),
        "",
        "## Slide Text",
        "",
        "_source: slide_text_",
        "",
        *_slide_lines(material_pack),
        "",
        "## Reference PDF",
        "",
        "_source: reference_pdf_",
        "",
        *_pdf_lines(material_pack, pdf_results),
        "",
        "## Additional Research",
        "",
        "_source: additional_research_",
        "",
        *_additional_research_lines(reference_lookup_plans, reference_lookup_results),
        "",
        "## Needs Review",
        "",
        *_needs_review_lines(material_pack, pdf_results),
    ]
    return EnrichedNotes(markdown="\n".join(lines).rstrip() + "\n")


def _speaker_lines(transcript: TranscriptResult) -> list[str]:
    lines = []
    for segment in transcript.segments:
        timestamp = (
            f"[{segment.start_seconds:.2f}-{segment.end_seconds:.2f}] "
            if segment.start_seconds is not None and segment.end_seconds is not None
            else ""
        )
        speaker = f"{segment.speaker}: " if segment.speaker else ""
        lines.append(f"- {timestamp}{speaker}{segment.text}")
    return lines or ["- No transcript segments available."]


def _slide_lines(material_pack: MaterialPack | None) -> list[str]:
    if material_pack is None:
        return ["- No material pack was provided."]
    if not material_pack.knowledge_pack.research_tasks:
        return ["- No slide-derived research tasks were detected."]
    lines = []
    for task in material_pack.knowledge_pack.research_tasks[:12]:
        lines.append(
            "- [{grade}] {query} (priority {priority}, slides: {slides})".format(
                grade=task.evidence_grade.name,
                query=task.query,
                priority=task.priority_score,
                slides=", ".join(task.source_slide_ids) or "unknown",
            )
        )
    return lines


def _pdf_lines(
    material_pack: MaterialPack | None,
    pdf_results: tuple[PdfExtractionResult, ...],
) -> list[str]:
    lines = []
    for result in pdf_results:
        lines.append(
            "- {reference} | PDF: `{pdf}` | output: `{out}` | status: {status}".format(
                reference=result.reference,
                pdf=result.pdf_path,
                out=result.out_dir,
                status=result.status,
            )
        )
    if lines:
        return lines

    if material_pack and material_pack.pdf_sources:
        return [
            f"- PDF queued but not extracted: `{pdf_source}`"
            for pdf_source in material_pack.pdf_sources
        ]
    return ["- No reference PDF source was provided."]


def _additional_research_lines(
    reference_lookup_plans: tuple[ReferenceLookupPlan, ...],
    reference_lookup_results: tuple[ReferenceLookupResult, ...],
) -> list[str]:
    if reference_lookup_results:
        return [
            "- {reference} | status: {status} | source: {source} | quality: {quality} | title: {title} | pdf: {pdf} | review: {review}".format(
                reference=result.reference,
                status=result.status,
                source=result.metadata_source or "unknown",
                quality=result.metadata_quality_score,
                title=result.title or "unknown",
                pdf=result.cached_pdf_path or result.pdf_url or "not found",
                review=", ".join(result.review_flags) or "none",
            )
            for result in reference_lookup_results
        ]
    if not reference_lookup_plans:
        return [
            "- Not run. Add explicit reference search/acquisition before treating this section as evidence."
        ]
    lines = []
    for plan in reference_lookup_plans:
        urls = ", ".join(plan.search_urls[:3])
        lines.append(
            "- {reference} | status: {status} | lookup: {urls}".format(
                reference=plan.reference,
                status=plan.status,
                urls=urls,
            )
        )
    return lines


def _needs_review_lines(
    material_pack: MaterialPack | None,
    pdf_results: tuple[PdfExtractionResult, ...],
) -> list[str]:
    lines = []
    if material_pack:
        lines.extend(f"- {warning}" for warning in material_pack.warnings)
        if material_pack.pdf_sources and not pdf_results:
            lines.append("- PDF sources exist, but `--extract-pdfs` was not run.")
    if not lines:
        lines.append("- Review transcript corrections and cited PDF outputs before using notes as evidence.")
    return lines
