from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from stt_pipeline.conference_context import (
    ConferenceArchive,
    RecordingManifestEntry,
    build_conference_context,
)
from stt_pipeline.correct import Correction, apply_declared_corrections
from stt_pipeline.transcript import TranscriptResult, TranscriptSegment


VERSION_NAME = "V1_conference_aware"
_CONFIDENCE_RANK = {"low": 1, "medium": 2, "high": 3}
_ALIGNMENT_STATUSES = {"confirmed", "likely", "boundary", "not_present", "uncertain"}


def generate_conference_correction_jobs(
    output_roots: Iterable[str | Path],
    *,
    archive: ConferenceArchive,
    manifest_entries: Iterable[RecordingManifestEntry] = (),
    version_name: str = VERSION_NAME,
    batch_index_path: str | Path | None = None,
) -> dict[str, object]:
    roots = tuple(Path(root).resolve() for root in output_roots)
    manifest_entries = tuple(manifest_entries)
    jobs = []
    for root in roots:
        transcript_paths = sorted((root / "sessions").glob("*/transcript.json"))
        version_root = root / "versions" / version_name
        jobs_dir = version_root / "jobs"
        responses_dir = version_root / "responses"
        jobs_dir.mkdir(parents=True, exist_ok=True)
        responses_dir.mkdir(parents=True, exist_ok=True)
        for transcript_path in transcript_paths:
            result = load_transcript_result(transcript_path)
            session_name = transcript_path.parent.name
            context = build_conference_context(
                session_name,
                result.text,
                archive=archive,
                manifest_entries=manifest_entries,
            )
            job = build_conference_correction_job(
                transcript_path,
                result,
                context,
                output_root=root,
                version_name=version_name,
            )
            job_path = jobs_dir / f"{session_name}.json"
            response_path = responses_dir / f"{session_name}.json"
            _write_json(job_path, job)
            jobs.append(
                {
                    "job_id": job["job_id"],
                    "session_name": session_name,
                    "date_root": root.name,
                    "job_path": str(job_path),
                    "response_path": str(response_path),
                    "status": "response_ready" if response_path.is_file() else "pending",
                }
            )

    if batch_index_path is None:
        if not roots:
            raise ValueError("at least one output root is required")
        batch_index = roots[0].parent / f"{version_name}_jobs.json"
    else:
        batch_index = Path(batch_index_path).resolve()
    payload = {
        "schema_version": 1,
        "version": version_name,
        "job_count": len(jobs),
        "output_roots": [str(root) for root in roots],
        "jobs": jobs,
    }
    _write_json(batch_index, payload)
    return {**payload, "batch_index_path": str(batch_index)}


