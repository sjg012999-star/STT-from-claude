import json
import unittest
from pathlib import Path

from stt_pipeline.reference_lookup import ReferenceLookupResult
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

    def test_openai_rich_summarizer_includes_reference_lookup_results(self):
        client = FakeClient(
            {
                "sections": [
                    {
                        "title": "Reference Context",
                        "items": [
                            {
                                "text": "A reference PDF was cached for review.",
                                "source_label": "additional_research",
                                "evidence": "reference_cache/paper.pdf",
                            }
                        ],
                    }
                ]
            }
        )
        summarizer = OpenAiRichSummarizer(client=client, model="gpt-test")
        lookup_result = ReferenceLookupResult(
            reference="Iacucci et al.",
            bibliographic_query="Iacucci et al.",
            source_slide_ids=("slide-27",),
            priority_score=100,
            lookup_url="https://api.crossref.org/works/10...",
            doi="10.1038/example",
            title="Reference title",
            pdf_url="https://example.org/paper.pdf",
            cached_pdf_path=Path("reference_cache/paper.pdf"),
            status="downloaded",
            metadata_source="publisher_pdf_fallback",
            metadata_quality_score=90,
            review_flags=("conflicting_doi",),
        )

        summarizer.summarize(
            _transcript(),
            reference_lookup_results=(lookup_result,),
        )

        prompt = json.dumps(client.responses.calls[0]["input"])
        self.assertIn("Reference lookup results", prompt)
        self.assertIn("reference_cache/paper.pdf", prompt)
        self.assertIn("publisher_pdf_fallback", prompt)
        self.assertIn("conflicting_doi", prompt)

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
