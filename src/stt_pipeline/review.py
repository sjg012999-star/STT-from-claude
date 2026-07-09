from __future__ import annotations

import hashlib
import html
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from stt_pipeline.correct import Correction, CorrectionReport
from stt_pipeline.reference_lookup import ReferenceLookupResult


REVIEW_STATUSES = frozenset({"pending", "accepted", "rejected"})


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


def review_items_from_dict(payload: object) -> tuple[ReviewItem, ...]:
    if not isinstance(payload, dict):
        raise ValueError("review queue must be a JSON object")
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("review queue must contain an items array")

    items = []
    seen_ids = set()
    for index, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, dict):
            raise ValueError(f"review item {index} must be a JSON object")
        item_id = _required_review_text(raw_item, "item_id", index)
        if item_id in seen_ids:
            raise ValueError(f"duplicate review item_id: {item_id}")
        seen_ids.add(item_id)

        status = _required_review_text(raw_item, "status", index)
        if status not in REVIEW_STATUSES:
            raise ValueError(f"invalid review status for {item_id}: {status}")
        item_payload = raw_item.get("payload")
        if not isinstance(item_payload, dict):
            raise ValueError(f"review item {item_id} must contain a payload object")

        items.append(
            ReviewItem(
                item_id=item_id,
                kind=_required_review_text(raw_item, "kind", index),
                status=status,
                title=_required_review_text(raw_item, "title", index),
                reason=_required_review_text(raw_item, "reason", index),
                source=_required_review_text(raw_item, "source", index),
                payload=dict(item_payload),
            )
        )
    return tuple(items)