def build_conference_correction_job(
    transcript_path: str | Path,
    result: TranscriptResult,
    conference_context: dict[str, object],
    *,
    output_root: str | Path,
    version_name: str = VERSION_NAME,
) -> dict[str, object]:
    source = Path(transcript_path).resolve()
    session_name = source.parent.name
    job_id = hashlib.sha256(
        f"{Path(output_root).resolve()}::{session_name}::{_sha256(source)}".encode("utf-8")
    ).hexdigest()[:20]
    evidence_catalog = list(conference_context.get("evidence_catalog", []))
    evidence_catalog.extend(
        {
            "evidence_id": f"transcript:{segment.segment_id}",
            "kind": "speaker_transcript",
            "source": source.name,
        }
        for segment in result.segments
    )
    context_with_transcript_evidence = {
        **conference_context,
        "evidence_catalog": evidence_catalog,
    }
    return {
        "schema_version": 1,
        "job_id": job_id,
        "version": version_name,
        "source_version": "V0_raw",
        "source_transcript": str(source),
        "source_sha256": _sha256(source),
        "session_name": session_name,
        "instructions": [
            "Correct only clear automatic speech-recognition errors; do not rewrite style or add facts.",
            "Use the full event, session, presentation, speaker, and neighboring-talk context together.",
            "The official schedule is planned context, not ground truth. Spoken introductions and transitions override it when they conflict.",
            "Every original value must be a non-empty exact substring of the declared transcript segment.",
            "Use high confidence for directly supported names/titles/terms, medium for strong contextual reconstruction, and low when uncertain.",
            "Do not use slide photos, PDFs, references, web search, or other material evidence in this version.",
            "Return every proposed change separately with one or more evidence_id values from the supplied catalog.",
            "Report likely presentation identity and recording boundaries separately from text corrections.",
        ],
        "evidence_policy": {
            "allowed": [
                "V0 transcript and adjacent transcript segments",
                "recording filename and recording-match manifest",
                "CRS event, session, presentation, speaker, and neighboring-talk schedule context",
            ],
            "excluded": [
                "slide photos or slide decks",
                "PDFs, cited references, and figure/table crops",
                "web search and external research",
                "paid Platform API post-processing",
            ],
            "priority": [
                "explicit spoken introduction or transition",
                "transcript syntax and repeated internal usage",
                "official presentation title and presenter",
                "session focus and neighboring presentations",
                "recording filename or planned clock time",
            ],
        },
        "response_contract": {
            "job_id": "must equal this job_id",
            "processor": {
                "surface": "Codex",
                "authentication": "ChatGPT OAuth",
                "model": "model name used by the active Codex task",
            },
            "presentation_alignment": [
                {
                    "presentation_id": "ID from matched or alternative session presentations",
                    "status": "confirmed | likely | boundary | not_present | uncertain",
                    "confidence": "high | medium | low",
                    "evidence_refs": ["evidence_id"],
                    "reason": "concise reason",
                }
            ],
            "corrections": [
                {
                    "segment_id": "source segment ID",
                    "original": "exact source substring",
                    "corrected": "replacement text",
                    "reason": "concise ASR-specific reason",
                    "confidence": "high | medium | low",
                    "evidence_refs": ["evidence_id"],
                }
            ],
            "notes": ["optional concise audit note"],
        },
        "conference_context": context_with_transcript_evidence,
        "transcript": {
            "provider": result.provider,
            "model": result.model,
            "profile": result.profile,
            "segments": [asdict(segment) for segment in result.segments],
        },
    }


def apply_conference_correction_responses(
    output_roots: Iterable[str | Path],
    *,
    version_name: str = VERSION_NAME,
    minimum_confidence: str = "medium",
    require_all_responses: bool = False,
) -> dict[str, object]:
    minimum = minimum_confidence.casefold()
    if minimum not in _CONFIDENCE_RANK:
        raise ValueError("minimum_confidence must be high, medium, or low")

    roots = tuple(Path(root).resolve() for root in output_roots)
    totals = {
        "job_count": 0,
        "response_count": 0,
        "applied_count": 0,
        "withheld_count": 0,
        "rejected_count": 0,
        "missing_response_count": 0,
    }
    root_summaries = []
    for root in roots:
        version_root = root / "versions" / version_name
        jobs = sorted((version_root / "jobs").glob("*.json"))
        totals["job_count"] += len(jobs)
        for job_path in jobs:
            response_path = version_root / "responses" / job_path.name
            if not response_path.is_file():
                totals["missing_response_count"] += 1
                if require_all_responses:
                    raise FileNotFoundError(f"missing conference correction response: {response_path}")
                continue
            manifest = apply_conference_correction_response(
                job_path,
                response_path,
                output_root=root,
                version_name=version_name,
                minimum_confidence=minimum,
            )
            totals["response_count"] += 1
            totals["applied_count"] += int(manifest["applied_count"])
            totals["withheld_count"] += int(manifest["withheld_count"])
            totals["rejected_count"] += int(manifest["rejected_count"])
        root_summary = build_conference_version_index(root, version_name=version_name)
        root_summaries.append(root_summary)
    return {
        "schema_version": 1,
        "version": version_name,
        "minimum_confidence": minimum,
        **totals,
        "roots": root_summaries,
    }


