"""mock end-to-end — 키 없이 transcript.md 생성까지 검증."""

from pathlib import Path

from stt_pipeline.cli import main


def test_mock_end_to_end_generates_transcript(tmp_path, monkeypatch):
    # 키가 환경에 있더라도 mock 을 강제 (결정론적 테스트).
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    # mock provider 는 오디오 내용을 무시하므로 더미 파일이면 충분.
    dummy_audio = tmp_path / "seminar.wav"
    dummy_audio.write_bytes(b"RIFFmock")
    out_dir = tmp_path / "out"

    rc = main(
        [
            "run",
            str(dummy_audio),
            "--profile",
            "seminar",
            "--provider",
            "mock",
            "--llm",
            "mock",
            "--out",
            str(out_dir),
        ]
    )
    assert rc == 0

    md = out_dir / "transcript.md"
    js = out_dir / "transcript.srt"
    assert md.exists() and js.exists()
    assert (out_dir / "transcript.json").exists()

    text = md.read_text(encoding="utf-8")
    # 교정이 실제로 반영됐는지 (오인식 → 정식 표기).
    assert "CRISPR-Cas9" in text
    assert "IL13RA2" in text
    # 레이어 섹션 존재.
    assert "## 🎤 교정 전사" in text
    assert "## 교정 내역" in text
    # 원시 오인식 표기는 본문에서 사라져야 함.
    assert "크리스퍼 캐스나인" not in _transcript_body(text)


def _transcript_body(md: str) -> str:
    """'🎤 교정 전사' 섹션 본문만 추출 (교정 내역 표는 원문 문자열 포함하므로 제외)."""
    start = md.index("## 🎤 교정 전사")
    end = md.index("## 교정 내역")
    return md[start:end]
