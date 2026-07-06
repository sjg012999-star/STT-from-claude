"""CLI 진입점 — `stt run <audio> --profile seminar --pack <dir> --provider mock|openai`.

mock provider + mock LLM 조합이면 API 키 없이 end-to-end 로 transcript.md 를 생성한다.
파이프라인 순서: Knowledge Pack → (전처리) → STT → 교정(diff검증) → 요약 → 리포트.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

from . import __version__
from .config import load_glossary, load_profile
from .correct import correct_segments
from .knowledge_pack import build_knowledge_pack
from .llm import get_llm_client
from .preprocess import ffmpeg_available, preprocess_audio
from .report import write_reports
from .stt_providers import get_provider
from .summarize import summarize


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stt", description="학회·강연·회의 STT 파이프라인")
    parser.add_argument("--version", action="version", version=f"stt {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="녹음을 전사·교정·요약해 리포트를 생성")
    run.add_argument("audio", help="입력 녹음 파일 경로")
    run.add_argument("--profile", default="seminar", help="프로필명 (기본: seminar)")
    run.add_argument("--pack", default=None, help="발표자료 디렉토리 (Knowledge Pack)")
    run.add_argument(
        "--provider", default="mock", choices=["mock", "openai"], help="STT provider"
    )
    run.add_argument(
        "--llm",
        default="auto",
        choices=["auto", "mock", "anthropic"],
        help="교정·요약 LLM (auto: 키 있으면 anthropic, 없으면 mock)",
    )
    run.add_argument("--out", default="outputs", help="산출물 디렉토리 (기본: outputs)")
    run.add_argument(
        "--no-preprocess", action="store_true", help="ffmpeg 전처리 건너뛰기"
    )
    run.set_defaults(func=cmd_run)
    return parser


def cmd_run(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)

    # LLM 클라이언트 (교정·요약·비전). auto 는 키 유무로 결정.
    llm = get_llm_client(args.llm)
    _log(f"LLM: {type(llm).__name__}")

    # ⓪ Knowledge Pack — 용어 추출 → glossary_terms 주입
    kp = build_knowledge_pack(args.pack, llm=llm)
    # 프로필에 지정된 용어집(config/glossaries)도 병합
    glossary_terms = list(kp.glossary_terms)
    aliases = dict(kp.aliases)
    for gname in profile.get("glossaries", []) or []:
        g = load_glossary(gname)
        glossary_terms.extend(str(t) for t in g.get("terms", []))
        aliases.update({str(k): str(v) for k, v in g.get("aliases", {}).items()})
    glossary_terms = _dedup(glossary_terms)
    _log(f"용어 주입: {len(glossary_terms)}개, alias {len(aliases)}개")

    # ① 전처리 (mock 이거나 --no-preprocess 면 건너뜀)
    audio_path = Path(args.audio)
    pre_cfg = profile.get("preprocess", {}) or {}
    if args.provider == "mock":
        _log("mock provider — 전처리/ffmpeg 생략")
    elif args.no_preprocess:
        _log("--no-preprocess — 전처리 생략")
    else:
        if not ffmpeg_available():
            _log("경고: ffmpeg 없음 — 원본 오디오를 그대로 사용")
        else:
            tmp = Path(tempfile.gettempdir()) / f"stt_prep_{audio_path.stem}.wav"
            audio_path = preprocess_audio(
                audio_path,
                tmp,
                sample_rate=pre_cfg.get("sample_rate", 16000),
                channels=pre_cfg.get("channels", 1),
                loudnorm=pre_cfg.get("loudnorm", "I=-16:TP=-1.5:LRA=11"),
                trim_silence=pre_cfg.get("trim_silence", True),
            )
            _log(f"전처리 완료: {audio_path}")

    # ② STT
    provider = get_provider(args.provider)
    segments = provider.transcribe(audio_path, glossary_terms)
    _log(f"전사: {len(segments)}개 세그먼트 ({provider.name})")

    # ③ 교정 + diff 검증
    corr_cfg = profile.get("correction", {}) or {}
    result = correct_segments(
        segments,
        llm,
        glossary_terms=glossary_terms,
        aliases=aliases,
        chunk_chars=corr_cfg.get("chunk_chars", 4000),
        overlap_chars=corr_cfg.get("overlap_chars", 500),
    )
    applied = sum(1 for c in result.corrections if not c.rolled_back)
    rolled = sum(1 for c in result.corrections if c.rolled_back)
    _log(f"교정: {applied}건 반영, {rolled}건 롤백, 플래그 {len(result.flags)}개")

    # ④ 요약
    summary_md = summarize(result.segments, profile, llm)

    # ⑤ 리포트
    paths = write_reports(
        args.out,
        segments=result.segments,
        correction=result,
        summary_md=summary_md,
        knowledge_pack=kp,
        profile=profile,
    )
    _log("산출물:")
    for kind, p in paths.items():
        _log(f"  {kind}: {p}")
    return 0


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        x = x.strip()
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
