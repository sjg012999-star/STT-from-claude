"""difflib 무단수정 롤백 검증 — 설계 불변 원칙 2의 핵심 테스트."""

from stt_pipeline.correct import (
    correct_segments,
    verify_segment_correction,
)
from stt_pipeline.llm.mock_client import MockLLMClient
from stt_pipeline.models import Segment


def test_authorized_change_is_kept():
    # corrections 에 근거가 있는 변경 → 교정문 채택.
    entries = [{"original": "안녕하세요", "corrected": "안녕하십니까"}]
    final, rolled_back, flags = verify_segment_correction(
        "안녕하세요 여러분", "안녕하십니까 여러분", entries
    )
    assert final == "안녕하십니까 여러분"
    assert rolled_back is False
    assert flags == []


def test_unauthorized_change_is_rolled_back():
    # corrections 가 비어 있는데 텍스트가 바뀜 → 무단 수정 → 원문 롤백 + 플래그.
    final, rolled_back, flags = verify_segment_correction(
        "안녕하세요 여러분", "안녕하십니까 여러분", entries=[]
    )
    assert final == "안녕하세요 여러분"  # 원문으로 롤백
    assert rolled_back is True
    assert len(flags) == 1


def test_partial_unauthorized_change_rolls_back_segment():
    # 하나는 근거 있고 하나는 없음 → 세그먼트 전체 롤백.
    entries = [{"original": "캐스나인", "corrected": "Cas9"}]
    original = "크리스퍼 캐스나인을 여기서 다르게 말함"
    corrected = "크리스퍼 Cas9을 여기서 완전히 새로 씀"  # 뒷부분은 근거 없음
    final, rolled_back, flags = verify_segment_correction(original, corrected, entries)
    assert final == original
    assert rolled_back is True


def test_identical_text_no_flag():
    final, rolled_back, flags = verify_segment_correction("동일", "동일", [])
    assert final == "동일"
    assert rolled_back is False
    assert flags == []


def test_correct_segments_end_to_end_with_mock_llm():
    # mock LLM 은 well-behaved: 내장 phonetic 교정을 corrections 에 모두 기록.
    segs = [
        Segment(id="seg_001", start=0, end=5, text="크리스퍼 캐스나인을 사용했다"),
        Segment(id="seg_002", start=5, end=10, text="변화 없는 문장"),
    ]
    result = correct_segments(segs, MockLLMClient(), glossary_terms=[])
    # 교정이 반영되고 롤백은 없어야 한다.
    assert result.segments[0].text == "CRISPR-Cas9을 사용했다"
    assert result.segments[1].text == "변화 없는 문장"
    assert any(not c.rolled_back for c in result.corrections)
    assert all(not c.rolled_back for c in result.corrections)
    assert result.flags == []


def test_low_confidence_marked_uncertain():
    segs = [Segment(id="seg_001", start=0, end=5, text="스몰리 연구팀")]
    result = correct_segments(segs, MockLLMClient())
    # "스몰리"→"Smillie" 는 내장 맵에서 confidence low → uncertain 표시.
    smillie = [c for c in result.corrections if c.corrected == "Smillie"]
    assert smillie and smillie[0].uncertain is True