def apply_conference_correction_response(
    job_path: str | Path,
    response_path: str | Path,
    *,
    output_root: str | Path,
    version_name: str = VERSION_NAME,
    minimum_confidence: str = "medium",
) -> dict[str, object]:
    job_source = Path(job_path)
    response_source = Path(response_path)
    root = Path(output_root).resolve()
    job = json.loads(job_source.read_text(encoding="utf-8"))
    response = json.loads(response_source.read_text(encoding="utf-8"))
    if str(response.get("job_id", "")) != str(job.get("job_id", "")):
        raise ValueError(f"response job_id does not match {job_source.name}")
    _validate_processor(response.get("processor"))
    raw_corrections = response.get("corrections", [])
    if not isinstance(raw_corrections, list):
        raise ValueError("response corrections must be a list")
    raw_alignment = response.get("presentation_alignment", [])
    if not isinstance(raw_alignment, list):
        raise ValueError("response presentation_alignment must be a list")

    transcript_path = Path(str(job["source_transcript"])).resolve()
    sessions_root = (root / "sessions").resolve()
    if not transcript_path.is_relative_to(sessions_root):
        raise ValueError("job source transcript is outside the selected V0 sessions root")
    current_source_hash = _sha256(transcript_path)
    if current_source_hash != str(job.get("source_sha256", "")):
        raise ValueError(f"V0 transcript changed after job creation: {transcript_path}")

    result = load_transcript_result(transcript_path)
    segment_text = {segment.segment_id: segment.text for segment in result.segments}
    known_evidence = {
        str(item.get("evidence_id", ""))
        for item in job.get("conference_context", {}).get("evidence_catalog", [])
    }
    accepted = []
    withheld = []
    rejected = []
    normalized_proposals = []
    seen = set()
    for index, raw in enumerate(raw_corrections, start=1):
        proposal = _normalize_proposal(raw, index=index)
        errors = _validate_proposal(
            proposal,
            segment_text=segment_text,
            known_evidence=known_evidence,
        )
        proposal_key = (
            proposal["segment_id"],
            proposal["original"],
            proposal["corrected"],
        )
        if proposal_key in seen:
            errors.append("duplicate correction proposal")
        seen.add(proposal_key)
        if errors:
            proposal["status"] = "rejected"
            proposal["validation_errors"] = errors
            rejected.append(proposal)
        elif _CONFIDENCE_RANK[proposal["confidence"]] < _CONFIDENCE_RANK[minimum_confidence]:
            proposal["status"] = "withheld_below_confidence_threshold"
            withheld.append(proposal)
        else:
            proposal["status"] = "accepted_for_exact_apply"
            accepted.append(proposal)
        normalized_proposals.append(proposal)

    declared = tuple(
        Correction(
            segment_id=item["segment_id"],
            original=item["original"],
            corrected=item["corrected"],
            reason=item["reason"],
            confidence=item["confidence"],
        )
        for item in accepted
    )
    report = apply_declared_corrections(result, declared)
    applied_keys = {
        (item.segment_id, item.original, item.corrected)
        for item in report.applied_corrections
    }
    final_applied = []
    for proposal in accepted:
        key = (proposal["segment_id"], proposal["original"], proposal["corrected"])
        if key in applied_keys:
            proposal["status"] = "applied"
            final_applied.append(proposal)
        else:
            proposal["status"] = "rejected_during_exact_apply"
            proposal["validation_errors"] = ["source substring unavailable after prior changes"]
            rejected.append(proposal)

    alignment = _validate_alignment(raw_alignment, job)
    session_name = str(job["session_name"])
    destination = root / "versions" / version_name / "sessions" / session_name
    destination.mkdir(parents=True, exist_ok=True)
    corrected_payload = asdict(report.corrected_result)
    _write_json(destination / "transcript.json", corrected_payload)
    _write_corrected_markdown(
        destination / "transcript.md",
        report.corrected_result,
        version_name=version_name,
        applied_count=len(final_applied),
    )
    _write_json(destination / "conference_context.json", job["conference_context"])
    _write_json(destination / "model_response.json", response)
    corrections_payload = {
        "schema_version": 1,
        "version": version_name,
        "source_version": "V0_raw",
        "minimum_confidence": minimum_confidence,
        "processor": response.get("processor", {}),
        "presentation_alignment": alignment,
        "applied": final_applied,
        "withheld": withheld,
        "rejected": rejected,
        "all_proposals": normalized_proposals,
        "notes": response.get("notes", []),
    }
    _write_json(destination / "corrections.json", corrections_payload)
    _write_comparison(
        destination / "comparison_v0_vs_v1.md",
        session_name,
        corrections_payload,
        job["conference_context"],
    )
    source_hash_after = _sha256(transcript_path)
    if source_hash_after != current_source_hash:
        raise RuntimeError(f"V0 transcript was modified while applying corrections: {transcript_path}")
    version_manifest = {
        "schema_version": 1,
        "version": version_name,
        "source_version": "V0_raw",
        "source_transcript": str(transcript_path),
        "source_sha256_before": current_source_hash,
        "source_sha256_after": source_hash_after,
        "source_unchanged": True,
        "job_id": job["job_id"],
        "job_path": str(job_source.resolve()),
        "response_path": str(response_source.resolve()),
        "minimum_confidence": minimum_confidence,
        "proposal_count": len(normalized_proposals),
        "applied_count": len(final_applied),
        "withheld_count": len(withheld),
        "rejected_count": len(rejected),
        "alignment_count": len(alignment),
    }
    _write_json(destination / "version_manifest.json", version_manifest)
    return version_manifest


