from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence
from xml.etree import ElementTree

from stt_pipeline.knowledge_pack import (
    EvidenceGrade,
    KnowledgePack,
    build_knowledge_pack,
)
from stt_pipeline.slide_extract import SlideOcrInput, extract_slide_evidence


TEXT_SUFFIXES = {".txt", ".md", ".markdown"}
SUPPORTED_SUFFIXES = {*TEXT_SUFFIXES, ".json", ".pptx"}
UNSUPPORTED_MATERIAL_SUFFIXES = {
    ".jpg",
    ".jpeg",
    ".png",
    ".heic",
    ".pdf",
    ".ppt",
}


@dataclass(frozen=True)
class MaterialPack:
    source_count: int
    slide_count: int
    prompt_terms: tuple[str, ...]
    warnings: tuple[str, ...]
    sources: tuple[str, ...]
    knowledge_pack: KnowledgePack


def load_material_pack(
    paths: Iterable[str | Path],
    *,
    max_prompt_terms: int = 80,
) -> MaterialPack:
    material_paths = tuple(Path(path) for path in paths)
    slides: list[SlideOcrInput] = []
    sources: list[str] = []
    warnings: list[str] = []

    for path in material_paths:
        files, path_warnings = _expand_material_path(path)
        warnings.extend(path_warnings)
        for file_path in files:
            loaded, file_warnings = _load_material_file(file_path)
            warnings.extend(file_warnings)
            if loaded:
                slides.extend(loaded)
                sources.append(str(file_path))

    knowledge_pack = build_knowledge_pack(
        extract_slide_evidence(slide) for slide in slides
    )
    return MaterialPack(
        source_count=len(sources),
        slide_count=len(slides),
        prompt_terms=_select_prompt_terms(knowledge_pack, max_prompt_terms),
        warnings=tuple(_dedupe(warnings)),
        sources=tuple(sources),
        knowledge_pack=knowledge_pack,
    )


def material_pack_to_dict(pack: MaterialPack) -> dict[str, object]:
    return {
        "source_count": pack.source_count,
        "slide_count": pack.slide_count,
        "prompt_terms": list(pack.prompt_terms),
        "warnings": list(pack.warnings),
        "sources": list(pack.sources),
        "research_tasks": [
            {
                "query": task.query,
                "evidence_grade": task.evidence_grade.name,
                "priority_score": task.priority_score,
                "source_slide_ids": list(task.source_slide_ids),
                "reason": task.reason,
            }
            for task in pack.knowledge_pack.research_tasks
        ],
        "pdf_extraction_jobs": [
            {
                "reference": job.reference,
                "source_slide_ids": list(job.source_slide_ids),
                "tools": list(job.tools),
                "goal": job.goal,
            }
            for job in pack.knowledge_pack.pdf_extraction_jobs
        ],
    }


def _expand_material_path(path: Path) -> tuple[tuple[Path, ...], tuple[str, ...]]:
    if not path.exists():
        return (), (f"material path not found: {path}",)
    if path.is_file():
        return ((path,) if path.suffix.casefold() in SUPPORTED_SUFFIXES else ()), _unsupported_warning(path)

    files = []
    warnings = []
    for child in sorted(value for value in path.rglob("*") if value.is_file()):
        suffix = child.suffix.casefold()
        if suffix in SUPPORTED_SUFFIXES:
            files.append(child)
        elif suffix in UNSUPPORTED_MATERIAL_SUFFIXES:
            warnings.extend(_unsupported_warning(child))
    return tuple(files), tuple(_dedupe(warnings))


def _unsupported_warning(path: Path) -> tuple[str, ...]:
    suffix = path.suffix.casefold()
    if suffix in TEXT_SUFFIXES or suffix in {".json", ".pptx"}:
        return ()
    if suffix in {".jpg", ".jpeg", ".png", ".heic"}:
        return (
            f"image OCR is not wired for {path}; provide PPTX, text, or slide OCR JSON",
        )
    if suffix == ".pdf":
        return (
            f"PDF text extraction is not wired for {path}; use text notes or the PDF figure/table workflow first",
        )
    if suffix == ".ppt":
        return (f"legacy PPT is not supported for {path}; export as PPTX first",)
    return (f"unsupported material file skipped: {path}",)


