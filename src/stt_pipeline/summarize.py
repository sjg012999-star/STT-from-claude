from __future__ import annotations

from dataclasses import dataclass

from stt_pipeline.correct import CorrectionReport
from stt_pipeline.transcript import TranscriptResult


@dataclass(frozen=True)
class SummaryResult:
    profile: str
    markdown: str
    transcript_characters: int
    correction_count: int


def build_basic_summary(
    result: TranscriptResult,
    *,
    correction_report: CorrectionReport | None = None,
) -> SummaryResult:
    title = {
        "seminar": "Seminar Summary",
        "lecture": "Lecture Summary",
        "meeting": "Meeting Summary",
    }.get(result.profile, "Transcript Summary")
    correction_count = (
        len(correction_report.applied_corrections) if correction_report else 0
    )

    lines = [
        f"# {title}",
        "",
        "## Speaker Transcript",
        "",
        "_source: transcript_",
        "",
        *_segment_bullets(result),
        "",
        "## Correction Notes",
        "",
    ]
    if correction_report and correction_report.applied_corrections:
        for correction in correction_report.applied_corrections:
            lines.append(
                "- `{segment_id}`: `{original}` -> `{corrected}` ({confidence}, {reason})".format(
                    segment_id=correction.segment_id,
                    original=correction.original,
                    corrected=correction.corrected,
                    confidence=correction.confidence,
                    reason=correction.reason,
                )
            )
    else:
        lines.append("- No corrections applied.")

    if correction_report and correction_report.rejected_corrections:
        lines.extend(["", "## Needs Review", ""])
        for correction in correction_report.rejected_corrections:
            lines.append(
                f"- `{correction.segment_id}` rejected: `{correction.original}` was not found in the segment."
            )

    return SummaryResult(
        profile=result.profile,
        markdown="\n".join(lines) + "\n",
        transcript_characters=len(result.text),
        correction_count=correction_count,
    )


def _segment_bullets(result: TranscriptResult) -> list[str]:
    bullets = []
    for segment in result.segments[:8]:
        timestamp = (
            f"[{segment.start_seconds:.2f}-{segment.end_seconds:.2f}] "
            if segment.start_seconds is not None and segment.end_seconds is not None
            else ""
        )
        speaker = f"{segment.speaker}: " if segment.speaker else ""
        bullets.append(f"- {timestamp}{speaker}{segment.text}")
    if len(result.segments) > 8:
        bullets.append(f"- ... {len(result.segments) - 8} more segments omitted from basic summary.")
    return bullets
