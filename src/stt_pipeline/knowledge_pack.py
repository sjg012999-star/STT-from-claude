from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class EvidenceGrade(Enum):
    """Source strength for downstream enrichment."""

    REFERENCE_PDF = "A"
    SLIDE_SENTENCE = "B"
    FIGURE_CONTEXT = "B"
    NAMED_ENTITY = "C"
    ISOLATED_KEYWORD = "D"


@dataclass(frozen=True)
class SlideEvidence:
    slide_id: str
    title: str
    references: list[str] = field(default_factory=list)
    full_sentences: list[str] = field(default_factory=list)
    figure_contexts: list[str] = field(default_factory=list)
    named_entities: list[str] = field(default_factory=list)
    isolated_keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TranscriptSegment:
    segment_id: str
    text: str


@dataclass(frozen=True)
class ResearchTask:
    query: str
    evidence_grade: EvidenceGrade
    priority_score: int
    source_slide_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class PdfExtractionJob:
    reference: str
    source_slide_ids: tuple[str, ...]
    tools: tuple[str, ...] = ("pymupdf", "pdfplumber", "camelot-py")
    goal: str = "extract figure/table captions, crops, and table cells from the source PDF"


@dataclass(frozen=True)
class SlideTranscriptLink:
    slide_id: str
    segment_id: str
    matched_terms: tuple[str, ...]
    score: int


@dataclass(frozen=True)
class KnowledgePack:
    research_tasks: tuple[ResearchTask, ...]
    pdf_extraction_jobs: tuple[PdfExtractionJob, ...]
    slide_transcript_links: tuple[SlideTranscriptLink, ...]
    glossary_terms: tuple[str, ...]
    enrichment_sections: tuple[str, ...] = (
        "speaker_transcript",
        "slide_text",
        "reference_pdf",
        "additional_research",
        "needs_review",
    )


def build_knowledge_pack(
    slides: Iterable[SlideEvidence],
    transcript_segments: Iterable[TranscriptSegment] = (),
) -> KnowledgePack:
    slide_list = tuple(slides)
    tasks = _build_research_tasks(slide_list)
    return KnowledgePack(
        research_tasks=tasks,
        pdf_extraction_jobs=_build_pdf_extraction_jobs(slide_list),
        slide_transcript_links=_align_transcript_to_slides(
            slide_list, tuple(transcript_segments)
        ),
        glossary_terms=_build_glossary_terms(slide_list),
    )


def _build_research_tasks(slides: tuple[SlideEvidence, ...]) -> tuple[ResearchTask, ...]:
    references = _collect_sources(slides, "references")
    full_sentences = _collect_sources(slides, "full_sentences")
    figure_contexts = _collect_sources(slides, "figure_contexts")
    named_entities = _collect_sources(slides, "named_entities")
    isolated_keywords = _collect_sources(slides, "isolated_keywords")

    tasks: list[ResearchTask] = []
    tasks.extend(
        _tasks_from_sources(
            references,
            grade=EvidenceGrade.REFERENCE_PDF,
            base_score=100,
            repeated_bonus=25,
            repeated_reason="reference appears on {count} slides",
            single_reason="reference printed on slide",
        )
    )
    tasks.extend(
        _tasks_from_sources(
            full_sentences,
            grade=EvidenceGrade.SLIDE_SENTENCE,
            base_score=70,
            repeated_bonus=10,
            repeated_reason="full sentence appears on {count} slides",
            single_reason="full sentence printed on slide",
        )
    )
    tasks.extend(
        _tasks_from_sources(
            figure_contexts,
            grade=EvidenceGrade.FIGURE_CONTEXT,
            base_score=60,
            repeated_bonus=10,
            repeated_reason="figure/table context appears on {count} slides",
            single_reason="figure/table context printed on slide",
        )
    )
    tasks.extend(
        _tasks_from_sources(
            named_entities,
            grade=EvidenceGrade.NAMED_ENTITY,
            base_score=40,
            repeated_bonus=5,
            repeated_reason="named entity appears on {count} slides",
            single_reason="named entity printed on slide",
        )
    )
    tasks.extend(
        _tasks_from_sources(
            isolated_keywords,
            grade=EvidenceGrade.ISOLATED_KEYWORD,
            base_score=10,
            repeated_bonus=2,
            repeated_reason="isolated keyword appears on {count} slides",
            single_reason="isolated keyword printed on slide",
        )
    )

    return tuple(
        sorted(
            tasks,
            key=lambda task: (
                -task.priority_score,
                task.evidence_grade.value,
                task.query.casefold(),
            ),
        )
    )


