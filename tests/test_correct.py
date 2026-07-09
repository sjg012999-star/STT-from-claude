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
        self.payloads = list(payload) if isinstance(payload, list) else [payload]
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        payload = self.payloads[min(len(self.calls) - 1, len(self.payloads) - 1)]
        return {"output_text": json.dumps(payload)}


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

    def test_openai_corrector_chunks_long_transcripts_with_overlap_context(self):
        segments = tuple(
            TranscriptSegment(
                segment_id=f"seg_{index:03d}",
                text=f"segment {index} mentions term {index}",
                start_seconds=float(index),
                end_seconds=float(index + 1),
            )
            for index in range(1, 6)
        )
        transcript = TranscriptResult(
            provider="gpt-4o",
            model="gpt-4o-transcribe",
            profile="seminar",
            text="\n".join(segment.text for segment in segments),
            segments=segments,
        )
        client = FakeClient(
            [
                {
                    "corrections": [
                        {
                            "segment_id": "seg_001",
                            "original": "term 1",
                            "corrected": "TERM-1",
                            "reason": "test",
                            "confidence": "high",
                        }
                    ]
                },
                {
                    "corrections": [
                        {
                            "segment_id": "seg_003",
                            "original": "term 3",
                            "corrected": "TERM-3",
                            "reason": "test",
                            "confidence": "high",
                        }
                    ]
                },
                {
                    "corrections": [
                        {
                            "segment_id": "seg_005",
                            "original": "term 5",
                            "corrected": "TERM-5",
                            "reason": "test",
                            "confidence": "high",
                        }
                    ]
                },
            ]
        )
        corrector = OpenAiTranscriptCorrector(
            client=client,
            model="gpt-test",
            max_segments_per_request=2,
            overlap_segments=1,
        )

        report = corrector.correct(transcript, prompt_terms=("TERM",))

        self.assertEqual(len(client.responses.calls), 3)
        self.assertEqual(
            [chunk.target_segment_ids for chunk in report.chunks],
            [("seg_001", "seg_002"), ("seg_003", "seg_004"), ("seg_005",)],
        )
        second_input = json.dumps(client.responses.calls[1]["input"])
        self.assertIn("Context-only segments", second_input)
        self.assertIn("seg_002", second_input)
        self.assertIn("Target segments", second_input)
        self.assertIn("seg_003", second_input)
        self.assertIn("TERM-5", report.corrected_result.text)


if __name__ == "__main__":
    unittest.main()
