from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Sequence

from stt_pipeline.materials import load_material_pack, material_pack_to_dict
from stt_pipeline.stt_provider import OpenAiSttTranscriber
from stt_pipeline.transcript import TranscriptResult


def main(argv: Sequence[str] | None = None, *, transcriber=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    active_transcriber = transcriber or OpenAiSttTranscriber()

    if args.command in {"transcribe", "run"}:
        return _run_transcribe(args, active_transcriber)
    if args.command == "bakeoff":
        return _run_bakeoff(args, active_transcriber)
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
    transcribe.add_argument("--output", required=True)

    run = subparsers.add_parser("run")
    run.add_argument("audio_path")
    run.add_argument("--profile", default="seminar")
    run.add_argument("--provider")
    run.add_argument("--terms-file")
    run.add_argument("--pack", "--materials", action="append", dest="pack_paths")
    run.add_argument("--output", required=True)

    bakeoff = subparsers.add_parser("bakeoff")
    bakeoff.add_argument("audio_path")
    bakeoff.add_argument("--profile", default="seminar")
    bakeoff.add_argument("--providers", required=True)
    bakeoff.add_argument("--terms-file")
    bakeoff.add_argument("--pack", "--materials", action="append", dest="pack_paths")
    bakeoff.add_argument("--output", required=True)

    return parser


def _run_transcribe(args, transcriber) -> int:
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    terms = _load_prompt_terms(args, output_dir)
    result = transcriber.transcribe(
        args.audio_path,
        provider=args.provider,
        profile=args.profile,
        prompt_terms=terms,
    )

    _write_result_json(output_dir / "transcript.json", result)
    _write_result_markdown(output_dir / "transcript.md", result)
    return 0


def _run_bakeoff(args, transcriber) -> int:
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    terms = _load_prompt_terms(args, output_dir)
    providers = tuple(value.strip() for value in args.providers.split(",") if value.strip())
    results = []

    for provider in providers:
        result = transcriber.transcribe(
            args.audio_path,
            provider=provider,
            profile=args.profile,
            prompt_terms=terms,
        )
        _write_result_json(output_dir / f"{provider}.json", result)
        results.append(result)

    _write_bakeoff_report(output_dir / "bakeoff_report.md", results, terms)
    return 0


def _load_prompt_terms(args, output_dir: Path) -> tuple[str, ...]:
    terms = list(_read_terms(args.terms_file))
    pack_paths = tuple(getattr(args, "pack_paths", None) or ())
    if pack_paths:
        pack = load_material_pack(pack_paths)
        terms.extend(pack.prompt_terms)
        _write_material_pack(output_dir / "knowledge_pack.json", pack)

    prompt_terms = _dedupe_terms(terms)
    if prompt_terms:
        _write_prompt_terms(output_dir / "prompt_terms.txt", prompt_terms)
    return prompt_terms


def _read_terms(terms_file: str | None) -> tuple[str, ...]:
    if not terms_file:
        return ()
    lines = Path(terms_file).read_text(encoding="utf-8").splitlines()
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
