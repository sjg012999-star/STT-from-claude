from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


_RECORDING_NAME = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})_(?P<hour>\d{2})(?P<minute>\d{2})_(?P<label>.+)$"
)
_ARCHIVE_DATE = re.compile(
    r"^[A-Za-z]+,\s+(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2}),\s+(?P<year>\d{4})$"
)
_CLOCK_TIME = re.compile(r"(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<period>AM|PM)", re.I)
_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "at",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "into",
    "is",
    "it",
    "not",
    "of",
    "on",
    "or",
    "part",
    "presentation",
    "session",
    "speaker",
    "the",
    "that",
    "this",
    "to",
    "using",
    "via",
    "with",
    "workshop",
}
_TOKEN_ALIASES = {
    "ibd": ("inflammatory", "bowel", "disease"),
    "lai": ("long", "acting", "injectable"),
    "lnp": ("lipid", "nanoparticle"),
    "mfg": ("manufacturing",),
    "nano": ("nanomedicine", "nanoscale"),
    "pk": ("pharmacokinetic",),
    "techforum": ("technical", "forum"),
}
_ROMAN_NUMERALS = {
    "i",
    "ii",
    "iii",
    "iv",
    "v",
    "vi",
    "vii",
    "viii",
    "ix",
    "x",
    "xi",
    "xii",
}


@dataclass(frozen=True)
class ConferencePresentation:
    presentation_id: str
    time: str
    title: str
    presenters: tuple[str, ...]
    start_minute: int | None
    end_minute: int | None


@dataclass(frozen=True)
class ConferenceSession:
    presentation_id: str
    date: str
    time: str
    title: str
    categories: tuple[str, ...]
    abstract: str
    source_url: str
    start_minute: int | None
    end_minute: int | None
    presentations: tuple[ConferencePresentation, ...]


@dataclass(frozen=True)
class ConferenceArchive:
    source_path: str
    generated_at: str
    agenda_url: str
    sessions: tuple[ConferenceSession, ...]


@dataclass(frozen=True)
class RecordingManifestEntry:
    source_name: str
    target_name: str
    local_start: str
    duration: str
    confidence: str
    note: str
    status: str


@dataclass(frozen=True)
class RecordingDescriptor:
    name: str
    date: str
    start_minute: int
    label: str


def load_conference_archive(path: str | Path) -> ConferenceArchive:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    sessions = []
    for raw in payload.get("sessions", []):
        date = _parse_archive_date(str(raw.get("date", "")))
        if not date:
            continue
        detail = raw.get("detail") or {}
        presentations = []
        for raw_presentation in detail.get("presentations", []):
            start_minute, end_minute = _parse_time_range(
                str(raw_presentation.get("time", ""))
            )
            presentations.append(
                ConferencePresentation(
                    presentation_id=str(raw_presentation.get("presentation_id", "")),
                    time=str(raw_presentation.get("time", "")),
                    title=_clean_text(raw_presentation.get("title", "")),
                    presenters=tuple(
                        _clean_text(value)
                        for value in raw_presentation.get("presenters", [])
                        if _clean_text(value)
                    ),
                    start_minute=start_minute,
                    end_minute=end_minute,
                )
            )
        start_minute, end_minute = _parse_time_range(str(raw.get("time", "")))
        sessions.append(
            ConferenceSession(
                presentation_id=str(raw.get("presentation_id", "")),
                date=date,
                time=str(raw.get("time", "")),
                title=_clean_text(raw.get("title", "")),
                categories=tuple(
                    _clean_text(value)
                    for value in raw.get("categories", [])
                    if _clean_text(value)
                ),
                abstract=_clean_text(detail.get("abstract", "")),
                source_url=str(raw.get("source_url", "")),
                start_minute=start_minute,
                end_minute=end_minute,
                presentations=tuple(presentations),
            )
        )
    return ConferenceArchive(
        source_path=str(source.resolve()),
        generated_at=str(payload.get("generated_at", "")),
        agenda_url=str(payload.get("agenda_url", "")),
        sessions=tuple(sessions),
    )


