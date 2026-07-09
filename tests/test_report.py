import unittest

from stt_pipeline.report import render_srt
from stt_pipeline.transcript import TranscriptResult, TranscriptSegment


class ReportTest(unittest.TestCase):
    def test_render_srt_from_timestamped_segments(self):
        result = TranscriptResult(
            provider="gpt-4o",
            model="gpt-4o-transcribe",
            profile="seminar",
            text="Hello world.\nNext line.",
            segments=(
                TranscriptSegment(
                    segment_id="seg_001",
                    text="Hello world.",
                    start_seconds=1.25,
                    end_seconds=4.5,
                ),
                TranscriptSegment(
                    segment_id="seg_002",
                    text="Next line.",
                    start_seconds=65.0,
                    end_seconds=67.25,
                    speaker="Speaker 2",
                ),
            ),
        )

        srt = render_srt(result)

        self.assertIn("1\n00:00:01,250 --> 00:00:04,500\nHello world.", srt)
        self.assertIn(
            "2\n00:01:05,000 --> 00:01:07,250\nSpeaker 2: Next line.",
            srt,
        )

    def test_render_srt_skips_segments_without_timestamps(self):
        result = TranscriptResult(
            provider="gpt-4o",
            model="gpt-4o-transcribe",
            profile="seminar",
            text="No timestamp.",
            segments=(TranscriptSegment(segment_id="seg_001", text="No timestamp."),),
        )

        self.assertEqual(render_srt(result), "")


if __name__ == "__main__":
    unittest.main()
