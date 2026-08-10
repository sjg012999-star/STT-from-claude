from pathlib import Path
import tempfile
import unittest

from stt_pipeline.stt_provider import (
    OpenAiSttTranscriber,
    RoutedSttTranscriber,
    build_openai_stt_request,
    default_provider_for_profile,
)


class FakeTranscriptions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "text": "The speaker mentions InTesTiny and IBD.",
            "segments": [
                {
                    "id": 0,
                    "text": "The speaker mentions InTesTiny and IBD.",
                    "start": 1.25,
                    "end": 4.5,
                }
            ],
            "duration": 4.5,
        }


class FakeClient:
    def __init__(self):
        self.transcriptions = FakeTranscriptions()
        self.audio = type("Audio", (), {"transcriptions": self.transcriptions})()


class SttProviderTest(unittest.TestCase):
    def test_profile_defaults_keep_meeting_diarization_separate(self):
        self.assertEqual(default_provider_for_profile("seminar"), "gpt-transcribe")
        self.assertEqual(default_provider_for_profile("lecture"), "gpt-transcribe")
        self.assertEqual(default_provider_for_profile("unknown"), "gpt-transcribe")
        self.assertEqual(default_provider_for_profile("meeting"), "diarize")

    def test_gpt_transcribe_request_uses_compact_terms_as_prompt(self):
        request = build_openai_stt_request(
            provider="gpt-transcribe",
            profile="seminar",
            prompt_terms=["InTesTiny", "IBD", "PET/MRI"],
        )

        self.assertEqual(request.model, "gpt-transcribe")
        self.assertEqual(request.response_format, "json")
        self.assertIn("InTesTiny", request.prompt or "")
        self.assertIn("PET/MRI", request.prompt or "")
        self.assertIsNone(request.chunking_strategy)

    def test_gpt4o_request_uses_compact_terms_as_prompt(self):
        request = build_openai_stt_request(
            provider="gpt-4o",
            profile="seminar",
            prompt_terms=["InTesTiny", "IBD", "PET/MRI"],
        )

        self.assertEqual(request.model, "gpt-4o-transcribe")
        self.assertEqual(request.response_format, "json")
        self.assertIn("InTesTiny", request.prompt or "")
        self.assertIn("PET/MRI", request.prompt or "")
        self.assertIsNone(request.chunking_strategy)

    def test_diarize_request_ignores_prompt_terms_and_sets_auto_chunking(self):
        request = build_openai_stt_request(
            provider="diarize",
            profile="meeting",
            prompt_terms=["InTesTiny", "IBD"],
        )

        self.assertEqual(request.model, "gpt-4o-transcribe-diarize")
        self.assertEqual(request.response_format, "diarized_json")
        self.assertEqual(request.chunking_strategy, "auto")
        self.assertIsNone(request.prompt)

    def test_transcriber_normalizes_openai_response_segments(self):
        client = FakeClient()
        transcriber = OpenAiSttTranscriber(client=client)
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "sample.wav"
            audio_path.write_bytes(b"fake audio")

            result = transcriber.transcribe(
                audio_path,
                provider="gpt-4o",
                profile="seminar",
                prompt_terms=["InTesTiny"],
            )

        self.assertEqual(result.provider, "gpt-4o")
        self.assertEqual(result.model, "gpt-4o-transcribe")
        self.assertEqual(result.text, "The speaker mentions InTesTiny and IBD.")
        self.assertEqual(len(result.segments), 1)
        self.assertEqual(result.segments[0].segment_id, "seg_000")
        self.assertEqual(result.segments[0].start_seconds, 1.25)
        self.assertIsNone(result.segments[0].speaker)
        call = client.transcriptions.calls[0]
        self.assertEqual(call["model"], "gpt-4o-transcribe")
        self.assertIn("prompt", call)

    def test_transcriber_uses_gpt_transcribe_by_default(self):
        client = FakeClient()
        transcriber = OpenAiSttTranscriber(client=client)
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "sample.wav"
            audio_path.write_bytes(b"fake audio")

            result = transcriber.transcribe(
                audio_path,
                profile="seminar",
                prompt_terms=["InTesTiny"],
            )

        self.assertEqual(result.provider, "gpt-transcribe")
        self.assertEqual(result.model, "gpt-transcribe")
        call = client.transcriptions.calls[0]
        self.assertEqual(call["model"], "gpt-transcribe")
        self.assertIn("prompt", call)

    def test_routed_transcriber_dispatches_gemini_audio_provider(self):
        class FakeOpenAi:
            def transcribe(self, audio_path, *, provider=None, profile="seminar", prompt_terms=()):
                raise AssertionError("OpenAI transcriber should not be called")

        class FakeGemini:
            def __init__(self):
                self.calls = []

            def transcribe(self, audio_path, *, provider=None, profile="seminar", prompt_terms=()):
                self.calls.append((provider, tuple(prompt_terms)))
                return _result("gemini-audio", "gemini-test")

        gemini = FakeGemini()
        router = RoutedSttTranscriber(
            openai_transcriber=FakeOpenAi(),
            gemini_transcriber=gemini,
        )

        result = router.transcribe(
            "sample.wav",
            provider="gemini-audio",
            profile="seminar",
            prompt_terms=["InTesTiny"],
        )

        self.assertEqual(result.provider, "gemini-audio")
        self.assertEqual(gemini.calls, [("gemini-audio", ("InTesTiny",))])


def _result(provider, model):
    from stt_pipeline.transcript import TranscriptResult, TranscriptSegment

    return TranscriptResult(
        provider=provider,
        model=model,
        profile="seminar",
        text=f"{provider} transcript",
        segments=(TranscriptSegment(segment_id="seg_001", text=f"{provider} transcript"),),
    )


if __name__ == "__main__":
    unittest.main()