def build_conference_version_index(
    output_root: str | Path,
    *,
    version_name: str = VERSION_NAME,
) -> dict[str, object]:
    root = Path(output_root).resolve()
    version_root = root / "versions" / version_name
    manifests = sorted((version_root / "sessions").glob("*/version_manifest.json"))
    totals = {"applied": 0, "withheld": 0, "rejected": 0}
    index_lines = [
        f"# {root.name} - {version_name}",
        "",
        "- Source: `V0_raw` (preserved and SHA-256 checked)",
        "- Context: CRS event, session, presentation, speaker, and adjacent-talk schedule",
        "- Excluded: slides, PDFs, references, web research, and paid post-processing APIs",
        "- Application: exact source match with high/medium confidence by default",
        "",
    ]
    combined_lines = [f"# {root.name} - Conference-Aware Corrected Transcript", ""]
    comparison_lines = [
        f"# {root.name} - V0 vs {version_name}",
        "",
        "| Recording | Applied | Withheld | Rejected | V0 unchanged |",
        "|---|---:|---:|---:|---|",
    ]
    review_lines = [
        f"# {root.name} - Conference-Aware Review Queue",
        "",
        "Low-confidence, invalid, ambiguous, and medium-confidence spot-check items are listed here.",
        "",
    ]
    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        session_dir = manifest_path.parent
        corrections = json.loads((session_dir / "corrections.json").read_text(encoding="utf-8"))
        transcript = json.loads((session_dir / "transcript.json").read_text(encoding="utf-8"))
        context = json.loads((session_dir / "conference_context.json").read_text(encoding="utf-8"))
        totals["applied"] += int(manifest["applied_count"])
        totals["withheld"] += int(manifest["withheld_count"])
        totals["rejected"] += int(manifest["rejected_count"])
        relative = session_dir.relative_to(version_root)
        index_lines.append(
            f"- **{session_dir.name}** - applied {manifest['applied_count']}, "
            f"withheld {manifest['withheld_count']}, rejected {manifest['rejected_count']}: "
            f"[transcript]({relative}/transcript.md) | "
            f"[comparison]({relative}/comparison_v0_vs_v1.md)"
        )
        combined_lines.extend([f"## {session_dir.name}", "", str(transcript["text"]).strip(), ""])
        comparison_lines.append(
            f"| {_escape_table(session_dir.name)} | {manifest['applied_count']} | "
            f"{manifest['withheld_count']} | {manifest['rejected_count']} | "
            f"{'yes' if manifest.get('source_unchanged') else 'NO'} |"
        )
        review_items = [
            item
            for item in corrections.get("applied", [])
            if item.get("confidence") == "medium"
        ] + list(corrections.get("withheld", [])) + list(corrections.get("rejected", []))
        warnings = context.get("match", {}).get("warnings", [])
        if review_items or warnings:
            review_lines.extend([f"## {session_dir.name}", ""])
            for warning in warnings:
                review_lines.append(
                    f"- Context warning `{warning.get('code', 'unknown')}`: "
                    f"{warning.get('message', '')}"
                )
            for item in review_items:
                review_lines.append(
                    f"- `{item.get('status', 'review')}` / `{item.get('confidence', '')}` / "
                    f"`{item.get('segment_id', '')}`: "
                    f"{_escape_inline(item.get('original', ''))} -> "
                    f"{_escape_inline(item.get('corrected', ''))}"
                )
            review_lines.append("")

    index_lines[7:7] = [
        f"- Completed recordings: **{len(manifests)}**",
        f"- Applied corrections: **{totals['applied']}**",
        f"- Withheld corrections: **{totals['withheld']}**",
        f"- Rejected corrections: **{totals['rejected']}**",
        "",
    ]
    version_root.mkdir(parents=True, exist_ok=True)
    (version_root / "index.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    (version_root / "combined_transcript.md").write_text(
        "\n".join(combined_lines) + "\n", encoding="utf-8"
    )
    (version_root / "comparison_overview.md").write_text(
        "\n".join(comparison_lines) + "\n", encoding="utf-8"
    )
    (version_root / "review_queue.md").write_text(
        "\n".join(review_lines) + "\n", encoding="utf-8"
    )
    summary = {
        "version": version_name,
        "completed": len(manifests),
        **totals,
    }
    _write_json(version_root / "summary.json", summary)
    return {"output_root": str(root), **summary}


