from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class AdditionalResearchItem:
    source_path: str
    title: str
    summary: str
    url: str | None = None
    evidence: str | None = None
    source_label: str = "additional_research"


def load_additional_research_files(
    paths: Iterable[str | Path],
) -> tuple[AdditionalResearchItem, ...]:
    items: list[AdditionalResearchItem] = []
    for path_value in paths:
        path = Path(path_value)
        if path.suffix.casefold() == ".json":
            items.extend(_items_from_json(path))
        else:
            items.append(_item_from_text(path))
    return tuple(items)


def additional_research_to_dict(
    items: tuple[AdditionalResearchItem, ...],
) -> dict[str, object]:
    return {"items": [asdict(item) for item in items]}


def _items_from_json(path: Path) -> tuple[AdditionalResearchItem, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_items = payload.get("items", payload) if isinstance(payload, dict) else payload
    if not isinstance(raw_items, list):
        raise ValueError(f"additional research JSON must contain a list: {path}")
    items = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            raise ValueError(f"additional research item must be an object: {path}")
        title = _clean(raw_item.get("title")) or path.stem
        summary = _clean(raw_item.get("summary") or raw_item.get("text"))
        if not summary:
            raise ValueError(f"additional research item summary is required: {path}")
        items.append(
            AdditionalResearchItem(
                source_path=str(raw_item.get("source_path") or path),
                title=title,
                summary=summary,
                url=_clean(raw_item.get("url")),
                evidence=_clean(raw_item.get("evidence")) or str(path),
            )
        )
    return tuple(items)


def _item_from_text(path: Path) -> AdditionalResearchItem:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    title = _title_from_lines(lines) or path.stem
    summary = _summary_from_text(text)
    if not summary:
        raise ValueError(f"additional research file is empty: {path}")
    return AdditionalResearchItem(
        source_path=str(path),
        title=title,
        summary=summary,
        url=_first_url(text),
        evidence=str(path),
    )


def _title_from_lines(lines: list[str]) -> str | None:
    for line in lines:
        cleaned = line.strip()
        if not cleaned:
            continue
        if cleaned.startswith("#"):
            return cleaned.lstrip("#").strip() or None
        if cleaned.casefold().startswith("source:"):
            continue
        return cleaned
    return None


def _summary_from_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        lines.append(cleaned)
    return _clean(" ".join(lines))


def _first_url(text: str) -> str | None:
    match = re.search(r"https?://[^\s)>\]]+", text)
    if not match:
        return None
    return match.group(0).rstrip(".,;")


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).split())
    return cleaned or None
