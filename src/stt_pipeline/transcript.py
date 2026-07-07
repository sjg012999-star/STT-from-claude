from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptSegment:
    segment_id: str
    text: str
    start_seconds: float | None = None
    end_seconds: float | None = None
    speaker: str | None = None


@dataclass(frozen=True)
class TranscriptResult:
    provider: str
    model: str
    profile: str
    text: str
    segments: tuple[TranscriptSegment, ...]
    usage_seconds: float | None = None
