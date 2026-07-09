from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

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


@dataclass(frozen=True)
class ReferenceLookupResult:
    reference: str
    bibliographic_query: str
    source_slide_ids: tuple[str, ...]
    priority_score: int
    lookup_url: str | None
    doi: str | None
    title: str | None
    pdf_url: str | None
    cached_pdf_path: Path | None
    status: str
    error: str | None = None
    metadata_source: str | None = None
    metadata_quality_score: int = 0
    review_flags: tuple[str, ...] = ()
    publisher_pdf_urls: tuple[str, ...] = ()


class ReferenceLookupHttpClient:
    def get_json(self, url: str) -> dict[str, Any]:
        request = Request(url, headers={"User-Agent": "stt-conference-reference-lookup/0.1"})
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

    def download(self, url: str) -> bytes:
        request = Request(url, headers={"User-Agent": "stt-conference-reference-lookup/0.1"})
        with urlopen(request, timeout=30) as response:
            return response.read()


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


def lookup_and_cache_references(
    plans: tuple[ReferenceLookupPlan, ...],
    *,
    cache_dir: Path,
    http_client,
) -> tuple[ReferenceLookupResult, ...]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for plan in plans:
        results.append(_lookup_one(plan, cache_dir=cache_dir, http_client=http_client))
    return tuple(results)


def reference_lookup_results_to_dict(
    results: tuple[ReferenceLookupResult, ...],
) -> dict[str, object]:
    return {
        "references": [
            {
                "reference": result.reference,
                "bibliographic_query": result.bibliographic_query,
                "source_slide_ids": list(result.source_slide_ids),
                "priority_score": result.priority_score,
                "lookup_url": result.lookup_url,
                "doi": result.doi,
                "title": result.title,
                "pdf_url": result.pdf_url,
                "cached_pdf_path": (
                    str(result.cached_pdf_path)
                    if result.cached_pdf_path is not None
                    else None
                ),
                "status": result.status,
                "error": result.error,
                "metadata_source": result.metadata_source,
                "metadata_quality_score": result.metadata_quality_score,
                "review_flags": list(result.review_flags),
                "publisher_pdf_urls": list(result.publisher_pdf_urls),
            }
            for result in results
        ]
    }


def _lookup_one(
    plan: ReferenceLookupPlan,
    *,
    cache_dir: Path,
    http_client,
) -> ReferenceLookupResult:
    lookup_urls = _metadata_lookup_urls(plan)
    if not lookup_urls:
        return _result_from_plan(plan, lookup_url=None, status="needs_lookup")
    best_result: ReferenceLookupResult | None = None
    candidates: list[ReferenceLookupResult] = []
    errors = []
    for lookup_url in lookup_urls:
        try:
            result = _lookup_metadata_url(
                plan,
                lookup_url=lookup_url,
                cache_dir=cache_dir,
                http_client=http_client,
            )
        except Exception as exc:  # pragma: no cover - fake clients cover the fallback behavior.
            errors.append(f"{lookup_url}: {exc}")
            continue
        candidates.append(result)
        if result.status == "downloaded":
            return _finalize_result(result, candidates, plan)
        best_result = _select_best_result(candidates, plan)
    if best_result is not None:
        fallback_result = _try_publisher_pdf_fallback(
            plan,
            best_result=best_result,
            cache_dir=cache_dir,
            http_client=http_client,
        )
        if fallback_result is not None:
            return _finalize_result(fallback_result, [*candidates, fallback_result], plan)
        return _finalize_result(best_result, candidates, plan)
    return _result_from_plan(
        plan,
        lookup_url=lookup_urls[0],
        status="lookup_failed",
        error="; ".join(errors) if errors else None,
    )


def _lookup_metadata_url(
    plan: ReferenceLookupPlan,
    *,
    lookup_url: str,
    cache_dir: Path,
    http_client,
) -> ReferenceLookupResult:
    payload = http_client.get_json(lookup_url)
    metadata = _metadata_from_payload(payload)
    pdf_url = metadata.get("pdf_url")
    cached_pdf_path = None
    status = "metadata_found"
    if pdf_url:
        cached_pdf_path = cache_dir / _safe_pdf_filename(metadata.get("doi") or plan.doi or plan.reference)
        cached_pdf_path.write_bytes(http_client.download(pdf_url))
        status = "downloaded"
    return _result_from_plan(
        plan,
        lookup_url=lookup_url,
        doi=metadata.get("doi") or plan.doi,
        title=metadata.get("title"),
        pdf_url=pdf_url,
        cached_pdf_path=cached_pdf_path,
        status=status,
        metadata_source=_metadata_source_from_url(lookup_url),
    )


