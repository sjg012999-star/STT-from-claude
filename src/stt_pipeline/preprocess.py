"""① 전처리 — ffmpeg 로 16kHz mono + loudnorm(EBU R128) + 무음 트리밍.

subprocess 래핑. ffmpeg 가 시스템에 없으면 명확한 에러를 던진다.
mock provider 경로에서는 cli 가 이 단계를 건너뛰므로 ffmpeg 없이도 e2e 가 돈다.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class FfmpegNotFoundError(RuntimeError):
    pass


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _require_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe is None:
        raise FfmpegNotFoundError(
            "ffmpeg 를 찾을 수 없습니다. 전처리에는 시스템 ffmpeg 설치가 필요합니다.\n"
            "  macOS:  brew install ffmpeg\n"
            "  Ubuntu: sudo apt-get install ffmpeg\n"
            "(mock provider 로는 ffmpeg 없이도 파이프라인을 검증할 수 있습니다.)"
        )
    return exe


def preprocess_audio(
    input_path: str | Path,
    output_path: str | Path,
    *,
    sample_rate: int = 16000,
    channels: int = 1,
    loudnorm: str = "I=-16:TP=-1.5:LRA=11",
    trim_silence: bool = True,
) -> Path:
    """녹음을 STT 업로드에 적합하게 정규화한다.

    - 16kHz mono 다운믹스
    - EBU R128 라우드니스 정규화 (loudnorm)
    - (옵션) 앞뒤/중간 긴 무음 트리밍으로 업로드 용량 절감
    """
    exe = _require_ffmpeg()
    input_path = Path(input_path)
    output_path = Path(output_path)
    if not input_path.exists():
        raise FileNotFoundError(f"입력 오디오가 없습니다: {input_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    filters = [f"loudnorm={loudnorm}"]
    if trim_silence:
        # 시작/끝의 긴 무음 제거. 문장 중간 절단을 피하기 위해 보수적으로.
        filters.append(
            "silenceremove=start_periods=1:start_silence=0.3:start_threshold=-50dB:"
            "stop_periods=1:stop_silence=0.3:stop_threshold=-50dB"
        )

    cmd = [
        exe,
        "-y",
        "-i",
        str(input_path),
        "-ac",
        str(channels),
        "-ar",
        str(sample_rate),
        "-af",
        ",".join(filters),
        str(output_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg 전처리 실패 (code {proc.returncode}):\n{proc.stderr[-2000:]}"
        )
    return output_path