def _load_material_file(path: Path) -> tuple[tuple[SlideOcrInput, ...], tuple[str, ...]]:
    suffix = path.suffix.casefold()
    try:
        if suffix in TEXT_SUFFIXES:
            return (_load_text_file(path),), ()
        if suffix == ".json":
            return _load_json_slides(path), ()
        if suffix == ".pptx":
            return _load_pptx_slides(path), ()
    except (OSError, UnicodeDecodeError, ValueError, zipfile.BadZipFile) as exc:
        return (), (f"failed to load material file {path}: {exc}",)
    return (), _unsupported_warning(path)


def _load_text_file(path: Path) -> SlideOcrInput:
    lines = _clean_lines(path.read_text(encoding="utf-8").splitlines())
    return SlideOcrInput(
        slide_id=_slide_id(path),
        title=lines[0] if lines else path.stem,
        text_lines=list(lines),
        source_path=str(path),
    )


def _load_json_slides(path: Path) -> tuple[SlideOcrInput, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "slides" in payload:
        raw_slides = payload["slides"]
    elif isinstance(payload, list):
        raw_slides = payload
    elif isinstance(payload, dict):
        raw_slides = [payload]
    else:
        raise ValueError("JSON material must be a slide object, a slide list, or {'slides': [...]}")

    slides = []
    for index, raw in enumerate(raw_slides, start=1):
        if not isinstance(raw, dict):
            raise ValueError("each JSON slide entry must be an object")
        text_lines = _clean_lines(raw.get("text_lines", []))
        title = str(raw.get("title") or (text_lines[0] if text_lines else path.stem))
        slides.append(
            SlideOcrInput(
                slide_id=str(raw.get("slide_id") or f"{path.stem}-slide-{index:03d}"),
                title=title,
                text_lines=list(text_lines),
                source_path=str(path),
            )
        )
    return tuple(slides)


def _load_pptx_slides(path: Path) -> tuple[SlideOcrInput, ...]:
    slides = []
    with zipfile.ZipFile(path) as archive:
        slide_names = sorted(
            (name for name in archive.namelist() if _is_pptx_slide_xml(name)),
            key=_slide_xml_sort_key,
        )
        for index, name in enumerate(slide_names, start=1):
            xml = archive.read(name)
            lines = _clean_lines(_extract_pptx_text_lines(xml))
            if not lines:
                continue
            slides.append(
                SlideOcrInput(
                    slide_id=f"{path.stem}-slide-{index:03d}",
                    title=lines[0],
                    text_lines=list(lines),
                    source_path=str(path),
                )
            )
    return tuple(slides)


def _is_pptx_slide_xml(name: str) -> bool:
    return name.startswith("ppt/slides/slide") and name.endswith(".xml")


def _slide_xml_sort_key(name: str) -> int:
    match = re.search(r"slide(\d+)\.xml$", name)
    return int(match.group(1)) if match else 0


def _extract_pptx_text_lines(xml: bytes) -> tuple[str, ...]:
    root = ElementTree.fromstring(xml)
    text_values = []
    for node in root.iter():
        if node.tag.endswith("}t") and node.text:
            text_values.append(node.text)
    return tuple(text_values)


def _select_prompt_terms(pack: KnowledgePack, max_prompt_terms: int) -> tuple[str, ...]:
    candidates = []
    for task in pack.research_tasks:
        if task.evidence_grade in {
            EvidenceGrade.REFERENCE_PDF,
            EvidenceGrade.SLIDE_SENTENCE,
            EvidenceGrade.FIGURE_CONTEXT,
            EvidenceGrade.NAMED_ENTITY,
        }:
            candidates.append(task.query)
    candidates.extend(pack.glossary_terms)
    return tuple(_dedupe(candidates))[:max_prompt_terms]


def _slide_id(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", path.stem).strip("-") or "material"


def _clean_lines(values: Sequence[object]) -> tuple[str, ...]:
    return tuple(
        line
        for line in (" ".join(str(value).split()) for value in values)
        if line
    )


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    result = []
    seen = set()
    for value in values:
        cleaned = " ".join(str(value).split())
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return tuple(result)
