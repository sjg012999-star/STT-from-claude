import unittest

from stt_pipeline.correct import Correction, CorrectionReport
from stt_pipeline.summarize import build_basic_summary
from stt_pipeline.transcript import TranscriptResult, TranscriptSegment


class SummarizeTest(unittest.TestCase):
    def test_builds_profile_summary_without_mixing_sources(self):
        transcript = TranscriptResult(
            provider="gpt-4o",
            model="gpt-4o-transcribe",
            profile="seminar",
            text="First finding about IBD. Second finding about InTesTiny.",
            segments=(
                TranscriptSegment(
                    segment_id="seg_001",
                    text="First finding about IBD.",
                    start_seconds=0.0,
                    end_seconds=2.0,
                ),
                TranscriptSegment(
                    segment_id="seg_002",
                    text="Second finding about InTesTiny.",
                    start_seconds=2.0,
                    end_seconds=4.0,
                ),
            ),
        )
        correction_report = CorrectionReport(
            corrected_result=transcript,
            applied_corrections=(
                Correction(
                    segment_id="seg_002",
                    original="in test tiny",
                    corrected="InTesTiny",
                    reason="domain term",
                    confidence="high",
                ),
            ),
            rejected_corrections=(),
        )

        summary = build_basic_summary(transcript, correction_report=correction_report)

        self.assertIn("# Seminar Summary", summary.markdown)
        self.assertIn("## Speaker Transcript", summary.markdown)
        self.assertIn("## Correction Notes", summary.markdown)
        self.assertIn("InTesTiny", summary.markdown)
        self.assertIn("source: transcript", summary.markdown)


if __name__ == "__main__":
    unittest.main()
