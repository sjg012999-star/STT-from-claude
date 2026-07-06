"""③ LLM 교정 계층 + difflib 검증 (이 시스템의 핵심).

설계 불변 원칙 2: 교정은 difflib diff 검증을 반드시 통과해야 한다.
LLM 이 반환한 corrected_segments 에서, `corrections` 목록으로 설명되지 않는
변경(무단 수정/환각)이 하나라도 있으면 **해당 세그먼트를 원문으로 롤백**하고
플래그를 남긴다. confidence == low 항목은 반영하되 ⚠️(uncertain) 표시한다.

전사 본문과 교정 기록은 분리된 채로 반환된다 (불변원칙 1·4).
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field

from .llm.base import LLMClient
from .models import Correction, Segment


@dataclass
class CorrectionResult:
    segments: list[Segment]  # 교정 반영된(또는 롤백된) 전사 본문
    corrections: list[Correction]  # 감사 레이어
    flags: list[str] = field(default_factory=list)  # 무단수정 롤백 등 경고


def chunk_segments(
    segments: list[Segment], chunk_chars: int = 4000, overlap_chars: int = 500
) -> list[list[Segment]]:
    """세그먼트를 문자 수 기준 청크로 분할(오버랩 포함).

    청크 경계 문맥 단절을 줄이기 위해 직전 청크 끝의 세그먼트들을 겹쳐 담는다.
    """
    if chunk_chars <= 0:
        return [segments] if segments else []
    chunks: list[list[Segment]] = []
    i = 0
    n = len(segments)
    while i < n:
        cur: list[Segment] = []
        cur_len = 0
        j = i
        while j < n and (cur_len + len(segments[j].text) <= chunk_chars or not cur):
            cur.append(segments[j])
            cur_len += len(segments[j].text)
            j += 1
        chunks.append(cur)
        if j >= n:
            break
        # 오버랩: 뒤에서부터 overlap_chars 만큼 되돌린 지점을 다음 청크 시작으로.
        back = 0
        k = j
        while k > i + 1 and back < overlap_chars:
            k -= 1
            back += len(segments[k].text)
        i = k if k > i else j
    return chunks


def _diff_spans(original: str, corrected: str) -> list[tuple[str, str]]:
    """원문↔교정문의 변경 구간을 (원문조각, 교정조각) 목록으로 반환."""
    sm = difflib.SequenceMatcher(a=original, b=corrected, autojunk=False)
    spans: list[tuple[str, str]] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            spans.append((original[i1:i2], corrected[j1:j2]))
    return spans


def _span_is_covered(orig_frag: str, corr_frag: str, entries: list[dict]) -> bool:
    """변경 구간이 corrections 항목 중 하나로 설명되는지 확인.

    구간이 difflib 에 의해 잘게 쪼개질 수 있으므로, 조각이 기록된
    original/corrected 의 부분 문자열이면 '설명됨'으로 본다.
    """
    o = orig_frag.strip()
    c = corr_frag.strip()
    for e in entries:
        eo = str(e.get("original", ""))
        ec = str(e.get("corrected", ""))
        orig_ok = (o == "") or (o in eo)
        corr_ok = (c == "") or (c in ec)
        if orig_ok and corr_ok and not (o == "" and c == ""):
            return True
    return False


def verify_segment_correction(
    original_text: str, corrected_text: str, entries: list[dict]
) -> tuple[str, bool, list[str]]:
    """한 세그먼트의 교정을 diff 검증한다.

    Returns:
        (final_text, rolled_back, flags)
        - 모든 변경이 corrections 로 설명되면 corrected_text 채택.
        - 설명되지 않는 변경이 하나라도 있으면 original_text 로 롤백(rolled_back=True).
    """
    flags: list[str] = []
    if original_text == corrected_text:
        return original_text, False, flags
    spans = _diff_spans(original_text, corrected_text)
    for orig_frag, corr_frag in spans:
        if not _span_is_covered(orig_frag, corr_frag, entries):
            flags.append(
                f"무단 수정 감지 → 원문 롤백: '{orig_frag}' → '{corr_frag}' "
                "(corrections 에 근거 없음)"
            )
            return original_text, True, flags
    return corrected_text, False, flags


def correct_segments(
    segments: list[Segment],
    llm: LLMClient,
    glossary_terms: list[str] | None = None,
    aliases: dict[str, str] | None = None,
    chunk_chars: int = 4000,
    overlap_chars: int = 500,
) -> CorrectionResult:
    """전체 세그먼트를 청크 단위로 교정하고 diff 검증을 적용한다."""
    glossary_terms = glossary_terms or []
    aliases = aliases or {}

    # 청크별 LLM 결과를 세그먼트 id 로 취합 (오버랩 중복은 마지막 결과로 덮어씀).
    corrected_text_by_id: dict[str, str] = {}
    entries_by_id: dict[str, list[dict]] = {}
    for chunk in chunk_segments(segments, chunk_chars, overlap_chars):
        out = llm.correct_chunk(chunk, glossary_terms, aliases)
        for cs in out.get("corrected_segments", []):
            corrected_text_by_id[str(cs["id"])] = str(cs.get("text", ""))
        for e in out.get("corrections", []):
            entries_by_id.setdefault(str(e.get("segment_id")), []).append(e)

    final_segments: list[Segment] = []
    kept_corrections: list[Correction] = []
    flags: list[str] = []

    for seg in segments:
        proposed = corrected_text_by_id.get(seg.id, seg.text)
        seg_entries = entries_by_id.get(seg.id, [])
        final_text, rolled_back, seg_flags = verify_segment_correction(
            seg.text, proposed, seg_entries
        )
        flags.extend(f"[{seg.id}] {m}" for m in seg_flags)

        final_segments.append(
            Segment(
                id=seg.id,
                start=seg.start,
                end=seg.end,
                text=final_text,
                confidence=seg.confidence,
                speaker=seg.speaker,
            )
        )
        # 교정 기록: 롤백되면 rolled_back 표시로 남겨 감사 가능하게.
        for e in seg_entries:
            conf = str(e.get("confidence", "medium")).lower()
            kept_corrections.append(
                Correction(
                    segment_id=seg.id,
                    original=str(e.get("original", "")),
                    corrected=str(e.get("corrected", "")),
                    reason=str(e.get("reason", "")),
                    confidence=conf,
                    rolled_back=rolled_back,
                    uncertain=(conf == "low"),
                )
            )

    return CorrectionResult(
        segments=final_segments, corrections=kept_corrections, flags=flags
    )