def load_transcript_result(path: str | Path) -> TranscriptResult:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return TranscriptResult(
        provider=str(payload["provider"]),
        model=str(payload["model"]),
        profile=str(payload["profile"]),
        text=str(payload["text"]),
        segments=tuple(TranscriptSegment(**item) for item in payload["segments"]),
        usage_seconds=payload.get("usage_seconds"),
    )


def _normalize_proposal(raw: object, *, index: int) -> dict[str, object]:
    value = raw if isinstance(raw, dict) else {}
    evidence_refs = value.get("evidence_refs", [])
    if not isinstance(evidence_refs, list):
        evidence_refs = []
    return {
        "proposal_id": f"c{index:04d}",
        "segment_id": str(value.get("segment_id", "")),
        "original": str(value.get("original", "")),
        "corrected": str(value.get("corrected", "")),
        "reason": str(value.get("reason", "")),
        "confidence": str(value.get("confidence", "")).casefold(),
        "evidence_refs": [str(item) for item in evidence_refs],
    }


def _validate_processor(raw_processor: object) -> None:
    if not isinstance(raw_processor, dict):
        raise ValueError("response processor metadata must be an object")
    if str(raw_processor.get("surface", "")).strip().casefold() != "codex":
        raise ValueError("response processor surface must be Codex")
    if (
        str(raw_processor.get("authentication", "")).strip().casefold()
        != "chatgpt oauth"
    ):
        raise ValueError("response processor authentication must be ChatGPT OAuth")
    if not str(raw_processor.get("model", "")).strip():
        raise ValueError("response processor model must be non-empty")


def _validate_proposal(
    proposal: dict[str, object],
    *,
    segment_text: dict[str, str],
    known_evidence: set[str],
) -> list[str]:
    errors = []
    segment_id = str(proposal["segment_id"])
    original = str(proposal["original"])
    corrected = str(proposal["corrected"])
    confidence = str(proposal["confidence"])
    evidence_refs = [str(item) for item in proposal["evidence_refs"]]
    if segment_id not in segment_text:
        errors.append("unknown segment_id")
    if not original:
        errors.append("original must be non-empty")
    elif segment_id in segment_text and original not in segment_text[segment_id]:
        errors.append("original is not an exact substring of the source segment")
    if not corrected:
        errors.append("corrected must be non-empty")
    if original == corrected:
        errors.append("original and corrected are identical")
    if len(original) > 500 or len(corrected) > 500:
        errors.append("correction exceeds the 500-character safety limit")
    if confidence not in _CONFIDENCE_RANK:
        errors.append("confidence must be high, medium, or low")
    if not str(proposal["reason"]).strip():
        errors.append("reason must be non-empty")
    if not evidence_refs:
        errors.append("at least one evidence_ref is required")
    unknown_refs = [item for item in evidence_refs if item not in known_evidence]
    if unknown_refs:
        errors.append(f"unknown evidence_refs: {', '.join(unknown_refs)}")
    transcript_ref = f"transcript:{segment_id}"
    if segment_id in segment_text and transcript_ref not in evidence_refs:
        errors.append(f"evidence_refs must include {transcript_ref}")
    return errors


