import json
import unittest

from stt_pipeline.correct import (
    Correction,
    OpenAiTranscriptCorrector,
    apply_declared_corrections,
)
from stt_pipeline.transcript import TranscriptResult, TranscriptSegment


def _transcript():
    return TranscriptResult(
        provider="gpt-4o",
        model="gpt-4o-transcribe",
        profile="seminar",
        text="The speaker said in test tiny for IBD.",
        segments=(
            TranscriptSegment(
                segment_id="seg_001",
                text="The speaker said in test tiny for IBD.",
                start_seconds=0.0,
                end_seconds=3.0,
            ),
        ),
    )


class FakeResponses:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return {"output_text": json.dumps(self.payload)}


class FakeClient:
    def __init__(self, payload):
        self.responses = FakeResponses(payload)


class CorrectTest(unittest.TestCase):
    def test_apply_declared_corrections_updates_only_exact_segment_matches(self):
        report = apply_declared_corrections(
            _transcript(),
            [
                Correction(
                    segment_id="seg_001",
                    original="in test tiny",
                    corrected="InTesTiny",
                    reason="domain term",
                    confidence="high",
                ),
                Correction(
                    segment_id="seg_001",
                    original="not in transcript",
                    corrected="hallucinated",
                    reason="bad correction",
                    confidence="low",
                ),
            ],
        )

        self.assertEqual(report.corrected_result.segments[0].text, "The speaker said InTesTiny for IBD.")
        self.assertEqual(report.corrected_result.text, "The speaker said InTesTiny for IBD.")
        self.assertEqual(len(report.applied_corrections), 1)
        self.assertEqual(len(report.rejected_corrections), 1)

    def test_openai_corrector_uses_structured_json_and_applies_payload(self):
        client = FakeClient(
            {
                "corrections": [
                    {
                        "segment_id": "seg_001",
                        "original": "in test tiny",
                        "corrected": "InTesTiny",
                        "reason": "domain term",
                        "confidence": "high",
                    }
                ]
            }
        )
        corrector = OpenAiTranscriptCorrector(client=client, model="gpt-test")

        report = corrector.correct(_transcript(), prompt_terms=("InTesTiny", "IBD"))

        self.assertEqual(report.corrected_result.text, "The speaker said InTesTiny for IBD.")
        call = client.responses.calls[0]
        self.assertEqual(call["model"], "gpt-test")
        self.assertEqual(call["text"]["format"]["type"], "json_schema")
        self.assertIn("InTesTiny", json.dumps(call["input"]))


if __name__ == "__main__":
    unittest.main()
