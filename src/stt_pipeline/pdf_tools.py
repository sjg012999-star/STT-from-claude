from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from stt_pipeline.knowledge_pack import PdfExtractionJob


@dataclass(frozen=True)
class FigureTableExtractorConfig:
    script_path: Path
    python_executable: str = "python3"
    page_render: bool = False
    zoom: int | None = None


def build_extraction_command(
    job: PdfExtractionJob,
    *,
    pdf_path: Path,
    out_dir: Path,
    config: FigureTableExtractorConfig,
) -> tuple[str, ...]:
    command = [
        config.python_executable,
        str(config.script_path),
        "--pdf",
        str(pdf_path),
        "--out",
        str(out_dir),
        "--reference",
        job.reference,
    ]
    if config.page_render:
        command.append("--page-render")
    if config.zoom is not None:
        command.extend(["--zoom", str(config.zoom)])
    return tuple(command)
