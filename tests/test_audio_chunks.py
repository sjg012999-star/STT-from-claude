from pathlib import Path
import tempfile
import unittest

from stt_pipeline.audio_chunks import (
    build_audio_chunk_plan,
    chunk_audio,
    merge_chunk_transcripts,
)
from stt_pipeline.transcript import TranscriptResult, TranscriptSegment


class AudioChunksTest(unittest.TestCase):
    def test_builds_ffmpeg_segment_plan_for_long_recordings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan = build_audio_chunk_plan(root / "seminar.wav", root / "out", chunk_seconds=600)

        self.assertEqual(plan.input_path, root / "seminar.wav")
        self.assertEqual(plan.output_dir, root / "out" / "audio_chunks")
        self.assertEqual(plan.chunk_pattern, root / "out" / "audio_chunks" / "chunk_%03d.wav")
        self.assertEqual(plan.command[0], "ffmpeg")
        self.assertIn("copy", plan.command)
        self.assertIn("-segment_time", plan.command)
        self.assertIn("600", plan.command)

    def test_does_not_stream_copy_non_wav_inputs_into_wav_chunks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan = build_audio_chunk_plan(root / "seminar.mp3", root / "out")

        self.assertNotIn("copy", plan.command)

    def test_chunk_audio_uses_injected_runner_and_returns_sorted_chunks(self):
        calls = []

        def runner(command):
            calls.append(command)
            chunk_dir = Path(command[-1]).parent
            chunk_dir.mkdir(parents=True, exist_ok=True)
            (chunk_dir / "chunk_001.wav").write_bytes(b"chunk 1")
            (chunk_dir / "chunk_000.wav").write_bytes(b"chunk 0")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            chunks = chunk_audio(root / "seminar.wav", root / "out", chunk_seconds=600, runner=runner)

        self.assertEqual([chunk.name for chunk in chunks], ["chunk_000.wav", "chunk_001.wav"])
        self.assertEqual(calls[0][0], "ffmpeg")

    def test_merge_chunk_transcripts_offsets_timestamps_and_segment_ids(self):
        first = TranscriptResult(
            provider="gpt-4o",
            model="gpt-4o-transcribe",
            profile="seminar",
            text="First chunk.",
            segments=(
                TranscriptSegment(
                    segment_id="seg_001",
                    text="First chunk.",
                    start_seconds=0.0,
                    end_seconds=3.0,
                ),
            ),
            usage_seconds=3.0,
        )
        second = TranscriptResult(
            provider="gpt-4o",
            model="gpt-4o-transcribe",
            profile="seminar",
            text="Second chunk.",
            segments=(
                TranscriptSegment(
                    segment_id="seg_001",
                    text="Second chunk.",
                    start_seconds=1.0,
                    end_seconds=4.0,
                ),
            ),
            usage_seconds=3.0,
        )

        merged = merge_chunk_transcripts((first, second), chunk_seconds=600)

        self.assertEqual(merged.text, "First chunk.\nSecond chunk.")
        self.assertEqual([segment.segment_id for segment in merged.segments], ["chunk_001_seg_001", "chunk_002_seg_001"])
        self.assertEqual(merged.segments[1].start_seconds, 601.0)
        self.assertEqual(merged.segments[1].end_seconds, 604.0)
        self.assertEqual(merged.usage_seconds, 6.0)


if __name__ == "__main__":
    unittest.main()