def _result_from_plan(
    plan: ReferenceLookupPlan,
    *,
    lookup_url: str | None,
    status: str,
    doi: str | None = None,
    title: str | None = None,
    pdf_url: str | None = None,
    cached_pdf_path: Path | None = None,
    error: str | None = None,
    metadata_source: str | None = None,
    metadata_quality_score: int = 0,
    review_flags: tuple[str, ...] = (),
    publisher_pdf_urls: tuple[str, ...] = (),
) -> ReferenceLookupResult:
    return ReferenceLookupResult(
        reference=plan.reference,
        bibliographic_query=plan.bibliographic_query,
        source_slide_ids=plan.source_slide_ids,
        priority_score=plan.priority_score,
        lookup_url=lookup_url,
        doi=doi or plan.doi,
        title=title,
        pdf_url=pdf_url,
        cached_pdf_path=cached_pdf_path,
        status=status,
        error=error,
        metadata_source=metadata_source,
        metadata_quality_score=metadata_quality_score,
        review_flags=review_flags,
        publisher_pdf_urls=publisher_pdf_urls,
    )


def _select_best_result(
    candidates: list[ReferenceLookupResult],
    plan: ReferenceLookupPlan,
) -> ReferenceLookupResult | None:
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda result: _metadata_quality_score(result, plan, review_flags=()),
    )


def _finalize_result(
    result: ReferenceLookupResult,
    candidates: list[ReferenceLookupResult],
    plan: ReferenceLookupPlan,
) -> ReferenceLookupResult:
    publisher_pdf_urls = result.publisher_pdf_urls or _publisher_pdf_urls(
        result.doi or plan.doi
    )
    flags = _review_flags(result, candidates, plan)
    return replace(
        result,
        metadata_quality_score=_metadata_quality_score(result, plan, review_flags=flags),
        review_flags=flags,
        publisher_pdf_urls=publisher_pdf_urls,
    )


def _review_flags(
    result: ReferenceLookupResult,
    candidates: list[ReferenceLookupResult],
    plan: ReferenceLookupPlan,
) -> tuple[str, ...]:
    flags = []
    if not result.doi:
        flags.append("doi_missing")
    if not result.title:
        flags.append("title_missing")
    if not result.pdf_url:
        flags.append("pdf_missing")
    if plan.doi and result.doi and _normalize_doi(result.doi) != _normalize_doi(plan.doi):
        flags.append("doi_mismatch")
    dois = {
        _normalize_doi(candidate.doi)
        for candidate in candidates
        if candidate.doi
    }
    if len(dois) > 1:
        flags.append("conflicting_doi")
    return tuple(_dedupe(flags))


def _metadata_quality_score(
    result: ReferenceLookupResult,
    plan: ReferenceLookupPlan,
    *,
    review_flags: tuple[str, ...],
) -> int:
    score = 0
    if result.doi:
        score += 30
    if result.title:
        score += 20
    if result.pdf_url:
        score += 30
    if plan.doi and result.doi:
        if _normalize_doi(result.doi) == _normalize_doi(plan.doi):
            score += 20
        else:
            score -= 20
    if "conflicting_doi" in review_flags:
        score -= 10
    return max(0, min(100, score))


def _try_publisher_pdf_fallback(
    plan: ReferenceLookupPlan,
    *,
    best_result: ReferenceLookupResult,
    cache_dir: Path,
    http_client,
) -> ReferenceLookupResult | None:
    doi = best_result.doi or plan.doi
    publisher_pdf_urls = _publisher_pdf_urls(doi)
    for pdf_url in publisher_pdf_urls:
        try:
            pdf_bytes = http_client.download(pdf_url)
        except Exception:
            continue
        if not _looks_like_pdf(pdf_bytes):
            continue
        cached_pdf_path = cache_dir / _safe_pdf_filename(doi or best_result.reference)
        cached_pdf_path.write_bytes(pdf_bytes)
        return _result_from_plan(
            plan,
            lookup_url=pdf_url,
            doi=doi,
            title=best_result.title,
            pdf_url=pdf_url,
            cached_pdf_path=cached_pdf_path,
            status="downloaded",
            metadata_source="publisher_pdf_fallback",
            publisher_pdf_urls=publisher_pdf_urls,
        )
    return None


def _publisher_pdf_urls(doi: str | None) -> tuple[str, ...]:
    normalized = _normalize_doi(doi)
    if not normalized:
        return ()
    suffix = normalized.split("/", 1)[1] if "/" in normalized else normalized
    urls = []
    if normalized.startswith("10.3390/"):
        urls.append(f"https://www.mdpi.com/{normalized}/pdf")
    if normalized.startswith("10.1371/"):
        urls.append(f"https://journals.plos.org/plosone/article/file?id={normalized}&type=printable")
    if normalized.startswith("10.3389/"):
        urls.append(f"https://www.frontiersin.org/articles/{normalized}/pdf")
    if normalized.startswith("10.1038/"):
        urls.append(f"https://www.nature.com/articles/{suffix}.pdf")
    if normalized.startswith(("10.1007/", "10.1186/")):
        urls.append(f"https://link.springer.com/content/pdf/{normalized}.pdf")
    if normalized.startswith("10.1002/"):
        urls.append(f"https://onlinelibrary.wiley.com/doi/pdf/{normalized}")
    if normalized.startswith("10.1021/"):
        urls.append(f"https://pubs.acs.org/doi/pdf/{normalized}")
    if normalized.startswith("10.1080/"):
        urls.append(f"https://www.tandfonline.com/doi/pdf/{normalized}")
    return tuple(_dedupe(urls))