def load_recording_manifest(path: str | Path | None) -> tuple[RecordingManifestEntry, ...]:
    if path is None:
        return ()
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"recording manifest not found: {source}")
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle, delimiter="\t")
        return tuple(
            RecordingManifestEntry(
                source_name=str(row.get("source_name", "")),
                target_name=str(row.get("target_name", "")),
                local_start=str(row.get("lisbon_start_WEST", "")),
                duration=str(row.get("duration", "")),
                confidence=str(row.get("confidence", "")),
                note=str(row.get("note", "")),
                status=str(row.get("status", "")),
            )
            for row in rows
        )


def build_conference_context(
    recording_name: str,
    transcript_text: str,
    *,
    archive: ConferenceArchive,
    manifest_entries: Iterable[RecordingManifestEntry] = (),
) -> dict[str, object]:
    descriptor = parse_recording_descriptor(recording_name)
    manifest_entry = find_manifest_entry(recording_name, manifest_entries)
    session_scores = _score_sessions(
        descriptor,
        transcript_text,
        archive.sessions,
        manifest_entry=manifest_entry,
    )
    if not session_scores:
        raise ValueError(f"no conference session found for recording date {descriptor.date}")

    best_score, matched_session, session_reasons = session_scores[0]
    second_score = session_scores[1][0] if len(session_scores) > 1 else None
    session_confidence = _session_confidence(best_score, second_score)
    session_margin = best_score - second_score if second_score is not None else best_score
    include_alternatives = (
        session_confidence != "high"
        or session_margin < 20
        or bool(manifest_entry and manifest_entry.confidence.casefold() != "high")
        or bool(manifest_entry and "check" in manifest_entry.target_name.casefold())
    )
    context_session_scores = session_scores[:5] if include_alternatives else session_scores[:1]
    presentation_candidates = _score_presentations(
        descriptor,
        transcript_text,
        matched_session,
        manifest_entry=manifest_entry,
    )
    warnings = _build_warnings(
        descriptor,
        matched_session,
        session_scores,
        presentation_candidates,
        manifest_entry,
    )
    evidence_catalog = _build_evidence_catalog(
        descriptor,
        archive,
        tuple(item[1] for item in context_session_scores),
        manifest_entry,
    )

    return {
        "schema_version": 1,
        "event": {
            "name": "CRS 2026 Annual Meeting & Exposition",
            "timezone": "WEST",
            "agenda_url": archive.agenda_url,
            "archive_generated_at": archive.generated_at,
            "archive_source": archive.source_path,
        },
        "recording": {
            **asdict(descriptor),
            "start_time": _format_minute(descriptor.start_minute),
            "manifest": asdict(manifest_entry) if manifest_entry else None,
        },
        "match": {
            "session_confidence": session_confidence,
            "session_score": round(best_score, 3),
            "session_score_margin": (
                round(session_margin, 3) if second_score is not None else None
            ),
            "session_reasons": list(session_reasons),
            "matched_session": conference_session_to_dict(matched_session),
            "alternative_session_candidates": [
                {
                    "score": round(score, 3),
                    "reasons": list(reasons),
                    "session": conference_session_to_dict(session),
                }
                for score, session, reasons in context_session_scores[1:]
            ],
            "presentation_candidates": presentation_candidates,
            "warnings": warnings,
        },
        "evidence_catalog": evidence_catalog,
    }


def parse_recording_descriptor(recording_name: str) -> RecordingDescriptor:
    stem = Path(recording_name).stem
    match = _RECORDING_NAME.match(stem)
    if not match:
        raise ValueError(
            "recording name must begin with YYYY-MM-DD_HHMM_: " f"{recording_name}"
        )
    start_minute = int(match.group("hour")) * 60 + int(match.group("minute"))
    return RecordingDescriptor(
        name=stem,
        date=match.group("date"),
        start_minute=start_minute,
        label=_clean_recording_label(match.group("label")),
    )


def find_manifest_entry(
    recording_name: str,
    entries: Iterable[RecordingManifestEntry],
) -> RecordingManifestEntry | None:
    wanted = _normalized_stem(recording_name)
    for entry in entries:
        if wanted in {
            _normalized_stem(entry.source_name),
            _normalized_stem(entry.target_name),
        }:
            return entry
    return None