def load_review_queue(path: str | Path) -> tuple[ReviewItem, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return review_items_from_dict(payload)


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


def render_review_html(
    items: tuple[ReviewItem, ...],
    *,
    source_name: str = "review_queue.json",
) -> str:
    items_json = json.dumps(
        [asdict(item) for item in items],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    safe_items_json = (
        items_json.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    cards_html = "\n".join(_render_review_card(item) for item in items)
    if not cards_html:
        cards_html = (
            '<p class="empty-state" id="empty-state">'
            "No review items were found in this queue."
            "</p>"
        )

    return (
        _REVIEW_HTML_TEMPLATE.replace("{{SOURCE_NAME}}", html.escape(source_name))
        .replace("{{ITEM_COUNT}}", str(len(items)))
        .replace("{{CARDS_HTML}}", cards_html)
        .replace("{{ITEMS_JSON}}", safe_items_json)
    )


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


def _required_review_text(raw_item: dict[str, Any], field: str, index: int) -> str:
    value = raw_item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"review item {index} must contain a non-empty {field}")
    return value


def _render_review_card(item: ReviewItem) -> str:
    escaped_id = html.escape(item.item_id, quote=True)
    escaped_kind = html.escape(item.kind)
    escaped_status = html.escape(item.status, quote=True)
    escaped_title = html.escape(item.title)
    escaped_reason = html.escape(item.reason)
    escaped_source = html.escape(item.source)
    escaped_payload = html.escape(
        json.dumps(item.payload, ensure_ascii=False, indent=2, sort_keys=True)
    )
    buttons = "".join(
        (
            '<button type="button" class="decision-button" '
            f'data-decision="{status}" '
            f'aria-pressed="{str(item.status == status).lower()}">'
            f"{label}</button>"
        )
        for status, label in (
            ("accepted", "Accept"),
            ("rejected", "Reject"),
            ("pending", "Pending"),
        )
    )
    return f"""
<article class="review-item" data-item-id="{escaped_id}" data-kind="{escaped_kind}" data-status="{escaped_status}">
  <header class="item-header">
    <span class="kind-label">{escaped_kind}</span>
    <span class="status-label" aria-live="polite">{escaped_status}</span>
  </header>
  <h2>{escaped_title}</h2>
  <p class="reason">{escaped_reason}</p>
  <dl class="source-row">
    <dt>Source</dt>
    <dd>{escaped_source}</dd>
  </dl>
  <details>
    <summary>Evidence details</summary>
    <pre>{escaped_payload}</pre>
  </details>
  <div class="decision-group" role="group" aria-label="Decision for {escaped_title}">
    {buttons}
  </div>
</article>""".strip()


_REVIEW_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>STT Review Queue</title>
  <style>
    :root {
      color-scheme: light;
      font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f4f6f8;
      color: #17202a;
    }
    * { box-sizing: border-box; }
    body { margin: 0; min-width: 320px; }
    button, input, select { font: inherit; letter-spacing: 0; }
    .page-header {
      background: #ffffff;
      border-bottom: 1px solid #d8dee6;
      padding: 28px max(20px, calc((100vw - 1120px) / 2));
    }
    .page-header h1 { margin: 0 0 6px; font-size: 28px; line-height: 1.2; letter-spacing: 0; }
    .page-header p { margin: 0; color: #5b6573; overflow-wrap: anywhere; }
    .workspace { width: min(1120px, calc(100% - 40px)); margin: 24px auto 48px; }
    .toolbar {
      display: grid;
      grid-template-columns: minmax(220px, 1fr) auto;
      gap: 14px;
      align-items: end;
      padding: 0 0 18px;
      border-bottom: 1px solid #cfd6df;
    }
    .filter-controls { display: flex; flex-wrap: wrap; gap: 8px; align-items: end; }
    .search-field { display: grid; gap: 6px; min-width: min(100%, 280px); }
    .search-field span { color: #4f5967; font-size: 13px; font-weight: 650; }
    input[type="search"], select {
      min-height: 40px;
      border: 1px solid #aeb8c4;
      border-radius: 6px;
      background: #ffffff;
      color: #17202a;
      padding: 8px 10px;
    }
    input[type="search"]:focus, select:focus, button:focus-visible, .download-button:focus-visible {
      outline: 3px solid #9bc4ee;
      outline-offset: 1px;
    }
    .toolbar-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
    button {
      min-height: 40px;
      border: 1px solid #9aa6b3;
      border-radius: 6px;
      background: #ffffff;
      color: #1f2933;
      padding: 8px 12px;
      cursor: pointer;
    }
    button:hover { background: #edf1f5; }
    .download-button {
      display: inline-flex;
      min-height: 40px;
      align-items: center;
      justify-content: center;
      border: 1px solid #166534;
      border-radius: 6px;
      background: #166534;
      color: #ffffff;
      padding: 8px 12px;
      font-weight: 700;
      text-decoration: none;
    }
    .download-button:hover { background: #14532d; }
    .counts { display: flex; flex-wrap: wrap; gap: 10px 18px; margin: 18px 0; color: #4f5967; font-size: 14px; }
    .counts strong { color: #17202a; font-variant-numeric: tabular-nums; }
    .queue { display: grid; gap: 12px; }
    .review-item {
      border: 1px solid #c7d0db;
      border-left: 5px solid #b7791f;
      border-radius: 7px;
      background: #ffffff;
      padding: 18px;
      overflow: hidden;
    }
    .review-item[data-status="accepted"] { border-left-color: #16803c; }
    .review-item[data-status="rejected"] { border-left-color: #b42318; }
    .review-item[hidden] { display: none; }
    .item-header { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px; }
    .kind-label { color: #155e75; font-size: 12px; font-weight: 750; text-transform: uppercase; overflow-wrap: anywhere; }
    .status-label { color: #5b6573; font-size: 12px; font-weight: 700; text-transform: uppercase; }
    .review-item h2 { margin: 10px 0 6px; font-size: 19px; line-height: 1.35; overflow-wrap: anywhere; }
    .reason { margin: 0 0 14px; color: #4f5967; line-height: 1.55; }
    .source-row { display: grid; grid-template-columns: 72px minmax(0, 1fr); gap: 8px; margin: 0 0 14px; font-size: 14px; }
    .source-row dt { font-weight: 700; }
    .source-row dd { margin: 0; overflow-wrap: anywhere; }
    details { border-top: 1px solid #e1e6ec; padding-top: 12px; }
    summary { cursor: pointer; font-weight: 650; color: #334155; }
    pre {
      max-height: 280px;
      overflow: auto;
      border: 1px solid #d7dde5;
      border-radius: 5px;
      background: #f7f8fa;
      padding: 12px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      font-size: 12px;
      line-height: 1.5;
    }
    .decision-group { display: grid; grid-template-columns: repeat(3, minmax(80px, 1fr)); gap: 8px; margin-top: 16px; }
    .decision-button[data-decision="accepted"][aria-pressed="true"] { border-color: #16803c; background: #e8f5ec; color: #125c2d; font-weight: 750; }
    .decision-button[data-decision="rejected"][aria-pressed="true"] { border-color: #b42318; background: #fdecea; color: #8f1d14; font-weight: 750; }
    .decision-button[data-decision="pending"][aria-pressed="true"] { border-color: #b7791f; background: #fff7df; color: #7a4e0e; font-weight: 750; }
    .empty-state { border: 1px dashed #aeb8c4; border-radius: 7px; background: #ffffff; padding: 32px; text-align: center; color: #5b6573; }
    .save-state { min-height: 22px; margin: 18px 0 0; color: #5b6573; font-size: 13px; }
    @media (max-width: 760px) {
      .page-header { padding: 22px 20px; }
      .page-header h1 { font-size: 24px; }
      .workspace { width: min(100% - 24px, 1120px); margin-top: 16px; }
      .toolbar { grid-template-columns: 1fr; }
      .toolbar-actions { justify-content: flex-start; }
      .search-field { width: 100%; }
      .search-field input { width: 100%; }
      .review-item { padding: 15px; }
      .decision-group { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header class="page-header">
    <h1>STT Review Queue</h1>
    <p>Source: <strong>{{SOURCE_NAME}}</strong> | {{ITEM_COUNT}} items</p>
  </header>
  <main class="workspace">
    <section class="toolbar" aria-label="Review controls">
      <div class="filter-controls">
        <label class="search-field">
          <span>Search evidence</span>
          <input id="search" type="search" placeholder="Title, source, term, or DOI">
        </label>
        <label class="search-field">
          <span>Status</span>
          <select id="status-filter">
            <option value="all">All statuses</option>
            <option value="pending">Pending</option>
            <option value="accepted">Accepted</option>
            <option value="rejected">Rejected</option>
          </select>
        </label>
      </div>
      <div class="toolbar-actions">
        <button type="button" data-bulk="accepted">Accept visible</button>
        <button type="button" data-bulk="rejected">Reject visible</button>
        <a class="download-button" id="download" download="review_decisions.json" href="#">Download decisions</a>
      </div>
    </section>
    <div class="counts" aria-live="polite">
      <span>Total <strong id="count-total">0</strong></span>
      <span>Visible <strong id="count-visible">0</strong></span>
      <span>Pending <strong id="count-pending">0</strong></span>
      <span>Accepted <strong id="count-accepted">0</strong></span>
      <span>Rejected <strong id="count-rejected">0</strong></span>
    </div>
    <section class="queue" id="queue" aria-label="Review items">
      {{CARDS_HTML}}
    </section>
    <p class="save-state" id="save-state" role="status">Decisions are kept in this page until downloaded.</p>
  </main>
  <script type="application/json" id="review-data">{{ITEMS_JSON}}</script>
  <script>
    const items = JSON.parse(document.getElementById("review-data").textContent);
    const itemsById = new Map(items.map((item) => [item.item_id, item]));
    const cards = Array.from(document.querySelectorAll(".review-item"));
    const searchInput = document.getElementById("search");
    const statusFilter = document.getElementById("status-filter");
    const saveState = document.getElementById("save-state");
    const downloadLink = document.getElementById("download");

    function updateCounts() {
      document.getElementById("count-total").textContent = String(items.length);
      document.getElementById("count-visible").textContent = String(cards.filter((card) => !card.hidden).length);
      for (const status of ["pending", "accepted", "rejected"]) {
        document.getElementById(`count-${status}`).textContent = String(items.filter((item) => item.status === status).length);
      }
    }

    function applyFilters() {
      const query = searchInput.value.trim().toLocaleLowerCase();
      const selectedStatus = statusFilter.value;
      for (const card of cards) {
        const matchesText = !query || card.textContent.toLocaleLowerCase().includes(query);
        const matchesStatus = selectedStatus === "all" || card.dataset.status === selectedStatus;
        card.hidden = !(matchesText && matchesStatus);
      }
      updateCounts();
    }

    function refreshDownloadLink() {
      const decisionsJson = JSON.stringify({ items }, null, 2) + "\\n";
      downloadLink.href = `data:application/json;charset=utf-8,${encodeURIComponent(decisionsJson)}`;
    }

    function setDecision(card, status) {
      const item = itemsById.get(card.dataset.itemId);
      if (!item || !["pending", "accepted", "rejected"].includes(status)) return;
      item.status = status;
      card.dataset.status = status;
      card.querySelector(".status-label").textContent = status;
      for (const button of card.querySelectorAll("[data-decision]")) {
        button.setAttribute("aria-pressed", String(button.dataset.decision === status));
      }
      saveState.textContent = "Decisions changed. Download the JSON file to save them.";
      applyFilters();
      refreshDownloadLink();
    }

    document.getElementById("queue").addEventListener("click", (event) => {
      const button = event.target.closest("[data-decision]");
      if (!button) return;
      const card = button.closest(".review-item");
      if (card) setDecision(card, button.dataset.decision);
    });

    for (const button of document.querySelectorAll("[data-bulk]")) {
      button.addEventListener("click", () => {
        for (const card of cards.filter((candidate) => !candidate.hidden)) {
          setDecision(card, button.dataset.bulk);
        }
      });
    }

    searchInput.addEventListener("input", applyFilters);
    statusFilter.addEventListener("change", applyFilters);

    downloadLink.addEventListener("click", () => {
      saveState.textContent = "Download started for review_decisions.json.";
    });

    refreshDownloadLink();
    applyFilters();
  </script>
</body>
</html>
"""