def _metadata_source_from_url(url: str) -> str:
    if "api.openalex.org/works" in url:
        return "openalex"
    if "api.semanticscholar.org/graph/v1/paper" in url:
        return "semantic_scholar"
    if "api.crossref.org/works" in url:
        return "crossref"
    return "unknown"


def _metadata_lookup_urls(plan: ReferenceLookupPlan) -> tuple[str, ...]:
    exact_crossref = []
    openalex = []
    semantic_scholar = []
    broad_crossref = []
    for url in plan.search_urls:
        if "api.openalex.org/works" in url:
            openalex.append(url)
        elif "api.semanticscholar.org/graph/v1/paper" in url:
            semantic_scholar.append(url)
        elif "api.crossref.org/works" in url and "query.bibliographic" in url:
            broad_crossref.append(url)
        elif "api.crossref.org/works" in url:
            exact_crossref.append(url)
    return tuple(_dedupe([*exact_crossref, *openalex, *semantic_scholar, *broad_crossref]))


def _metadata_from_payload(payload: dict[str, Any]) -> dict[str, str | None]:
    if "message" in payload:
        return _crossref_metadata(payload.get("message") or {})
    if "results" in payload:
        results = payload.get("results") or []
        first = results[0] if results else {}
        return _openalex_metadata(first)
    if "openAccessPdf" in payload or "externalIds" in payload:
        return _semantic_scholar_metadata(payload)
    return {"doi": None, "title": None, "pdf_url": None}


def _crossref_metadata(message: dict[str, Any]) -> dict[str, str | None]:
    title_values = message.get("title") or []
    links = message.get("link") or []
    return {
        "doi": _clean_optional(message.get("DOI")),
        "title": _clean_optional(title_values[0] if title_values else None),
        "pdf_url": _first_pdf_url(links),
    }


def _openalex_metadata(work: dict[str, Any]) -> dict[str, str | None]:
    primary_location = work.get("primary_location") or {}
    open_access = work.get("open_access") or {}
    raw_doi = _clean_optional(work.get("doi"))
    doi = raw_doi.removeprefix("https://doi.org/") if raw_doi else None
    return {
        "doi": doi,
        "title": _clean_optional(work.get("title")),
        "pdf_url": _clean_optional(
            primary_location.get("pdf_url") or open_access.get("oa_url")
        ),
    }


def _semantic_scholar_metadata(work: dict[str, Any]) -> dict[str, str | None]:
    external_ids = work.get("externalIds") or {}
    open_access_pdf = work.get("openAccessPdf") or {}
    return {
        "doi": _clean_optional(external_ids.get("DOI")),
        "title": _clean_optional(work.get("title")),
        "pdf_url": _clean_optional(open_access_pdf.get("url")),
    }


def _first_pdf_url(links: list[dict[str, Any]]) -> str | None:
    for link in links:
        url = _clean_optional(link.get("URL"))
        content_type = _clean_optional(link.get("content-type")) or ""
        if url and ("pdf" in content_type.casefold() or url.casefold().endswith(".pdf")):
            return url
    return None


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
        urls.append(
            "https://api.semanticscholar.org/graph/v1/paper/"
            f"DOI:{encoded_doi}?fields=title,externalIds,openAccessPdf"
        )

    encoded_query = quote(bibliographic_query)
    urls.append(f"https://api.crossref.org/works?query.bibliographic={encoded_query}")
    urls.append(f"https://api.openalex.org/works?search={encoded_query}")
    urls.append(
        "https://api.semanticscholar.org/graph/v1/paper/search?"
        f"query={encoded_query}&limit=1&fields=title,externalIds,openAccessPdf"
    )
    return tuple(_dedupe(urls))


def _dedupe(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _safe_pdf_filename(value: str) -> str:
    stem = "".join(char if char.isalnum() else "-" for char in value.casefold())
    stem = re.sub(r"-+", "-", stem).strip("-") or "reference"
    return f"{stem}.pdf"


def _normalize_doi(value: str | None) -> str | None:
    cleaned = _clean_optional(value)
    if not cleaned:
        return None
    return cleaned.removeprefix("https://doi.org/").removeprefix("doi:").lower()


def _looks_like_pdf(value: bytes) -> bool:
    return value.lstrip().startswith(b"%PDF")


def _clean_optional(value: object) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).split())
    return cleaned or None
