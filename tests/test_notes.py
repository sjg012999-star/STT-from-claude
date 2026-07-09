from pathlib import Path
import tempfile
import unittest

from stt_pipeline.materials import load_material_pack
from stt_pipeline.notes import build_enriched_notes
from stt_pipeline.pdf_tools import PdfExtractionResult
from stt_pipeline.transcript import TranscriptResult, TranscriptSegment


class NotesTest(unittest.TestCase):
    def test_builds_source_separated_notes_from_transcript_materials_and_pdf_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            materials_dir = root / "materials"
            pdf_path = materials_dir / "iacucci-2024.pdf"
            materials_dir.mkdir()
            (materials_dir / "slides.md").write_text(
                "\n".join(
                    [
                        "The future of AI in IBD clinical practice",
                        "Iacucci et al., Nature Reviews Gastroenterology & Hepatology 21, 510 (2024)",
                        "Road map to implementation requires robust study design and reproducibility.",
                    ]
                ),
                encoding="utf-8",
            )
            pdf_path.write_bytes(b"%PDF-1.7 fake")
            pack = load_material_pack([materials_dir])
            pdf_result = PdfExtractionResult(
                reference="Iacucci et al., Nature Reviews Gastroenterology & Hepatology 21, 510 (2024)",
                pdf_path=pdf_path,
                out_dir=root / "pdf_extract" / "iacucci-2024",
                command=("python3", "extract.py"),
                status="planned",
                source_slide_ids=("slides",),
            )
            transcript = TranscriptResult(
                provider="gpt-4o",
                model="gpt-4o-transcribe",
                profile="seminar",
                text="The speaker discussed AI in IBD.",
                segments=(
                    TranscriptSegment(
                        segment_id="seg_001",
                        text="The speaker discussed AI in IBD.",
                        start_seconds=0.0,
                        end_seconds=3.0,
                    ),
                ),
            )

            notes = build_enriched_notes(
                transcript,
                material_pack=pack,
                pdf_results=(pdf_result,),
            )

        self.assertIn("# Enriched Notes", notes.markdown)
        self.assertIn("## Speaker Transcript", notes.markdown)
        self.assertIn("_source: speaker_transcript_", notes.markdown)
        self.assertIn("## Slide Text", notes.markdown)
        self.assertIn("_source: slide_text_", notes.markdown)
        self.assertIn("## Reference PDF", notes.markdown)
        self.assertIn("_source: reference_pdf_", notes.markdown)
        self.assertIn("Iacucci et al.", notes.markdown)
        self.assertIn("pdf_extract/iacucci-2024", notes.markdown)
        self.assertIn("## Additional Research", notes.markdown)
        self.assertIn("_source: additional_research_", notes.markdown)
        self.assertIn("## Needs Review", notes.markdown)


if __name__ == "__main__":
    unittest.main()
