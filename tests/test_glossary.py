from pathlib import Path
import tempfile
import unittest

from stt_pipeline.correct import Correction, CorrectionReport
from stt_pipeline.glossary import (
    build_glossary_entries_from_corrections,
    load_glossary_tsv,
    merge_glossary_entries,
    write_glossary_tsv,
)
from stt_pipeline.transcript import TranscriptResult, TranscriptSegment


def _report():
    transcript = TranscriptResult(
        provider="gpt-4o",
        model="gpt-4o-transcribe",
        profile="seminar",
        text="The speaker said InTesTiny.",
        segments=(TranscriptSegment(segment_id="seg_001", text="The speaker said InTesTiny."),),
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
        ),
        rejected_corrections=(
            Correction(
                segment_id="seg_001",
                original="maybe",
                corrected="MAYBE",
                reason="not applied",
                confidence="low",
            ),
        ),
    )


class GlossaryTest(unittest.TestCase):
    def test_builds_glossary_entries_from_applied_corrections_only(self):
        entries = build_glossary_entries_from_corrections(_report())

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].original, "in test tiny")
        self.assertEqual(entries[0].corrected, "InTesTiny")
        self.assertEqual(entries[0].count, 1)
        self.assertEqual(entries[0].confidence, "high")

    def test_merges_existing_glossary_entries_by_correction_pair(self):
        existing = build_glossary_entries_from_corrections(_report())
        merged = merge_glossary_entries(
            existing,
            build_glossary_entries_from_corrections(_report()),
        )

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].count, 2)

    def test_writes_and_loads_glossary_tsv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "glossary.tsv"
            write_glossary_tsv(path, build_glossary_entries_from_corrections(_report()))
            loaded = load_glossary_tsv(path)

        self.assertEqual(loaded[0].original, "in test tiny")
        self.assertEqual(loaded[0].corrected, "InTesTiny")
        self.assertEqual(loaded[0].count, 1)


if __name__ == "__main__":
    unittest.main()
