from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote

from stt_pipeline.knowledge_pack import EvidenceGrade, KnowledgePack


@dataclass(frozen=True)
class ReferenceLookupPlan:
    reference: str
    bibliographic_query: str
    source_slide_ids: tuple[str, ...]
    priority_score: int
    search_urls: tuple[str, ...]
    doi: str | None = None
    status: str = "needs_lookup"


def build_reference_lookup_plans(
    pack: KnowledgePack,
    *,
    max_references: int | None = None,
) -> tuple[ReferenceLookupPlan, ...]:
    reference_tasks = tuple(
        task
        for task in pack.research_tasks
        if task.evidence_grade is EvidenceGrade.REFERENCE_PDF
    )
    plans = []
    for task in reference_tasks:
        doi = _extract_doi(task.query)
        bibliographic_query = _clean_reference_query(task.query)
        plans.append(
            ReferenceLookupPlan(
                reference=task.query,
                bibliographic_query=bibliographic_query,
                source_slide_ids=task.source_slide_ids,
                priority_score=task.priority_score,
                doi=doi,
                search_urls=_build_search_urls(bibliographic_query, doi=doi),
                status="planned" if doi else "needs_lookup",
            )
        )

    ordered = tuple(
        sorted(
            plans,
            key=lambda plan: (-plan.priority_score, plan.reference.casefold()),
        )
    )
    if max_references is None or max_references <= 0:
        return ordered
    return ordered[:max_references]


def reference_lookup_plans_to_dict(
    plans: tuple[ReferenceLookupPlan, ...],
) -> dict[str, object]:
    return {
        "references": [
            {
                "reference": plan.reference,
                "bibliographic_query": plan.bibliographic_query,
                "source_slide_ids": list(plan.source_slide_ids),
                "priority_score": plan.priority_score,
                "doi": plan.doi,
                "search_urls": list(plan.search_urls),
                "status": plan.status,
            }
            for plan in plans
        ]
    }


def _extract_doi(reference: str) -> str | None:
    match = re.search(r"\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", reference, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).rstrip(").,;").lower()


def _clean_reference_query(reference: str) -> str:
    without_doi = re.sub(
        r"\bdoi\s*:?\s*10\.\d{4,9}/[-._;()/:A-Z0-9]+",
        "",
        reference,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", without_doi).strip(" .;,")


def _build_search_urls(
    bibliographic_query: str,
    *,
    doi: str | None,
) -> tuple[str, ...]:
    urls = []
    if doi:
        encoded_doi = quote(doi, safe="")
        urls.append(f"https://doi.org/{doi}")
        urls.append(f"https://api.crossref.org/works/{encoded_doi}")

    encoded_query = quote(bibliographic_query)
    urls.append(f"https://api.crossref.org/works?query.bibliographic={encoded_query}")
    urls.append(f"https://api.openalex.org/works?search={encoded_query}")
    return tuple(_dedupe(urls))


def _dedupe(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