def conference_session_to_dict(session: ConferenceSession) -> dict[str, object]:
    return {
        "evidence_id": f"conference.session:{session.presentation_id}",
        "presentation_id": session.presentation_id,
        "date": session.date,
        "time": session.time,
        "title": session.title,
        "categories": list(session.categories),
        "abstract": session.abstract,
        "source_url": session.source_url,
        "presentations": [
            {
                "evidence_id": f"conference.presentation:{item.presentation_id}",
                "presentation_id": item.presentation_id,
                "time": item.time,
                "title": item.title,
                "presenters": list(item.presenters),
            }
            for item in session.presentations
        ],
    }


def _score_sessions(
    descriptor: RecordingDescriptor,
    transcript_text: str,
    sessions: tuple[ConferenceSession, ...],
    *,
    manifest_entry: RecordingManifestEntry | None,
) -> list[tuple[float, ConferenceSession, tuple[str, ...]]]:
    label_text = " ".join(
        value
        for value in (
            descriptor.label,
            manifest_entry.source_name if manifest_entry else "",
            manifest_entry.target_name if manifest_entry else "",
        )
        if value
    )
    label_tokens = _tokenize(label_text)
    transcript_tokens = _tokenize(transcript_text)
    scored = []
    for session in sessions:
        if session.date != descriptor.date:
            continue
        session_text = " ".join(
            (
                session.title,
                " ".join(session.categories),
                session.abstract,
                " ".join(item.title for item in session.presentations),
                " ".join(
                    presenter
                    for item in session.presentations
                    for presenter in item.presenters
                ),
            )
        )
        session_tokens = _tokenize(session_text)
        session_title_tokens = _tokenize(session.title)
        label_hits = sorted(label_tokens & session_tokens)
        transcript_hits = sorted(transcript_tokens & session_tokens)
        time_score, time_reason = _time_score(
            descriptor.start_minute,
            session.start_minute,
            session.end_minute,
        )
        score = time_score
        score += len(label_hits) * 14
        if label_tokens:
            score += 35 * len(label_hits) / len(label_tokens)
        score += min(20, len(transcript_hits) * 0.35)
        reasons = [time_reason]
        label_track = label_tokens & _ROMAN_NUMERALS
        session_track = session_title_tokens & _ROMAN_NUMERALS
        if label_track and session_track:
            if label_track & session_track:
                score += 70
                reasons.append(
                    f"explicit track match: {', '.join(sorted(label_track & session_track))}"
                )
            else:
                score -= 70
                reasons.append("explicit track numeral conflicts with the session title")
        if label_hits:
            reasons.append(f"recording label tokens: {', '.join(label_hits[:12])}")
        if transcript_hits:
            reasons.append(
                f"transcript/session vocabulary overlap: {', '.join(transcript_hits[:12])}"
            )
        scored.append((score, session, tuple(reasons)))
    return sorted(scored, key=lambda item: (-item[0], item[1].title.casefold()))


def _score_presentations(
    descriptor: RecordingDescriptor,
    transcript_text: str,
    session: ConferenceSession,
    *,
    manifest_entry: RecordingManifestEntry | None,
) -> list[dict[str, object]]:
    label_text = " ".join(
        value
        for value in (
            descriptor.label,
            manifest_entry.target_name if manifest_entry else "",
        )
        if value
    )
    label_tokens = _tokenize(label_text)
    transcript_tokens = _tokenize(transcript_text)
    title_token_sets = [_tokenize(item.title) for item in session.presentations]
    token_frequency: dict[str, int] = {}
    for tokens in title_token_sets:
        for token in tokens:
            token_frequency[token] = token_frequency.get(token, 0) + 1

    candidates = []
    for item, title_tokens in zip(session.presentations, title_token_sets):
        presenter_tokens = _presenter_name_tokens(item.presenters)
        label_hits = sorted(label_tokens & (title_tokens | presenter_tokens))
        transcript_title_hits = sorted(transcript_tokens & title_tokens)
        presenter_hits = sorted(transcript_tokens & presenter_tokens)
        time_score, time_reason = _presentation_time_score(
            descriptor.start_minute,
            item.start_minute,
            item.end_minute,
        )
        rare_title_score = sum(
            9 if token_frequency.get(token, 0) == 1 else 3
            for token in transcript_title_hits
        )
        score = time_score + rare_title_score
        score += len(label_hits) * 18
        score += len(presenter_hits) * 12
        reasons = [time_reason]
        if label_hits:
            reasons.append(f"filename/manifest hits: {', '.join(label_hits)}")
        if transcript_title_hits:
            reasons.append(
                f"transcript title hits: {', '.join(transcript_title_hits[:12])}"
            )
        if presenter_hits:
            reasons.append(f"transcript presenter hits: {', '.join(presenter_hits)}")
        candidates.append(
            {
                "evidence_id": f"conference.presentation:{item.presentation_id}",
                "presentation_id": item.presentation_id,
                "time": item.time,
                "title": item.title,
                "presenters": list(item.presenters),
                "score": round(score, 3),
                "time_delta_minutes": (
                    descriptor.start_minute - item.start_minute
                    if item.start_minute is not None
                    else None
                ),
                "label_hits": label_hits,
                "transcript_title_hits": transcript_title_hits,
                "transcript_presenter_hits": presenter_hits,
                "reasons": reasons,
            }
        )
    return sorted(candidates, key=lambda item: (-float(item["score"]), str(item["time"])))


