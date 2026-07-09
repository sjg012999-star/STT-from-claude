from pathlib import Path
import json
import tempfile
import unittest

from stt_pipeline.correct import Correction, CorrectionReport
from stt_pipeline.reference_lookup import ReferenceLookupResult
from stt_pipeline.review import (
    build_review_queue,
    filter_report_to_accepted_glossary_corrections,
    load_review_decisions,
    review_queue_to_dict,
)
from stt_pipeline.transcript import TranscriptResult, TranscriptSegment


def _report_with_two_corrections():
    transcript = TranscriptResult(
        provider="gpt-4o",
        model="gpt-4o-transcribe",
        profile="seminar",
        text="The speaker said InTesTiny and IBD.",
        segments=(
            TranscriptSegment(
                segment_id="seg_001",
                text="The speaker said InTesTiny and IBD.",
            ),
        ),
    )
    return CorrectionReport(
        corrected_result=transcript,
        applied_corrections=(
            Correction(
                segment_id="seg_001",
                original="in test tiny",
                corrected="InTesTiny",
                reason="domain term",
                confidence="high",
            ),
            Correction(
                segment_id="seg_001",
                original="eye bee dee",
                corrected="IBD",
                reason="abbreviation",
                confidence="medium",
            ),
        ),
        rejected_corrections=(),
    )


class ReviewTest(unittest.TestCase):
    def test_builds_review_queue_for_glossary_candidates_and_low_quality_metadata(self):
        reference_result = ReferenceLookupResult(
            reference="Author et al.",
            bibliographic_query="Author et al.",
            source_slide_ids=("slide-1",),
            priority_score=100,
            lookup_url="https://api.openalex.org/works?search=Author",
            doi="10.5555/test",
            title="Candidate metadata",
            pdf_url=None,
            cached_pdf_path=None,
            status="metadata_found",
            metadata_source="openalex",
            metadata_quality_score=55,
            review_flags=("pdf_missing",),
        )

        items = build_review_queue(
            correction_report=_report_with_two_corrections(),
            reference_lookup_results=(reference_result,),
        )
        payload = review_queue_to_dict(items)

        self.assertEqual(len(items), 3)
        self.assertEqual(items[0].kind, "glossary_candidate")
        self.assertEqual(items[0].status, "pending")
        self.assertEqual(items[0].payload["corrected"], "InTesTiny")
        self.assertEqual(items[-1].kind, "reference_metadata")
        self.assertIn("pdf_missing", items[-1].payload["review_flags"])
        self.assertEqual(payload["items"][-1]["status"], "pending")

    def test_filters_glossary_corrections_to_accepted_review_decisions(self):
        report = _report_with_two_corrections()
        queue = list(build_review_queue(correction_report=report))
        queue[0] = queue[0].with_status("accepted")
        queue[1] = queue[1].with_status("rejected")

        with tempfile.TemporaryDirectory() as tmpdir:
            decisions_path = Path(tmpdir) / "review_queue.json"
            decisions_path.write_text(
                json.dumps(review_queue_to_dict(tuple(queue)), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            decisions = load_review_decisions(decisions_path)
            filtered = filter_report_to_accepted_glossary_corrections(report, decisions)

        self.assertEqual(len(filtered.applied_corrections), 1)
        self.assertEqual(filtered.applied_corrections[0].corrected, "InTesTiny")


if __name__ == "__main__":
    unittest.main()
