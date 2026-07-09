from pathlib import Path
import json
import tempfile
import unittest

from stt_pipeline.local_whisper import (
    MlxWhisperConfig,
    MlxWhisperTranscriber,
    build_mlx_whisper_command,
)


class LocalWhisperTest(unittest.TestCase):
    def test_builds_mlx_whisper_command_without_hard_dependency(self):
        config = MlxWhisperConfig(
            command="mlx_whisper",
            model="mlx-community/whisper-large-v3-turbo",
        )

        command = build_mlx_whisper_command(
            Path("audio.wav"),
            Path("out/mlx"),
            config=config,
        )

        self.assertEqual(command[0], "mlx_whisper")
        self.assertIn("audio.wav", command)
        self.assertIn("--model", command)
        self.assertIn("mlx-community/whisper-large-v3-turbo", command)
        self.assertIn("--output-dir", command)
        self.assertIn("out/mlx", command)
        self.assertIn("--output-format", command)
        self.assertIn("json", command)

    def test_transcriber_runs_mlx_whisper_and_normalizes_json_output(self):
        calls = []

        def runner(command):
            calls.append(command)
            output_dir = Path(command[command.index("--output-dir") + 1])
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "sample.json").write_text(
                json.dumps(
                    {
                        "text": "Local transcript.",
                        "segments": [
                            {
                                "id": 0,
                                "start": 0.0,
                                "end": 2.5,
                                "text": "Local transcript.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            audio_path = root / "sample.wav"
            audio_path.write_bytes(b"fake audio")
            transcriber = MlxWhisperTranscriber(
                runner=runner,
                work_dir=root / "mlx_out",
                config=MlxWhisperConfig(command="mlx_whisper", model="local-model"),
            )

            result = transcriber.transcribe(audio_path, profile="seminar")

        self.assertEqual(result.provider, "mlx-whisper")
        self.assertEqual(result.model, "local-model")
        self.assertEqual(result.text, "Local transcript.")
        self.assertEqual(result.segments[0].segment_id, "seg_000")
        self.assertEqual(result.segments[0].start_seconds, 0.0)
        self.assertEqual(result.segments[0].end_seconds, 2.5)
        self.assertEqual(calls[0][0], "mlx_whisper")


if __name__ == "__main__":
    unittest.main()