def _build_warnings(
    descriptor: RecordingDescriptor,
    session: ConferenceSession,
    session_scores: list[tuple[float, ConferenceSession, tuple[str, ...]]],
    presentation_candidates: list[dict[str, object]],
    manifest_entry: RecordingManifestEntry | None,
) -> list[dict[str, str]]:
    warnings = [
        {
            "code": "schedule_is_planned_context",
            "message": (
                "The archive is a planned schedule, not proof of the live running order. "
                "Explicit speaker introductions and talk transitions in the transcript take priority."
            ),
        }
    ]
    if len(session_scores) > 1 and session_scores[0][0] - session_scores[1][0] < 15:
        warnings.append(
            {
                "code": "session_match_ambiguous",
                "message": (
                    f"The top session match is close to {session_scores[1][1].title}; "
                    "do not use the session label alone for corrections."
                ),
            }
        )
    if manifest_entry and manifest_entry.confidence.casefold() != "high":
        warnings.append(
            {
                "code": "recording_manifest_needs_review",
                "message": manifest_entry.note or "The recording manifest confidence is not high.",
            }
        )
    if manifest_entry and "check" in manifest_entry.target_name.casefold():
        warnings.append(
            {
                "code": "recording_boundary_check",
                "message": manifest_entry.note or "The filename marks this recording for review.",
            }
        )

    scheduled = _scheduled_presentation_at(descriptor.start_minute, session.presentations)
    top = presentation_candidates[0] if presentation_candidates else None
    if scheduled and top and top["presentation_id"] != scheduled.presentation_id:
        warnings.append(
            {
                "code": "schedule_content_conflict",
                "message": (
                    f"Clock time points to '{scheduled.title}', while filename/transcript "
                    f"signals rank '{top['title']}' first. Verify the spoken introduction."
                ),
            }
        )
    if len(presentation_candidates) > 1:
        margin = float(presentation_candidates[0]["score"]) - float(
            presentation_candidates[1]["score"]
        )
        if margin < 10:
            warnings.append(
                {
                    "code": "presentation_match_ambiguous",
                    "message": "The top presentation candidates are close; retain multiple candidates.",
                }
            )
    return warnings


def _build_evidence_catalog(
    descriptor: RecordingDescriptor,
    archive: ConferenceArchive,
    sessions: tuple[ConferenceSession, ...],
    manifest_entry: RecordingManifestEntry | None,
) -> list[dict[str, str]]:
    session = sessions[0]
    catalog = [
        {
            "evidence_id": "recording.filename",
            "kind": "recording_metadata",
            "source": descriptor.name,
        },
        {
            "evidence_id": f"conference.session:{session.presentation_id}",
            "kind": "official_schedule_session",
            "source": session.source_url or archive.agenda_url,
        },
    ]
    if manifest_entry:
        catalog.append(
            {
                "evidence_id": "recording.manifest",
                "kind": "recording_match_manifest",
                "source": manifest_entry.target_name,
            }
        )
    for candidate_session in sessions:
        session_evidence_id = f"conference.session:{candidate_session.presentation_id}"
        if not any(item["evidence_id"] == session_evidence_id for item in catalog):
            catalog.append(
                {
                    "evidence_id": session_evidence_id,
                    "kind": "official_schedule_session_candidate",
                    "source": candidate_session.source_url or archive.agenda_url,
                }
            )
        catalog.extend(
            {
                "evidence_id": f"conference.presentation:{item.presentation_id}",
                "kind": "official_schedule_presentation",
                "source": candidate_session.source_url or archive.agenda_url,
            }
            for item in candidate_session.presentations
        )
    return catalog


