"""⑤ 산출물 — transcript.md / transcript.json / transcript.srt.

레이어 분리 원칙(불변원칙 1·4)을 출력에서도 강제한다:
  - 🎤 전사 본문        : 교정된 세그먼트 (사실 레이어)
  - 교정 내역 표         : 별도 섹션 (감사 레이어, 무단수정 롤백/⚠️ 표시)
  - 📊 슬라이드 사실     : Knowledge Pack, 전사와 분리
  - 🔍 AI 조사 보강      : Phase 3 (여기서는 골격/placeholder만)
이 레이어들을 한 문단에 섞지 않는다.
"""

from __future__ import annotations

import json
from pathlib import Path

from .correct import CorrectionResult
from .models import KnowledgePack, Segment


def write_reports(
    out_dir: str | Path,
    *,
    segments: list[Segment],
    correction: CorrectionResult,
    summary_md: str,
    knowledge_pack: KnowledgePack | None = None,
    profile: dict | None = None,
) -> dict[str, Path]:
    """세 산출물을 out_dir 에 쓴다. 생성된 경로 dict 반환."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "md": out_dir / "transcript.md",
        "json": out_dir / "transcript.json",
        "srt": out_dir / "transcript.srt",
    }
    paths["md"].write_text(
        _render_markdown(segments, correction, summary_md, knowledge_pack, profile),
        encoding="utf-8",
    )
    paths["json"].write_text(
        _render_json(segments, correction, summary_md, knowledge_pack, profile),
        encoding="utf-8",
    )
    paths["srt"].write_text(_render_srt(segments), encoding="utf-8")
    return paths


# --------------------------------------------------------------------------- md
def _render_markdown(segments, correction, summary_md, kp, profile) -> str:
    profile_name = (profile or {}).get("name", "seminar")
    out: list[str] = [f"# 전사 리포트 — {profile_name}", ""]

    # 1) 요약 (별도 섹션)
    out.append(summary_md.rstrip())
    out.append("")

    # 2) 🎤 교정 전사 본문 (사실 레이어)
    out.append("## 🎤 교정 전사")
    out.append("")
    for s in segments:
        ts = _fmt_ts_hms(s.start)
        warn = ""
        if s.confidence is not None and s.confidence < 0.7:
            warn = " ⚠️"  # 저신뢰 구간 — 사람 확인 유도
        spk = f"**{s.speaker}** " if s.speaker else ""
        out.append(f"- `[{ts}]`{warn} {spk}{s.text}")
    out.append("")

    # 3) 교정 내역 표 (감사 레이어 — 본문과 분리)
    out.append("## 교정 내역")
    out.append("")
    applied = [c for c in correction.corrections if not c.rolled_back]
    rolled = [c for c in correction.corrections if c.rolled_back]
    if applied:
        out.append("| 세그먼트 | 원문 | 교정 | 근거 | 신뢰도 |")
        out.append("|---|---|---|---|---|")
        for c in applied:
            conf = c.confidence + (" ⚠️" if c.uncertain else "")
            out.append(
                f"| {c.segment_id} | {_esc(c.original)} | {_esc(c.corrected)} "
                f"| {_esc(c.reason)} | {conf} |"
            )
    else:
        out.append("_(반영된 교정 없음)_")
    out.append("")

    if rolled:
        out.append("### ⚠️ 무단 수정으로 롤백된 항목 (diff 검증 실패)")
        out.append("")
        out.append("| 세그먼트 | LLM 제안 원문 | LLM 제안 교정 | 처리 |")
        out.append("|---|---|---|---|")
        for c in rolled:
            out.append(
                f"| {c.segment_id} | {_esc(c.original)} | {_esc(c.corrected)} "
                f"| 원문 유지 (근거 없음) |"
            )
        out.append("")

    if correction.flags:
        out.append("### 검증 플래그")
        out.append("")
        for f in correction.flags:
            out.append(f"- {f}")
        out.append("")

    # 4) 📊 슬라이드 사실 (Knowledge Pack — 전사와 분리)
    if kp and (kp.slide_facts or kp.glossary_terms):
        out.append("## 📊 슬라이드 사실 (자료 기반, 전사와 분리)")
        out.append("")
        if kp.glossary_terms:
            out.append("**주입 용어(🔤):** " + ", ".join(kp.glossary_terms))
            out.append("")
        for sf in kp.slide_facts:
            out.append(f"### {sf.source}")
            for fact in sf.slide_only_facts:
                out.append(f"- {fact}")
            out.append("")
        # 🔍 레이어는 Phase 3 — 병합 금지, placeholder 만.
        out.append("## 🔍 AI 조사 보강")
        out.append("")
        out.append(
            "_Phase 3 미구현. 보강 항목은 출처 확보 시에만 기록되며, "
            "못 찾으면 '확인 불가'로 남깁니다 (전사 본문과 병합 금지)._"
        )
        out.append("")

    return "\n".join(out).rstrip() + "\n"


# ------------------------------------------------------------------------- json
def _render_json(segments, correction, summary_md, kp, profile) -> str:
    data = {
        "profile": (profile or {}).get("name", "seminar"),
        "summary": summary_md,
        # 🎤 사실 레이어
        "segments": [s.to_dict() for s in segments],
        # 감사 레이어 (분리)
        "corrections": [c.to_dict() for c in correction.corrections],
        "flags": correction.flags,
        # 📊 자료 레이어 (분리)
        "knowledge_pack": kp.to_dict() if kp else None,
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


# -------------------------------------------------------------------------- srt
def _render_srt(segments: list[Segment]) -> str:
    blocks: list[str] = []
    for i, s in enumerate(segments, start=1):
        blocks.append(
            f"{i}\n{_fmt_ts_srt(s.start)} --> {_fmt_ts_srt(s.end)}\n{s.text}\n"
        )
    return "\n".join(blocks)


# ---------------------------------------------------------------------- helpers
def _fmt_ts_hms(seconds: float) -> str:
    seconds = max(0.0, seconds)
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _fmt_ts_srt(seconds: float) -> str:
    seconds = max(0.0, seconds)
    ms = int(round((seconds - int(seconds)) * 1000))
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _esc(text: str) -> str:
    """markdown 표 셀 이스케이프 (파이프/개행)."""
    return text.replace("|", "\\|").replace("\n", " ")
