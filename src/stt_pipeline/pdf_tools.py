from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from stt_pipeline.knowledge_pack import PdfExtractionJob


@dataclass(frozen=True)
class FigureTableExtractorConfig:
    script_path: Path
    python_executable: str = "python3"
    page_render: bool = False
    zoom: int | None = None


@dataclass(frozen=True)
class PdfExtractionResult:
    reference: str
    pdf_path: Path
    out_dir: Path
    command: tuple[str, ...]
    status: str
    source_slide_ids: tuple[str, ...]


CommandRunner = Callable[[Sequence[str]], None]


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


def run_pdf_extraction_jobs(
    jobs: tuple[PdfExtractionJob, ...],
    *,
    pdf_paths: tuple[Path, ...],
    out_dir: Path,
    config: FigureTableExtractorConfig,
    runner: CommandRunner,
) -> tuple[PdfExtractionResult, ...]:
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for index, job in enumerate(jobs):
        pdf_path = _select_pdf_path(job, pdf_paths, index)
        job_out_dir = out_dir / _safe_pdf_output_name(pdf_path)
        job_out_dir.mkdir(parents=True, exist_ok=True)
        command = build_extraction_command(
            job,
            pdf_path=pdf_path,
            out_dir=job_out_dir,
            config=config,
        )
        runner(command)
        results.append(
            PdfExtractionResult(
                reference=job.reference,
                pdf_path=pdf_path,
                out_dir=job_out_dir,
                command=command,
                status="planned",
                source_slide_ids=job.source_slide_ids,
            )
        )
    return tuple(results)


def pdf_extraction_results_to_dict(
    results: tuple[PdfExtractionResult, ...],
) -> dict[str, object]:
    return {
        "jobs": [
            {
                "reference": result.reference,
                "pdf_path": str(result.pdf_path),
                "out_dir": str(result.out_dir),
                "command": list(result.command),
                "status": result.status,
                "source_slide_ids": list(result.source_slide_ids),
            }
            for result in results
        ]
    }


def _select_pdf_path(
    job: PdfExtractionJob,
    pdf_paths: tuple[Path, ...],
    index: int,
) -> Path:
    if not pdf_paths:
        raise ValueError("at least one PDF path is required for PDF extraction")
    scored = sorted(
        pdf_paths,
        key=lambda path: (
            -_filename_reference_score(path, job.reference),
            path.name.casefold(),
        ),
    )
    if _filename_reference_score(scored[0], job.reference) > 0:
        return scored[0]
    return pdf_paths[min(index, len(pdf_paths) - 1)]


def _filename_reference_score(path: Path, reference: str) -> int:
    filename = path.stem.casefold()
    score = 0
    for token in reference.casefold().replace(",", " ").replace(".", " ").split():
        if len(token) >= 4 and token in filename:
            score += 1
    return score


def _safe_pdf_output_name(path: Path) -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_" else "-" for char in path.stem)
    return cleaned.strip("-") or "pdf"
