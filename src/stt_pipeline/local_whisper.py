from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from stt_pipeline.transcript import TranscriptResult, TranscriptSegment


CommandRunner = Callable[[Sequence[str]], None]


@dataclass(frozen=True)
class MlxWhisperConfig:
    command: str = "mlx_whisper"
    model: str = "mlx-community/whisper-large-v3-turbo"
    output_format: str = "json"


def build_mlx_whisper_command(
    audio_path: str | Path,
    output_dir: str | Path,
    *,
    config: MlxWhisperConfig,
) -> tuple[str, ...]:
    return (
        config.command,
        str(audio_path),
        "--model",
        config.model,
        "--output-dir",
        str(output_dir),
        "--output-format",
        config.output_format,
    )


class MlxWhisperTranscriber:
    def __init__(
        self,
        *,
        runner: CommandRunner | None = None,
        work_dir: str | Path | None = None,
        config: MlxWhisperConfig | None = None,
    ):
        self._runner = runner or _run_command
        self._work_dir = Path(work_dir) if work_dir is not None else None
        self._config = config or _config_from_env()

    def transcribe(
        self,
        audio_path: str | Path,
        *,
        provider: str | None = None,
        profile: str = "seminar",
        prompt_terms=(),
    ) -> TranscriptResult:
        if provider not in {None, "mlx-whisper"}:
            raise ValueError(f"MlxWhisperTranscriber only supports mlx-whisper, got {provider}")
        if self._work_dir is None:
            with tempfile.TemporaryDirectory() as tmpdir:
                return self._transcribe_to_dir(Path(audio_path), Path(tmpdir), profile=profile)
        self._work_dir.mkdir(parents=True, exist_ok=True)
        return self._transcribe_to_dir(Path(audio_path), self._work_dir, profile=profile)

    def _transcribe_to_dir(
        self,
        audio_path: Path,
        output_dir: Path,
        *,
        profile: str,
    ) -> TranscriptResult:
        command = build_mlx_whisper_command(
            audio_path,
            output_dir,
            config=self._config,
        )
        self._runner(command)
        payload = _load_mlx_json(output_dir)
        return _normalize_mlx_payload(
            payload,
            profile=profile,
            model=self._config.model,
        )


def _load_mlx_json(output_dir: Path) -> dict[str, object]:
    json_paths = sorted(output_dir.glob("*.json"))
    if not json_paths:
        raise ValueError(f"mlx-whisper did not write a JSON output in {output_dir}")
    return json.loads(json_paths[0].read_text(encoding="utf-8"))


def _normalize_mlx_payload(
    payload: dict[str, object],
    *,
    profile: str,
    model: str,
) -> TranscriptResult:
    text = str(payload.get("text") or "")
    raw_segments = payload.get("segments") or []
    segments = tuple(
        _normalize_mlx_segment(index, raw_segment)
        for index, raw_segment in enumerate(raw_segments)
        if isinstance(raw_segment, dict)
    )
    if not segments:
        segments = (TranscriptSegment(segment_id="seg_000", text=text),)
    return TranscriptResult(
        provider="mlx-whisper",
        model=model,
        profile=profile,
        text=text,
        segments=segments,
        usage_seconds=None,
    )


def _normalize_mlx_segment(index: int, raw_segment: dict[str, object]) -> TranscriptSegment:
    raw_id = raw_segment.get("id", index)
    segment_id = (
        raw_id
        if isinstance(raw_id, str) and raw_id.startswith("seg_")
        else f"seg_{int(raw_id):03d}" if isinstance(raw_id, int) else f"seg_{index:03d}"
    )
    return TranscriptSegment(
        segment_id=segment_id,
        text=str(raw_segment.get("text") or ""),
        start_seconds=_optional_float(raw_segment.get("start")),
        end_seconds=_optional_float(raw_segment.get("end")),
        speaker=None,
    )


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _config_from_env() -> MlxWhisperConfig:
    return MlxWhisperConfig(
        command=os.environ.get("MLX_WHISPER_COMMAND", "mlx_whisper"),
        model=os.environ.get(
            "MLX_WHISPER_MODEL",
            "mlx-community/whisper-large-v3-turbo",
        ),
    )


def _run_command(command: Sequence[str]) -> None:
    subprocess.run(command, check=True)
