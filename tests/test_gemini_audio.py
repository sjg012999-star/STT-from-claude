import json
from pathlib import Path
import tempfile
import unittest

from stt_pipeline.gemini_audio import GeminiAudioTranscriber


class FakeFiles:
    def __init__(self):
        self.uploads = []
        self.deletes = []

    def upload(self, *, file):
        self.uploads.append(file)
        return type("UploadedFile", (), {"name": "files/test-audio"})()

    def delete(self, *, name):
        self.deletes.append(name)


class FakeModels:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return type("Response", (), {"text": json.dumps(self.payload)})()


class FakeClient:
    def __init__(self, payload):
        self.files = FakeFiles()
        self.models = FakeModels(payload)


class GeminiAudioTest(unittest.TestCase):
    def test_transcribes_structured_audio_and_deletes_uploaded_file(self):
        client = FakeClient(
            {
                "text": "Speaker 1 discusses InTesTiny and IBD.",
                "segments": [
                    {
                        "id": "seg_001",
                        "start_seconds": 1.25,
                        "end_seconds": 4.5,
                        "speaker": "Speaker 1",
                        "text": "Speaker 1 discusses InTesTiny and IBD.",
                    }
                ],
            }
        )
        transcriber = GeminiAudioTranscriber(client=client, model="gemini-test")

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "sample.wav"
            audio_path.write_bytes(b"fake audio")
            result = transcriber.transcribe(
                audio_path,
                provider="gemini-audio",
                profile="seminar",
                prompt_terms=["InTesTiny", "IBD", "InTesTiny"],
            )

        self.assertEqual(result.provider, "gemini-audio")
        self.assertEqual(result.model, "gemini-test")
        self.assertEqual(result.segments[0].speaker, "Speaker 1")
        self.assertEqual(result.segments[0].start_seconds, 1.25)
        self.assertEqual(result.usage_seconds, 4.5)
        prompt = client.models.calls[0]["contents"][1]
        self.assertEqual(prompt.count("InTesTiny"), 1)
        self.assertIn("Do not summarize", prompt)
        self.assertEqual(client.files.deletes, ["files/test-audio"])

    def test_rejects_non_json_model_output_and_still_deletes_upload(self):
        client = FakeClient({})
        client.models.generate_content = lambda **kwargs: type(
            "Response", (), {"text": "not json"}
        )()
        transcriber = GeminiAudioTranscriber(client=client, model="gemini-test")

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "sample.wav"
            audio_path.write_bytes(b"fake audio")
            with self.assertRaisesRegex(ValueError, "valid JSON"):
                transcriber.transcribe(audio_path, provider="gemini-audio")

        self.assertEqual(client.files.deletes, ["files/test-audio"])


if __name__ == "__main__":
    unittest.main()
