from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from stt_pipeline.transcript import TranscriptResult, TranscriptSegment


CommandRunner = Callable[[Sequence[str]], None]


@dataclass(frozen=True)
class AudioChunkPlan:
    input_path: Path
    output_dir: Path
    chunk_pattern: Path
    chunk_seconds: int
    command: tuple[str, ...]


def build_audio_chunk_plan(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    chunk_seconds: int = 600,
) -> AudioChunkPlan:
    input_audio = Path(input_path)
    chunk_dir = Path(output_dir) / "audio_chunks"
    chunk_pattern = chunk_dir / "chunk_%03d.wav"
    safe_seconds = max(1, int(chunk_seconds))
    codec_args = ("-c", "copy") if input_audio.suffix.casefold() == ".wav" else ()
    return AudioChunkPlan(
        input_path=input_audio,
        output_dir=chunk_dir,
        chunk_pattern=chunk_pattern,
        chunk_seconds=safe_seconds,
        command=(
            "ffmpeg",
            "-y",
            "-i",
            str(input_audio),
            *codec_args,
            "-f",
            "segment",
            "-segment_time",
            str(safe_seconds),
            "-reset_timestamps",
            "1",
            str(chunk_pattern),
        ),
    )


def chunk_audio(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    chunk_seconds: int = 600,
    runner: CommandRunner,
) -> tuple[Path, ...]:
    plan = build_audio_chunk_plan(
        input_path,
        output_dir,
        chunk_seconds=chunk_seconds,
    )
    plan.output_dir.mkdir(parents=True, exist_ok=True)
    runner(plan.command)
    return tuple(sorted(plan.output_dir.glob("chunk_*.wav")))


def merge_chunk_transcripts(
    results: tuple[TranscriptResult, ...],
    *,
    chunk_seconds: int,
) -> TranscriptResult:
    if not results:
        raise ValueError("at least one chunk transcript is required")

    segments = []
    for chunk_index, result in enumerate(results, start=1):
        offset = (chunk_index - 1) * chunk_seconds
        for segment in result.segments:
            segments.append(
                TranscriptSegment(
                    segment_id=f"chunk_{chunk_index:03d}_{segment.segment_id}",
                    text=segment.text,
                    start_seconds=_offset_seconds(segment.start_seconds, offset),
                    end_seconds=_offset_seconds(segment.end_seconds, offset),
                    speaker=segment.speaker,
                )
            )

    usage_values = [result.usage_seconds for result in results if result.usage_seconds is not None]
    return TranscriptResult(
        provider=results[0].provider,
        model=results[0].model,
        profile=results[0].profile,
        text="\n".join(result.text for result in results if result.text),
        segments=tuple(segments),
        usage_seconds=sum(usage_values) if usage_values else None,
    )


def _offset_seconds(value: float | None, offset: int) -> float | None:
    if value is None:
        return None
    return float(value) + offset
