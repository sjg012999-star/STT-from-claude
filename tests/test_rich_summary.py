import json
import unittest

from stt_pipeline.rich_summary import OpenAiRichSummarizer
from stt_pipeline.transcript import TranscriptResult, TranscriptSegment


def _transcript():
    return TranscriptResult(
        provider="gpt-4o",
        model="gpt-4o-transcribe",
        profile="seminar",
        text="AI in IBD needs validation.",
        segments=(
            TranscriptSegment(
                segment_id="seg_001",
                text="AI in IBD needs validation.",
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


class RichSummaryTest(unittest.TestCase):
    def test_openai_rich_summarizer_renders_source_labeled_sections(self):
        client = FakeClient(
            {
                "sections": [
                    {
                        "title": "Key Findings",
                        "items": [
                            {
                                "text": "AI in IBD needs validation.",
                                "source_label": "speaker_transcript",
                                "evidence": "seg_001",
                            },
                            {
                                "text": "Road map includes reproducibility.",
                                "source_label": "slide_text",
                                "evidence": "slide-27",
                            },
                        ],
                    }
                ]
            }
        )
        summarizer = OpenAiRichSummarizer(client=client, model="gpt-test")

        summary = summarizer.summarize(_transcript(), prompt_terms=("IBD",))

        self.assertIn("# Rich Summary", summary.markdown)
        self.assertIn("## Key Findings", summary.markdown)
        self.assertIn("- [speaker_transcript] AI in IBD needs validation. _(evidence: seg_001)_", summary.markdown)
        self.assertIn("- [slide_text] Road map includes reproducibility. _(evidence: slide-27)_", summary.markdown)
        call = client.responses.calls[0]
        self.assertEqual(call["model"], "gpt-test")
        self.assertEqual(call["text"]["format"]["type"], "json_schema")
        self.assertIn("IBD", json.dumps(call["input"]))

    def test_openai_rich_summarizer_rejects_unlabeled_or_unknown_sources(self):
        client = FakeClient(
            {
                "sections": [
                    {
                        "title": "Bad Section",
                        "items": [
                            {
                                "text": "This has no valid provenance.",
                                "source_label": "model_guess",
                                "evidence": "",
                            }
                        ],
                    }
                ]
            }
        )
        summarizer = OpenAiRichSummarizer(client=client, model="gpt-test")

        with self.assertRaises(ValueError):
            summarizer.summarize(_transcript())


if __name__ == "__main__":
    unittest.main()
