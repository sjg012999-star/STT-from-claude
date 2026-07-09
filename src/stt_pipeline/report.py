from __future__ import annotations

from stt_pipeline.transcript import TranscriptResult, TranscriptSegment


def render_srt(result: TranscriptResult) -> str:
    blocks = []
    index = 1
    for segment in result.segments:
        if segment.start_seconds is None or segment.end_seconds is None:
            continue
        blocks.append(_render_srt_block(index, segment))
        index += 1
    if not blocks:
        return ""
    return "\n\n".join(blocks) + "\n"


def _render_srt_block(index: int, segment: TranscriptSegment) -> str:
    speaker = f"{segment.speaker}: " if segment.speaker else ""
    return "\n".join(
        [
            str(index),
            f"{_format_srt_time(segment.start_seconds)} --> {_format_srt_time(segment.end_seconds)}",
            f"{speaker}{segment.text}",
        ]
    )


def _format_srt_time(value: float) -> str:
    milliseconds_total = int(round(float(value) * 1000))
    milliseconds = milliseconds_total % 1000
    seconds_total = milliseconds_total // 1000
    seconds = seconds_total % 60
    minutes_total = seconds_total // 60
    minutes = minutes_total % 60
    hours = minutes_total // 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
