from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from stt_pipeline.correct import CorrectionReport


@dataclass(frozen=True)
class GlossaryEntry:
    original: str
    corrected: str
    reason: str
    confidence: str
    count: int = 1


def build_glossary_entries_from_corrections(
    report: CorrectionReport,
) -> tuple[GlossaryEntry, ...]:
    entries = []
    for correction in report.applied_corrections:
        entries.append(
            GlossaryEntry(
                original=_clean(correction.original),
                corrected=_clean(correction.corrected),
                reason=_clean(correction.reason),
                confidence=_clean(correction.confidence),
                count=1,
            )
        )
    return merge_glossary_entries((), tuple(entries))


def merge_glossary_entries(
    existing: tuple[GlossaryEntry, ...],
    new_entries: tuple[GlossaryEntry, ...],
) -> tuple[GlossaryEntry, ...]:
    merged: dict[tuple[str, str], GlossaryEntry] = {}
    for entry in (*existing, *new_entries):
        key = (entry.original.casefold(), entry.corrected.casefold())
        previous = merged.get(key)
        if previous is None:
            merged[key] = entry
            continue
        merged[key] = GlossaryEntry(
            original=previous.original,
            corrected=previous.corrected,
            reason=previous.reason or entry.reason,
            confidence=_max_confidence(previous.confidence, entry.confidence),
            count=previous.count + entry.count,
        )
    return tuple(
        sorted(
            merged.values(),
            key=lambda value: (-value.count, value.corrected.casefold(), value.original.casefold()),
        )
    )


def load_glossary_tsv(path: str | Path) -> tuple[GlossaryEntry, ...]:
    glossary_path = Path(path)
    if not glossary_path.exists():
        return ()
    with glossary_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return tuple(
            GlossaryEntry(
                original=row.get("original", ""),
                corrected=row.get("corrected", ""),
                reason=row.get("reason", ""),
                confidence=row.get("confidence", ""),
                count=int(row.get("count") or "1"),
            )
            for row in reader
            if row.get("original") and row.get("corrected")
        )


def write_glossary_tsv(path: str | Path, entries: tuple[GlossaryEntry, ...]) -> None:
    glossary_path = Path(path)
    glossary_path.parent.mkdir(parents=True, exist_ok=True)
    with glossary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("original", "corrected", "reason", "confidence", "count"),
            delimiter="\t",
        )
        writer.writeheader()
        for entry in entries:
            writer.writerow(
                {
                    "original": entry.original,
                    "corrected": entry.corrected,
                    "reason": entry.reason,
                    "confidence": entry.confidence,
                    "count": entry.count,
                }
            )


def _max_confidence(left: str, right: str) -> str:
    order = {"high": 3, "medium": 2, "low": 1}
    return left if order.get(left, 0) >= order.get(right, 0) else right


def _clean(value: object) -> str:
    return " ".join(str(value).split())
