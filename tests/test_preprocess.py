from pathlib import Path
import tempfile
import unittest

from stt_pipeline.preprocess import build_preprocess_plan, preprocess_audio


class PreprocessTest(unittest.TestCase):
    def test_builds_ffmpeg_preprocess_plan_for_stt_upload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_path = root / "raw.wav"
            output_dir = root / "out"

            plan = build_preprocess_plan(input_path, output_dir)

        self.assertEqual(plan.input_path, input_path)
        self.assertEqual(plan.output_path, output_dir / "preprocessed.wav")
        self.assertEqual(plan.command[0], "ffmpeg")
        self.assertIn("-ac", plan.command)
        self.assertIn("1", plan.command)
        self.assertIn("-ar", plan.command)
        self.assertIn("16000", plan.command)
        self.assertIn("loudnorm=I=-16:TP=-1.5:LRA=11", plan.command)

    def test_preprocess_audio_uses_injected_runner_and_returns_output_path(self):
        calls = []

        def runner(command):
            calls.append(command)

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_path = root / "raw.wav"
            output_dir = root / "out"

            output_path = preprocess_audio(input_path, output_dir, runner=runner)

        self.assertEqual(output_path, output_dir / "preprocessed.wav")
        self.assertEqual(calls[0][0], "ffmpeg")
        self.assertEqual(calls[0][-1], str(output_path))


if __name__ == "__main__":
    unittest.main()
