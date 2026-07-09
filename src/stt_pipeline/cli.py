from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Sequence

from stt_pipeline.audio_chunks import chunk_audio, merge_chunk_transcripts
from stt_pipeline.correct import (
    OpenAiTranscriptCorrector,
    CorrectionReport,
    correction_report_to_dict,
)
from stt_pipeline.glossary import (
    build_glossary_entries_from_corrections,
    load_glossary_tsv,
    merge_glossary_entries,
    write_glossary_tsv,
)
from stt_pipeline.materials import load_material_pack, material_pack_to_dict
from stt_pipeline.notes import build_enriched_notes
from stt_pipeline.pdf_tools import (
    FigureTableExtractorConfig,
    pdf_extraction_results_to_dict,
    run_pdf_extraction_jobs,
)
from stt_pipeline.preprocess import build_preprocess_plan, preprocess_audio
from stt_pipeline.report import render_srt
from stt_pipeline.reference_lookup import (
    ReferenceLookupHttpClient,
    build_reference_lookup_plans,
    lookup_and_cache_references,
    reference_lookup_plans_to_dict,
    reference_lookup_results_to_dict,
)
from stt_pipeline.rich_summary import OpenAiRichSummarizer
from stt_pipeline.stt_provider import RoutedSttTranscriber
from stt_pipeline.summarize import build_basic_summary
from stt_pipeline.transcript import TranscriptResult
from stt_pipeline.vision_ocr import OpenAiSlideImageOcr


