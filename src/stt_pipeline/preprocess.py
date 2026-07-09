from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


CommandRunner = Callable[[Sequence[str]], None]


@dataclass(frozen=True)
class PreprocessPlan:
    input_path: Path
    output_path: Path
    command: tuple[str, ...]


def build_preprocess_plan(
    input_path: str | Path,
    output_dir: str | Path,
) -> PreprocessPlan:
    source = Path(input_path)
    destination = Path(output_dir) / "preprocessed.wav"
    return PreprocessPlan(
        input_path=source,
        output_path=destination,
        command=(
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11",
            str(destination),
        ),
    )


def preprocess_audio(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    runner: CommandRunner | None = None,
) -> Path:
    plan = build_preprocess_plan(input_path, output_dir)
    plan.output_path.parent.mkdir(parents=True, exist_ok=True)
    active_runner = runner or _run_subprocess
    active_runner(plan.command)
    return plan.output_path


def _run_subprocess(command: Sequence[str]) -> None:
    subprocess.run(command, check=True)
