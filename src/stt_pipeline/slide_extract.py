from __future__ import annotations

from dataclasses import dataclass, field

from stt_pipeline.knowledge_pack import SlideEvidence


REFERENCE_MARKERS = (
    " et al.",
    "doi:",
    "nature ",
    "gastroenterology",
    "hepatology",
    "journal",
    "proceedings",
)

FIGURE_CONTEXT_MARKERS = (
    "next-generation",
    "hydrodynamic",
    "diameter",
    "control",
    "healthy",
    "small intestine",
    "colon",
    "ibd:",
    "road map",
    "vs",
)

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "this",
    "that",
    "using",
    "requires",
    "should",
    "clinical",
    "practice",
}


@dataclass(frozen=True)
class SlideOcrInput:
    slide_id: str
    title: str
    text_lines: list[str] = field(default_factory=list)
    source_path: str | None = None


def extract_slide_evidence(slide: SlideOcrInput) -> SlideEvidence:
    references: list[str] = []
    full_sentences: list[str] = []
    figure_contexts: list[str] = []
    named_entities: list[str] = []
    isolated_keywords: list[str] = []

    for line in (_clean_line(value) for value in slide.text_lines):
        if not line:
            continue
        if _is_reference(line):
            references.append(line)
            continue
        if _is_full_sentence(line):
            full_sentences.append(line)
        if _is_figure_context(line):
            figure_contexts.append(line)
        named_entities.extend(_extract_named_entities(line))
        isolated_keywords.extend(_extract_keywords(line))

    named_entities.extend(_extract_named_entities(slide.title))

    return SlideEvidence(
        slide_id=slide.slide_id,
        title=slide.title,
        references=list(_dedupe(references)),
        full_sentences=list(_dedupe(full_sentences)),
        figure_contexts=list(_dedupe(figure_contexts)),
        named_entities=list(_dedupe(named_entities)),
        isolated_keywords=list(_dedupe(isolated_keywords)),
    )


def _is_reference(line: str) -> bool:
    lowered = line.casefold()
    has_year = "(20" in line or " 20" in line
    return has_year and any(marker in lowered for marker in REFERENCE_MARKERS)


def _is_full_sentence(line: str) -> bool:
    return len(line) >= 60 and line.endswith((".", "?", "!"))


def _is_figure_context(line: str) -> bool:
    lowered = line.casefold()
    return any(marker in lowered for marker in FIGURE_CONTEXT_MARKERS)


def _extract_named_entities(line: str) -> list[str]:
    entities = []
    if "Large language models" in line:
        entities.append("Large language models")
    for token in _tokenize(line):
        if len(token) < 3:
            continue
        if token.isupper() and len(token) <= 8:
            entities.append(token)
            continue
        if "-" in token and any(char.isupper() for char in token):
            entities.append(token)
            continue
        if any(char.isupper() for char in token[1:]):
            entities.append(token)
    return entities


def _extract_keywords(line: str) -> list[str]:
    keywords = []
    for token in _tokenize(line):
        lowered = token.casefold()
        if len(lowered) < 4 or lowered in STOPWORDS:
            continue
        if token.isupper() or any(char.isupper() for char in token[1:]):
            continue
        keywords.append(lowered)
    return keywords


def _tokenize(line: str) -> list[str]:
    normalized = line.replace("(", " ").replace(")", " ").replace(",", " ")
    normalized = normalized.replace(":", " ").replace(";", " ")
    return [token.strip(".") for token in normalized.split()]


def _clean_line(line: str) -> str:
    return " ".join(str(line).split())


def _dedupe(values: list[str]):
    seen = set()
    for value in values:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            yield value