def main(
    argv: Sequence[str] | None = None,
    *,
    transcriber=None,
    corrector=None,
    image_ocr=None,
    summarizer=None,
    reference_lookup_client=None,
    command_runner=None,
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    active_transcriber = transcriber or RoutedSttTranscriber()

    if args.command in {"transcribe", "run"}:
        return _run_transcribe(
            args,
            active_transcriber,
            corrector=corrector,
            image_ocr=image_ocr,
            summarizer=summarizer,
            reference_lookup_client=reference_lookup_client,
            command_runner=command_runner,
        )
    if args.command == "bakeoff":
        return _run_bakeoff(
            args,
            active_transcriber,
            image_ocr=image_ocr,
            command_runner=command_runner,
        )
    parser.error("unknown command")
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stt")
    subparsers = parser.add_subparsers(dest="command", required=True)

    transcribe = subparsers.add_parser("transcribe")
    transcribe.add_argument("audio_path")
    transcribe.add_argument("--profile", default="seminar")
    transcribe.add_argument("--provider")
    transcribe.add_argument("--terms-file")
    transcribe.add_argument("--pack", "--materials", action="append", dest="pack_paths")
    transcribe.add_argument("--ocr-images", action="store_true")
    transcribe.add_argument("--extract-pdfs", action="store_true")
    transcribe.add_argument("--plan-reference-search", action="store_true")
    transcribe.add_argument("--lookup-references", action="store_true")
    transcribe.add_argument("--pdf-extractor-script")
    transcribe.add_argument("--pdf-page-render", action="store_true")
    transcribe.add_argument("--preprocess", action="store_true")
    transcribe.add_argument("--chunk-audio", action="store_true")
    transcribe.add_argument("--chunk-seconds", type=int, default=600)
    transcribe.add_argument("--correct", action="store_true")
    transcribe.add_argument("--save-glossary")
    transcribe.add_argument("--correction-chunk-size", type=int)
    transcribe.add_argument("--correction-overlap", type=int, default=1)
    transcribe.add_argument("--summarize", action="store_true")
    transcribe.add_argument("--llm-summarize", action="store_true")
    transcribe.add_argument("--enrich-notes", action="store_true")
    transcribe.add_argument("--output", required=True)

    run = subparsers.add_parser("run")
    run.add_argument("audio_path")
    run.add_argument("--profile", default="seminar")
    run.add_argument("--provider")
    run.add_argument("--terms-file")
    run.add_argument("--pack", "--materials", action="append", dest="pack_paths")
    run.add_argument("--ocr-images", action="store_true")
    run.add_argument("--extract-pdfs", action="store_true")
    run.add_argument("--plan-reference-search", action="store_true")
    run.add_argument("--lookup-references", action="store_true")
    run.add_argument("--pdf-extractor-script")
    run.add_argument("--pdf-page-render", action="store_true")
    run.add_argument("--preprocess", action="store_true")
    run.add_argument("--chunk-audio", action="store_true")
    run.add_argument("--chunk-seconds", type=int, default=600)
    run.add_argument("--correct", action="store_true")
    run.add_argument("--save-glossary")
    run.add_argument("--correction-chunk-size", type=int)
    run.add_argument("--correction-overlap", type=int, default=1)
    run.add_argument("--summarize", action="store_true")
    run.add_argument("--llm-summarize", action="store_true")
    run.add_argument("--enrich-notes", action="store_true")
    run.add_argument("--output", required=True)

    bakeoff = subparsers.add_parser("bakeoff")
    bakeoff.add_argument("audio_path")
    bakeoff.add_argument("--profile", default="seminar")
    bakeoff.add_argument("--providers", required=True)
    bakeoff.add_argument("--terms-file")
    bakeoff.add_argument("--pack", "--materials", action="append", dest="pack_paths")
    bakeoff.add_argument("--ocr-images", action="store_true")
    bakeoff.add_argument("--extract-pdfs", action="store_true")
    bakeoff.add_argument("--plan-reference-search", action="store_true")
    bakeoff.add_argument("--lookup-references", action="store_true")
    bakeoff.add_argument("--pdf-extractor-script")
    bakeoff.add_argument("--pdf-page-render", action="store_true")
    bakeoff.add_argument("--preprocess", action="store_true")
    bakeoff.add_argument("--chunk-audio", action="store_true")
    bakeoff.add_argument("--chunk-seconds", type=int, default=600)
    bakeoff.add_argument("--output", required=True)

    return parser


def _run_transcribe(
    args,
    transcriber,
    *,
    corrector=None,
    image_ocr=None,
    summarizer=None,
    reference_lookup_client=None,
    command_runner=None,
) -> int:
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    terms, pack = _load_prompt_terms(args, output_dir, image_ocr=image_ocr)
    reference_lookup_plans = _maybe_plan_reference_search(args, output_dir, pack)
    reference_lookup_results = _maybe_lookup_references(
        args,
        output_dir,
        pack,
        reference_lookup_plans,
        reference_lookup_client,
    )
    pdf_results = _maybe_extract_pdfs(
        args,
        output_dir,
        pack,
        command_runner,
        reference_lookup_results=reference_lookup_results,
    )
    audio_path, preprocess_manifest = _prepare_audio(args, output_dir, command_runner)
    result, chunk_manifest = _transcribe_audio(
        args,
        transcriber,
        audio_path,
        terms,
        output_dir=output_dir,
        command_runner=command_runner,
        provider=args.provider,
    )

    _write_result_json(output_dir / "transcript.json", result)
    _write_result_markdown(output_dir / "transcript.md", result)
    _write_srt(output_dir / "transcript.srt", result)
    correction_report = _maybe_write_corrections(
        args,
        output_dir,
        result,
        terms,
        corrector=corrector,
    )
    glossary_manifest = _maybe_save_glossary(args, correction_report)
    summary_source = (
        correction_report.corrected_result if correction_report is not None else result
    )
    if getattr(args, "summarize", False):
        _write_summary(output_dir / "summary.md", summary_source, correction_report)
    if getattr(args, "llm_summarize", False):
        _write_rich_summary(
            output_dir / "rich_summary.md",
            summary_source,
            terms,
            material_pack=pack,
            pdf_results=pdf_results,
            reference_lookup_plans=reference_lookup_plans,
            reference_lookup_results=reference_lookup_results,
            correction_report=correction_report,
            summarizer=summarizer,
        )
    if getattr(args, "enrich_notes", False):
        _write_enriched_notes(
            output_dir / "notes.md",
            summary_source,
            material_pack=pack,
            pdf_results=pdf_results,
            reference_lookup_plans=reference_lookup_plans,
            reference_lookup_results=reference_lookup_results,
        )
    _write_run_manifest(
        output_dir / "run_manifest.json",
        input_audio=args.audio_path,
        stt_audio=audio_path,
        preprocess_manifest=preprocess_manifest,
        chunk_manifest=chunk_manifest,
        result=result,
        corrected=correction_report is not None,
        summarized=getattr(args, "summarize", False),
        llm_summarized=getattr(args, "llm_summarize", False),
        reference_lookup_planned=getattr(args, "plan_reference_search", False),
        references_looked_up=getattr(args, "lookup_references", False),
        glossary_manifest=glossary_manifest,
        correction_manifest=_correction_manifest(args),
    )
    return 0


def _run_bakeoff(args, transcriber, *, image_ocr=None, command_runner=None) -> int:
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    terms, pack = _load_prompt_terms(args, output_dir, image_ocr=image_ocr)
    plans = _maybe_plan_reference_search(args, output_dir, pack)
    _maybe_lookup_references(args, output_dir, pack, plans, None)
    _maybe_extract_pdfs(args, output_dir, pack, command_runner)
    audio_path, preprocess_manifest = _prepare_audio(args, output_dir, command_runner)
    providers = tuple(value.strip() for value in args.providers.split(",") if value.strip())
    results = []

    for provider in providers:
        result, _chunk_manifest = _transcribe_audio(
            args,
            transcriber,
            audio_path,
            terms,
            output_dir=output_dir,
            command_runner=command_runner,
            provider=provider,
        )
        _write_result_json(output_dir / f"{provider}.json", result)
        results.append(result)

    _write_bakeoff_report(output_dir / "bakeoff_report.md", results, terms)
    _write_bakeoff_manifest(
        output_dir / "run_manifest.json",
        input_audio=args.audio_path,
        stt_audio=audio_path,
        preprocess_manifest=preprocess_manifest,
        providers=providers,
    )
    return 0


def _transcribe_audio(
    args,
    transcriber,
    audio_path: Path,
    terms: tuple[str, ...],
    *,
    output_dir: Path,
    command_runner,
    provider: str | None,
):
    if not getattr(args, "chunk_audio", False):
        return (
            transcriber.transcribe(
                audio_path,
                provider=provider,
                profile=args.profile,
                prompt_terms=terms,
            ),
            {"enabled": False},
        )

    chunk_seconds = max(1, int(getattr(args, "chunk_seconds", 600)))
    runner = command_runner or _run_command
    chunk_paths = chunk_audio(
        audio_path,
        output_dir,
        chunk_seconds=chunk_seconds,
        runner=runner,
    )
    if not chunk_paths:
        raise ValueError("audio chunking did not produce any chunk_*.wav files")
    chunk_results = tuple(
        transcriber.transcribe(
            chunk_path,
            provider=provider,
            profile=args.profile,
            prompt_terms=terms,
        )
        for chunk_path in chunk_paths
    )
    return (
        merge_chunk_transcripts(chunk_results, chunk_seconds=chunk_seconds),
        {
            "enabled": True,
            "chunk_seconds": chunk_seconds,
            "chunk_count": len(chunk_paths),
            "chunks": [str(path) for path in chunk_paths],
        },
    )


def _prepare_audio(args, output_dir: Path, command_runner) -> tuple[Path, dict[str, object]]:
    input_audio = Path(args.audio_path)
    if not getattr(args, "preprocess", False):
        return input_audio, {"enabled": False}

    plan = build_preprocess_plan(input_audio, output_dir)
    output_audio = preprocess_audio(input_audio, output_dir, runner=command_runner)
    return output_audio, {
        "enabled": True,
        "command": list(plan.command),
        "output_audio": str(output_audio),
    }


def _load_prompt_terms(args, output_dir: Path, *, image_ocr=None):
    terms = list(_read_terms(args.terms_file))
    pack = None
    pack_paths = tuple(getattr(args, "pack_paths", None) or ())
    if pack_paths:
        active_image_ocr = None
        if getattr(args, "ocr_images", False):
            active_image_ocr = image_ocr or OpenAiSlideImageOcr()
        pack = load_material_pack(pack_paths, image_ocr=active_image_ocr)
        terms.extend(pack.prompt_terms)
        _write_material_pack(output_dir / "knowledge_pack.json", pack)

    prompt_terms = _dedupe_terms(terms)
    if prompt_terms:
        _write_prompt_terms(output_dir / "prompt_terms.txt", prompt_terms)
    return prompt_terms, pack


def _maybe_extract_pdfs(
    args,
    output_dir: Path,
    pack,
    command_runner,
    *,
    reference_lookup_results=(),
):
    if not getattr(args, "extract_pdfs", False):
        return ()
    lookup_pdf_sources = tuple(
        str(result.cached_pdf_path)
        for result in reference_lookup_results
        if result.cached_pdf_path is not None
    )
    pdf_sources = tuple(getattr(pack, "pdf_sources", ()) or ()) + lookup_pdf_sources
    if pack is None and not pdf_sources:
        (output_dir / "pdf_extraction_jobs.json").write_text(
            json.dumps({"jobs": []}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return ()
    if not pdf_sources:
        (output_dir / "pdf_extraction_jobs.json").write_text(
            json.dumps({"jobs": []}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return ()
    if not args.pdf_extractor_script:
        raise ValueError("--pdf-extractor-script is required when --extract-pdfs is set")
    runner = command_runner or _run_command
    config = FigureTableExtractorConfig(
        script_path=Path(args.pdf_extractor_script),
        page_render=bool(getattr(args, "pdf_page_render", False)),
    )
    jobs = pack.knowledge_pack.pdf_extraction_jobs if pack is not None else ()
    if not jobs:
        jobs = tuple(
            _fallback_pdf_jobs(pdf_sources)
        )
    results = run_pdf_extraction_jobs(
        jobs,
        pdf_paths=tuple(Path(path) for path in pdf_sources),
        out_dir=output_dir / "pdf_extract",
        config=config,
        runner=runner,
    )
    (output_dir / "pdf_extraction_jobs.json").write_text(
        json.dumps(pdf_extraction_results_to_dict(results), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return results


def _maybe_plan_reference_search(args, output_dir: Path, pack):
    if not getattr(args, "plan_reference_search", False) and not getattr(args, "lookup_references", False):
        return ()
    if pack is None:
        plans = ()
    else:
        plans = build_reference_lookup_plans(pack.knowledge_pack)
    (output_dir / "reference_lookup_jobs.json").write_text(
        json.dumps(reference_lookup_plans_to_dict(plans), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return plans


def _maybe_lookup_references(
    args,
    output_dir: Path,
    pack,
    plans,
    reference_lookup_client,
):
    if not getattr(args, "lookup_references", False):
        return ()
    active_plans = plans
    if not active_plans and pack is not None:
        active_plans = build_reference_lookup_plans(pack.knowledge_pack)
    client = reference_lookup_client or ReferenceLookupHttpClient()
    results = lookup_and_cache_references(
        active_plans,
        cache_dir=output_dir / "reference_cache",
        http_client=client,
    )
    (output_dir / "reference_lookup_results.json").write_text(
        json.dumps(reference_lookup_results_to_dict(results), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return results


def _fallback_pdf_jobs(pdf_sources: tuple[str, ...]):
    from stt_pipeline.knowledge_pack import PdfExtractionJob

    for pdf_source in pdf_sources:
        yield PdfExtractionJob(reference=Path(pdf_source).stem, source_slide_ids=())


def _run_command(command: Sequence[str]) -> None:
    import subprocess

    subprocess.run(command, check=True)


def _read_terms(terms_file: str | None) -> tuple[str, ...]:
    if not terms_file:
        return ()
    lines = Path(terms_file).read_text(encoding="utf-8").splitlines()
    if lines and "\t" in lines[0] and "corrected" in lines[0].split("\t"):
        headers = lines[0].split("\t")
        corrected_index = headers.index("corrected")
        terms = []
        for line in lines[1:]:
            columns = line.split("\t")
            if len(columns) > corrected_index and columns[corrected_index].strip():
                terms.append(columns[corrected_index].strip())
        return tuple(terms)
    return tuple(line.strip() for line in lines if line.strip())


def _write_result_json(path: Path, result: TranscriptResult) -> None:
    path.write_text(
        json.dumps(asdict(result), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_material_pack(path: Path, pack) -> None:
    path.write_text(
        json.dumps(material_pack_to_dict(pack), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_prompt_terms(path: Path, terms: tuple[str, ...]) -> None:
    path.write_text("\n".join(terms) + "\n", encoding="utf-8")


def _write_srt(path: Path, result: TranscriptResult) -> None:
    path.write_text(render_srt(result), encoding="utf-8")


def _maybe_write_corrections(
    args,
    output_dir: Path,
    result: TranscriptResult,
    terms: tuple[str, ...],
    *,
    corrector,
) -> CorrectionReport | None:
    if not getattr(args, "correct", False):
        return None
    active_corrector = corrector or OpenAiTranscriptCorrector(
        max_segments_per_request=getattr(args, "correction_chunk_size", None),
        overlap_segments=getattr(args, "correction_overlap", 1),
    )
    report = active_corrector.correct(result, prompt_terms=terms)
    _write_result_json(output_dir / "corrected_transcript.json", report.corrected_result)
    _write_result_markdown(output_dir / "corrected_transcript.md", report.corrected_result)
    _write_srt(output_dir / "corrected_transcript.srt", report.corrected_result)
    (output_dir / "corrections.json").write_text(
        json.dumps(correction_report_to_dict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def _maybe_save_glossary(args, correction_report: CorrectionReport | None) -> dict[str, object]:
    path = getattr(args, "save_glossary", None)
    if not path:
        return {"enabled": False}
    if correction_report is None:
        raise ValueError("--save-glossary requires --correct")
    glossary_path = Path(path)
    existing = load_glossary_tsv(glossary_path)
    new_entries = build_glossary_entries_from_corrections(correction_report)
    merged = merge_glossary_entries(existing, new_entries)
    write_glossary_tsv(glossary_path, merged)
    return {
        "enabled": True,
        "saved_to": str(glossary_path),
        "new_entries": len(new_entries),
        "total_entries": len(merged),
    }


def _write_summary(
    path: Path,
    result: TranscriptResult,
    correction_report: CorrectionReport | None,
) -> None:
    summary = build_basic_summary(result, correction_report=correction_report)
    path.write_text(summary.markdown, encoding="utf-8")


def _write_rich_summary(
    path: Path,
    result: TranscriptResult,
    terms: tuple[str, ...],
    *,
    material_pack,
    pdf_results,
    reference_lookup_plans,
    reference_lookup_results,
    correction_report: CorrectionReport | None,
    summarizer,
) -> None:
    active_summarizer = summarizer or OpenAiRichSummarizer()
    summary = active_summarizer.summarize(
        result,
        prompt_terms=terms,
        material_pack=material_pack,
        pdf_results=pdf_results,
        reference_lookup_plans=reference_lookup_plans,
        reference_lookup_results=reference_lookup_results,
        correction_report=correction_report,
    )
    path.write_text(summary.markdown, encoding="utf-8")


def _write_enriched_notes(
    path: Path,
    result: TranscriptResult,
    *,
    material_pack,
    pdf_results,
    reference_lookup_plans=(),
    reference_lookup_results=(),
) -> None:
    notes = build_enriched_notes(
        result,
        material_pack=material_pack,
        pdf_results=pdf_results,
        reference_lookup_plans=reference_lookup_plans,
        reference_lookup_results=reference_lookup_results,
    )
    path.write_text(notes.markdown, encoding="utf-8")


def _write_run_manifest(
    path: Path,
    *,
    input_audio: str,
    stt_audio: Path,
    preprocess_manifest: dict[str, object],
    chunk_manifest: dict[str, object],
    result: TranscriptResult,
    corrected: bool,
    summarized: bool,
    llm_summarized: bool,
    reference_lookup_planned: bool,
    references_looked_up: bool,
    glossary_manifest: dict[str, object],
    correction_manifest: dict[str, object],
) -> None:
    path.write_text(
        json.dumps(
            {
                "input_audio": input_audio,
                "stt_audio": str(stt_audio),
                "preprocess": preprocess_manifest,
                "chunking": chunk_manifest,
                "provider": result.provider,
                "model": result.model,
                "profile": result.profile,
                "corrected": corrected,
                "summarized": summarized,
                "llm_summarized": llm_summarized,
                "reference_lookup_planned": reference_lookup_planned,
                "references_looked_up": references_looked_up,
                "glossary": glossary_manifest,
                "correction": correction_manifest,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _correction_manifest(args) -> dict[str, object]:
    return {
        "enabled": bool(getattr(args, "correct", False)),
        "chunk_size": getattr(args, "correction_chunk_size", None),
        "overlap": getattr(args, "correction_overlap", 1),
    }


def _write_bakeoff_manifest(
    path: Path,
    *,
    input_audio: str,
    stt_audio: Path,
    preprocess_manifest: dict[str, object],
    providers: tuple[str, ...],
) -> None:
    path.write_text(
        json.dumps(
            {
                "input_audio": input_audio,
                "stt_audio": str(stt_audio),
                "preprocess": preprocess_manifest,
                "providers": list(providers),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_result_markdown(path: Path, result: TranscriptResult) -> None:
    lines = [
        "# Transcript",
        "",
        f"- Provider: `{result.provider}`",
        f"- Model: `{result.model}`",
        f"- Profile: `{result.profile}`",
        "",
        "## Segments",
        "",
    ]
    for segment in result.segments:
        speaker = f"{segment.speaker}: " if segment.speaker else ""
        timestamp = _format_time_range(segment.start_seconds, segment.end_seconds)
        lines.append(f"- {timestamp} {speaker}{segment.text}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_bakeoff_report(
    path: Path,
    results: Iterable[TranscriptResult],
    terms: tuple[str, ...],
) -> None:
    lines = [
        "# STT Bakeoff Report",
        "",
        "| Provider | Model | Segments | Speakers | Term hits | Characters |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for result in results:
        speakers = {segment.speaker for segment in result.segments if segment.speaker}
        lines.append(
            "| {provider} | {model} | {segments} | {speakers} | "
            "{term_hits} | {chars} |".format(
                provider=result.provider,
                model=result.model,
                segments=len(result.segments),
                speakers=len(speakers),
                term_hits=_count_term_hits(result.text, terms),
                chars=len(result.text),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _count_term_hits(text: str, terms: tuple[str, ...]) -> int:
    lowered = text.casefold()
    return sum(1 for term in terms if term.casefold() in lowered)


def _dedupe_terms(terms: Iterable[str]) -> tuple[str, ...]:
    result = []
    seen = set()
    for term in terms:
        cleaned = " ".join(str(term).split())
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return tuple(result)


def _format_time_range(start: float | None, end: float | None) -> str:
    if start is None and end is None:
        return "[no timestamp]"
    return f"[{_format_seconds(start)} - {_format_seconds(end)}]"


def _format_seconds(value: float | None) -> str:
    if value is None:
        return "?"
    minutes, seconds = divmod(float(value), 60)
    return f"{int(minutes):02d}:{seconds:06.3f}"


if __name__ == "__main__":
    raise SystemExit(main())
