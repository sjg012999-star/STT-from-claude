from pathlib import Path
import json
import tempfile
import unittest

from stt_pipeline.cli import main
from stt_pipeline.transcript import TranscriptResult, TranscriptSegment


class FakeTranscriber:
    def __init__(self):
        self.calls = []

    def transcribe(self, audio_path, *, provider=None, profile="seminar", prompt_terms=()):
        self.calls.append(
            {
                "audio_path": Path(audio_path),
                "provider": provider,
                "profile": profile,
                "prompt_terms": tuple(prompt_terms),
            }
        )
        selected_provider = provider or "gpt-4o"
        return TranscriptResult(
            provider=selected_provider,
            model=f"model-for-{selected_provider}",
            profile=profile,
            text=f"Transcript from {selected_provider}",
            segments=(
                TranscriptSegment(
                    segment_id="seg_001",
                    text=f"Transcript from {selected_provider}",
                    start_seconds=0.0,
                    end_seconds=3.0,
                    speaker="Speaker 1" if selected_provider == "diarize" else None,
                ),
            ),
            usage_seconds=3.0,
        )


class CliTest(unittest.TestCase):
    def test_transcribe_writes_json_and_markdown_with_terms(self):
        transcriber = FakeTranscriber()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            audio_path = root / "sample.wav"
            terms_path = root / "terms.txt"
            output_dir = root / "out"
            audio_path.write_bytes(b"fake audio")
            terms_path.write_text("InTesTiny\nIBD\n", encoding="utf-8")

            exit_code = main(
                [
                    "transcribe",
                    str(audio_path),
                    "--profile",
                    "seminar",
                    "--provider",
                    "gpt-4o",
                    "--terms-file",
                    str(terms_path),
                    "--output",
                    str(output_dir),
                ],
                transcriber=transcriber,
            )

            payload = json.loads((output_dir / "transcript.json").read_text(encoding="utf-8"))
            markdown = (output_dir / "transcript.md").read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual(transcriber.calls[0]["prompt_terms"], ("InTesTiny", "IBD"))
        self.assertEqual(payload["provider"], "gpt-4o")
        self.assertEqual(payload["segments"][0]["segment_id"], "seg_001")
        self.assertIn("# Transcript", markdown)
        self.assertIn("Transcript from gpt-4o", markdown)

    def test_bakeoff_writes_provider_outputs_and_report(self):
        transcriber = FakeTranscriber()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            audio_path = root / "sample.wav"
            output_dir = root / "bakeoff"
            audio_path.write_bytes(b"fake audio")

            exit_code = main(
                [
                    "bakeoff",
                    str(audio_path),
                    "--profile",
                    "seminar",
                    "--providers",
                    "whisper-1,gpt-4o-mini",
                    "--output",
                    str(output_dir),
                ],
                transcriber=transcriber,
            )

            whisper_payload = json.loads(
                (output_dir / "whisper-1.json").read_text(encoding="utf-8")
            )
            report = (output_dir / "bakeoff_report.md").read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual([call["provider"] for call in transcriber.calls], ["whisper-1", "gpt-4o-mini"])
        self.assertEqual(whisper_payload["model"], "model-for-whisper-1")
        self.assertIn("whisper-1", report)
        self.assertIn("gpt-4o-mini", report)


if __name__ == "__main__":
    unittest.main()