def _collect_sources(
    slides: tuple[SlideEvidence, ...], field_name: str
) -> dict[str, list[str]]:
    source_map: dict[str, list[str]] = defaultdict(list)
    for slide in slides:
        values = getattr(slide, field_name)
        for value in values:
            normalized = _clean_value(value)
            if normalized and slide.slide_id not in source_map[normalized]:
                source_map[normalized].append(slide.slide_id)
    return source_map


def _tasks_from_sources(
    source_map: dict[str, list[str]],
    *,
    grade: EvidenceGrade,
    base_score: int,
    repeated_bonus: int,
    repeated_reason: str,
    single_reason: str,
) -> list[ResearchTask]:
    tasks = []
    for query, slide_ids in source_map.items():
        count = len(slide_ids)
        reason = repeated_reason.format(count=count) if count > 1 else single_reason
        tasks.append(
            ResearchTask(
                query=query,
                evidence_grade=grade,
                priority_score=base_score + repeated_bonus * (count - 1),
                source_slide_ids=tuple(slide_ids),
                reason=reason,
            )
        )
    return tasks


def _build_pdf_extraction_jobs(
    slides: tuple[SlideEvidence, ...],
) -> tuple[PdfExtractionJob, ...]:
    jobs = []
    for reference, slide_ids in _collect_sources(slides, "references").items():
        jobs.append(PdfExtractionJob(reference=reference, source_slide_ids=tuple(slide_ids)))
    return tuple(jobs)


def _align_transcript_to_slides(
    slides: tuple[SlideEvidence, ...],
    transcript_segments: tuple[TranscriptSegment, ...],
) -> tuple[SlideTranscriptLink, ...]:
    links = []
    for segment in transcript_segments:
        best_link: SlideTranscriptLink | None = None
        for slide in slides:
            terms = _slide_match_terms(slide)
            matched = tuple(term for term in terms if _contains_term(segment.text, term))
            if not matched:
                continue
            link = SlideTranscriptLink(
                slide_id=slide.slide_id,
                segment_id=segment.segment_id,
                matched_terms=matched,
                score=sum(_term_weight(term) for term in matched),
            )
            if best_link is None or link.score > best_link.score:
                best_link = link
        if best_link is not None:
            links.append(best_link)
    return tuple(sorted(links, key=lambda link: (-link.score, link.segment_id, link.slide_id)))


def _slide_match_terms(slide: SlideEvidence) -> tuple[str, ...]:
    terms = [slide.title, *slide.named_entities]
    for sentence in slide.full_sentences:
        terms.extend(_important_sentence_terms(sentence))
    return _dedupe(terms)


def _important_sentence_terms(sentence: str) -> tuple[str, ...]:
    candidates = []
    for raw in sentence.replace("(", " ").replace(")", " ").replace(",", " ").split():
        value = raw.strip(".:;")
        if len(value) >= 4 and any(char.isupper() for char in value):
            candidates.append(value)
    return tuple(candidates)


def _build_glossary_terms(slides: tuple[SlideEvidence, ...]) -> tuple[str, ...]:
    terms = []
    for slide in slides:
        terms.extend(slide.references)
        terms.extend(slide.named_entities)
        terms.extend(_important_sentence_terms(" ".join(slide.full_sentences)))
    return _dedupe(_clean_value(term) for term in terms)


def _contains_term(text: str, term: str) -> bool:
    return term.casefold() in text.casefold()


def _term_weight(term: str) -> int:
    if " " in term:
        return 3
    if any(char.isupper() for char in term) and len(term) > 3:
        return 2
    return 1


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    result = []
    seen = set()
    for value in values:
        cleaned = _clean_value(value)
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return tuple(result)


def _clean_value(value: str) -> str:
    return " ".join(str(value).split())