def _validate_alignment(raw_alignment: object, job: dict[str, object]) -> list[dict[str, object]]:
    match_context = job.get("conference_context", {}).get("match", {})
    session_candidates = [match_context.get("matched_session", {})]
    session_candidates.extend(
        item.get("session", {})
        for item in match_context.get("alternative_session_candidates", [])
    )
    valid_ids = {
        str(session.get("presentation_id", ""))
        for session in session_candidates
        if session.get("presentation_id")
    }
    valid_ids.update(
        str(item.get("presentation_id", ""))
        for session in session_candidates
        for item in session.get("presentations", [])
        if item.get("presentation_id")
    )
    known_evidence = {
        str(item.get("evidence_id", ""))
        for item in job.get("conference_context", {}).get("evidence_catalog", [])
    }
    if not isinstance(raw_alignment, list):
        return []
    result = []
    for raw in raw_alignment:
        item = raw if isinstance(raw, dict) else {}
        presentation_id = str(item.get("presentation_id", ""))
        refs = item.get("evidence_refs", [])
        refs = [str(value) for value in refs] if isinstance(refs, list) else []
        status = str(item.get("status", "uncertain")).casefold()
        errors = []
        if presentation_id not in valid_ids:
            errors.append("presentation_id is not in the matched session schedule")
        if status not in _ALIGNMENT_STATUSES:
            errors.append("invalid alignment status")
        if str(item.get("confidence", "")).casefold() not in _CONFIDENCE_RANK:
            errors.append("invalid confidence")
        if not refs:
            errors.append("at least one evidence_ref is required")
        unknown_refs = [ref for ref in refs if ref not in known_evidence]
        if unknown_refs:
            errors.append(f"unknown evidence_refs: {', '.join(unknown_refs)}")
        if not str(item.get("reason", "")).strip():
            errors.append("reason must be non-empty")
        result.append(
            {
                "presentation_id": presentation_id,
                "status": status,
                "confidence": str(item.get("confidence", "low")).casefold(),
                "evidence_refs": refs,
                "reason": str(item.get("reason", "")),
                "validation_status": "valid" if not errors else "invalid",
                "validation_errors": errors,
            }
        )
    return result


def _write_corrected_markdown(
    path: Path,
    result: TranscriptResult,
    *,
    version_name: str,
    applied_count: int,
) -> None:
    lines = [
        f"# Corrected Transcript - {version_name}",
        "",
        "- Source: `V0_raw` (unchanged)",
        f"- STT model: `{result.model}`",
        "- Correction processor: active Codex task using ChatGPT OAuth",
        "- Context: CRS schedule plus transcript introductions and transitions",
        "- Materials/references/web: **not used**",
        f"- Applied exact-match corrections: **{applied_count}**",
        "",
        "## Segments",
        "",
    ]
    for segment in result.segments:
        lines.append(f"- `{segment.segment_id}` {segment.text}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_comparison(
    path: Path,
    session_name: str,
    corrections: dict[str, object],
    context: dict[str, object],
) -> None:
    applied = list(corrections.get("applied", []))
    withheld = list(corrections.get("withheld", []))
    rejected = list(corrections.get("rejected", []))
    lines = [
        f"# V0 vs V1 Conference-Aware - {session_name}",
        "",
        f"- Applied: **{len(applied)}**",
        f"- Withheld: **{len(withheld)}**",
        f"- Rejected by validation: **{len(rejected)}**",
        "",
        "## Context Warnings",
        "",
    ]
    for warning in context.get("match", {}).get("warnings", []):
        lines.append(f"- `{warning.get('code', '')}`: {warning.get('message', '')}")
    if not context.get("match", {}).get("warnings", []):
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Applied Corrections",
            "",
            "| Confidence | Segment | Original | Corrected | Evidence | Reason |",
            "|---|---|---|---|---|---|",
        ]
    )
    for item in applied:
        lines.append(
            f"| {_escape_table(item.get('confidence', ''))} | "
            f"{_escape_table(item.get('segment_id', ''))} | "
            f"{_escape_table(item.get('original', ''))} | "
            f"{_escape_table(item.get('corrected', ''))} | "
            f"{_escape_table(', '.join(item.get('evidence_refs', [])))} | "
            f"{_escape_table(item.get('reason', ''))} |"
        )
    if not applied:
        lines.append("| - | - | - | - | - | No correction applied |")
    lines.extend(["", "## Withheld Or Rejected", ""])
    for item in withheld + rejected:
        errors = "; ".join(item.get("validation_errors", []))
        lines.append(
            f"- `{item.get('status', '')}` `{item.get('segment_id', '')}`: "
            f"{_escape_inline(item.get('original', ''))} -> "
            f"{_escape_inline(item.get('corrected', ''))}"
            + (f" ({errors})" if errors else "")
        )
    if not withheld and not rejected:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _escape_table(value: object) -> str:
    return " ".join(str(value).split()).replace("|", "\\|")


def _escape_inline(value: object) -> str:
    return " ".join(str(value).split()).replace("`", "'")