def _session_confidence(best_score: float, second_score: float | None) -> str:
    margin = best_score - second_score if second_score is not None else best_score
    if best_score >= 100 and margin >= 20:
        return "high"
    if best_score >= 70 and margin >= 10:
        return "medium"
    return "low"


def _time_score(
    recording_minute: int,
    start_minute: int | None,
    end_minute: int | None,
) -> tuple[float, str]:
    if start_minute is None or end_minute is None:
        return 0.0, "session time unavailable"
    if start_minute <= recording_minute <= end_minute:
        return 70.0, "recording starts within the scheduled session"
    distance = min(abs(recording_minute - start_minute), abs(recording_minute - end_minute))
    return max(-30.0, 40.0 - distance * 2.0), f"recording is {distance} minutes from session"


def _presentation_time_score(
    recording_minute: int,
    start_minute: int | None,
    end_minute: int | None,
) -> tuple[float, str]:
    if start_minute is None or end_minute is None:
        return 0.0, "presentation time unavailable"
    if start_minute <= recording_minute < end_minute:
        return 45.0, "recording starts inside the scheduled presentation"
    distance = abs(recording_minute - start_minute)
    return max(-20.0, 35.0 - distance * 2.0), f"scheduled start differs by {distance} minutes"


def _scheduled_presentation_at(
    recording_minute: int,
    presentations: tuple[ConferencePresentation, ...],
) -> ConferencePresentation | None:
    available = [item for item in presentations if item.start_minute is not None]
    if not available:
        return None
    inside = [
        item
        for item in available
        if item.end_minute is not None
        and item.start_minute <= recording_minute < item.end_minute
    ]
    if inside:
        return inside[0]
    return min(available, key=lambda item: abs(recording_minute - int(item.start_minute)))


def _parse_archive_date(value: str) -> str:
    match = _ARCHIVE_DATE.match(value.strip())
    if not match:
        return ""
    month = _MONTHS.get(match.group("month").casefold())
    if month is None:
        return ""
    return f"{int(match.group('year')):04d}-{month:02d}-{int(match.group('day')):02d}"


def _parse_time_range(value: str) -> tuple[int | None, int | None]:
    matches = list(_CLOCK_TIME.finditer(value))
    if not matches:
        return None, None
    start = _clock_match_to_minute(matches[0])
    end = _clock_match_to_minute(matches[1]) if len(matches) > 1 else None
    return start, end


def _clock_match_to_minute(match: re.Match[str]) -> int:
    hour = int(match.group("hour")) % 12
    if match.group("period").casefold() == "pm":
        hour += 12
    return hour * 60 + int(match.group("minute"))


def _format_minute(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def _clean_recording_label(value: str) -> str:
    cleaned = re.sub(r"(?:_P\d+)?(?:[-_]short(?:-clip|-tail)?)?$", "", value, flags=re.I)
    return _clean_text(cleaned.replace("_", " "))


def _normalized_stem(value: str) -> str:
    stem = Path(unicodedata.normalize("NFKC", value)).stem
    return " ".join(stem.casefold().split())


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").split())


def _tokenize(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value).casefold()
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    raw_tokens = re.findall(r"[a-z0-9]+", normalized)
    tokens = set()
    for token in raw_tokens:
        if token in _STOP_WORDS:
            continue
        if len(token) >= 3 or token in _ROMAN_NUMERALS:
            tokens.add(token)
        tokens.update(_TOKEN_ALIASES.get(token, ()))
    return tokens


def _presenter_name_tokens(presenters: tuple[str, ...]) -> set[str]:
    tokens = set()
    for presenter in presenters:
        name_section = re.split(r"\s+[–-]\s+", presenter, maxsplit=1)[0]
        name_section = name_section.split(":", maxsplit=1)[-1]
        for token in _tokenize(name_section):
            if token not in {"chair", "doctoral", "invited", "oral", "abstract", "phd", "msc"}:
                tokens.add(token)
    return tokens
