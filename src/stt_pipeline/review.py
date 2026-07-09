from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from stt_pipeline.correct import Correction, CorrectionReport
from stt_pipeline.reference_lookup import ReferenceLookupResult


@dataclass(frozen=True)
class ReviewItem:
    item_id: str
    kind: str
    status: str
    title: str
    reason: str
    source: str
    payload: dict[str, Any]

    def with_status(self, status: str) -> "ReviewItem":
        return replace(self, status=status)


def build_review_queue(
    *,
    correction_report: CorrectionReport | None = None,
    reference_lookup_results: tuple[ReferenceLookupResult, ...] = (),
    metadata_quality_threshold: int = 70,
) -> tuple[ReviewItem, ...]:
    items = []
    if correction_report is not None:
        for correction in correction_report.applied_corrections:
            items.append(_glossary_candidate(correction))
    for result in reference_lookup_results:
        if _needs_reference_review(result, metadata_quality_threshold):
            items.append(_reference_metadata_item(result))
    return tuple(items)


def review_queue_to_dict(items: tuple[ReviewItem, ...]) -> dict[str, object]:
    return {"items": [asdict(item) for item in items]}


def load_review_decisions(path: str | Path) -> dict[str, str]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_items = payload.get("items", []) if isinstance(payload, dict) else []
    decisions = {}
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("item_id") or "")
        status = str(item.get("status") or "")
        if item_id and status in {"accepted", "rejected", "pending"}:
            decisions[item_id] = status
    return decisions


def filter_report_to_accepted_glossary_corrections(
    report: CorrectionReport,
    decisions: dict[str, str],
) -> CorrectionReport:
    accepted = tuple(
        correction
        for correction in report.applied_corrections
        if decisions.get(glossary_review_item_id(correction)) == "accepted"
    )
    return CorrectionReport(
        corrected_result=report.corrected_result,
        applied_corrections=accepted,
        rejected_corrections=report.rejected_corrections,
        chunks=report.chunks,
    )


def glossary_review_item_id(correction: Correction) -> str:
    key = "|".join(
        (
            correction.segment_id,
            correction.original,
            correction.corrected,
            correction.reason,
        )
    )
    return f"glossary:{_digest(key)}"


def _glossary_candidate(correction: Correction) -> ReviewItem:
    return ReviewItem(
        item_id=glossary_review_item_id(correction),
        kind="glossary_candidate",
        status="pending",
        title=f"{correction.original} -> {correction.corrected}",
        reason="Applied transcript correction can be reused as a future prompt term.",
        source=correction.segment_id,
        payload={
            "segment_id": correction.segment_id,
            "original": correction.original,
            "corrected": correction.corrected,
            "reason": correction.reason,
            "confidence": correction.confidence,
        },
    )


def _reference_metadata_item(result: ReferenceLookupResult) -> ReviewItem:
    return ReviewItem(
        item_id=f"reference:{_digest(result.reference + '|' + str(result.doi or ''))}",
        kind="reference_metadata",
        status="pending",
        title=result.title or result.reference,
        reason="Reference lookup has low metadata quality or review flags.",
        source=result.lookup_url or result.reference,
        payload={
            "reference": result.reference,
            "doi": result.doi,
            "title": result.title,
            "metadata_source": result.metadata_source,
            "metadata_quality_score": result.metadata_quality_score,
            "review_flags": list(result.review_flags),
            "pdf_url": result.pdf_url,
            "cached_pdf_path": str(result.cached_pdf_path) if result.cached_pdf_path else None,
        },
    )


def _needs_reference_review(
    result: ReferenceLookupResult,
    metadata_quality_threshold: int,
) -> bool:
    return bool(result.review_flags) or result.metadata_quality_score < metadata_quality_threshold


def _digest(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
