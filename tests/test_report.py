"""SRT / JSON / MD 출력 테스트 + 레이어 분리 확인."""

import json

from stt_pipeline.correct import CorrectionResult
from stt_pipeline.models import Correction, KnowledgePack, Segment, SlideFact
from stt_pipeline.report import write_reports, _render_srt


def _sample_segments():
    return [
        Segment(id="seg_000", start=0.0, end=2.5, text="첫 번째 문장입니다."),
        Segment(id="seg_001", start=2.5, end=5.0, text="CRISPR-Cas9 실험."),
    ]


def test_srt_timestamp_format():
    segs = [Segment(id="a", start=3661.5, end=3663.0, text="hello")]
    srt = _render_srt(segs)
    assert "01:01:01,500 --> 01:01:03,000" in srt
    assert srt.startswith("1\n")
    assert "hello" in srt


def test_write_reports_creates_three_files(tmp_path):
    segs = _sample_segments()
    corr = CorrectionResult(
        segments=segs,
        corrections=[
            Correction(
                segment_id="seg_001",
                original="크리스퍼 캐스나인",
                corrected="CRISPR-Cas9",
                reason="음성 오인식",
                confidence="high",
            )
        ],
        flags=[],
    )
    paths = write_reports(
        tmp_path,
        segments=segs,
        correction=corr,
        summary_md="## 요약\n내용",
        knowledge_pack=None,
        profile={"name": "seminar"},
    )
    for p in paths.values():
        assert p.exists()

    # JSON: 전사와 교정이 분리된 키로 존재해야 한다 (불변원칙 1).
    data = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert "segments" in data and "corrections" in data
    assert data["segments"][1]["text"] == "CRISPR-Cas9 실험."
    assert data["corrections"][0]["corrected"] == "CRISPR-Cas9"

    # MD: 교정 전사 섹션과 교정 내역 표가 별도 헤딩으로 존재.
    md = paths["md"].read_text(encoding="utf-8")
    assert "## 🎤 교정 전사" in md
    assert "## 교정 내역" in md
    assert "CRISPR-Cas9" in md


def test_rolled_back_correction_shown_separately(tmp_path):
    segs = _sample_segments()
    corr = CorrectionResult(
        segments=segs,
        corrections=[
            Correction(
                segment_id="seg_000",
                original="첫 번째",
                corrected="완전히 다른 말",
                reason="",
                confidence="high",
                rolled_back=True,
            )
        ],
        flags=["[seg_000] 무단 수정 감지 → 원문 롤백"],
    )
    paths = write_reports(
        tmp_path,
        segments=segs,
        correction=corr,
        summary_md="## 요약",
        profile={"name": "seminar"},
    )
    md = paths["md"].read_text(encoding="utf-8")
    assert "롤백된 항목" in md
    assert "검증 플래그" in md


def test_knowledge_pack_layers_not_merged(tmp_path):
    segs = _sample_segments()
    corr = CorrectionResult(segments=segs, corrections=[], flags=[])
    kp = KnowledgePack(
        glossary_terms=["CRISPR-Cas9", "IL13RA2"],
        slide_facts=[
            SlideFact(source="slide1.pptx", slide_only_facts=["366,650 세포 분석"])
        ],
    )
    paths = write_reports(
        tmp_path,
        segments=segs,
        correction=corr,
        summary_md="## 요약",
        knowledge_pack=kp,
        profile={"name": "seminar"},
    )
    md = paths["md"].read_text(encoding="utf-8")
    # 📊 슬라이드 사실과 🔍 보강이 별도 섹션으로 (전사와 병합 안 됨).
    assert "## 📊 슬라이드 사실" in md
    assert "## 🔍 AI 조사 보강" in md
    assert "366,650 세포 분석" in md
