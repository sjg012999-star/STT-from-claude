from pathlib import Path
import tempfile
import unittest

from stt_pipeline.materials import load_material_pack
from stt_pipeline.notes import build_enriched_notes
from stt_pipeline.pdf_tools import PdfExtractionResult
from stt_pipeline.additional_research import AdditionalResearchItem
from stt_pipeline.reference_lookup import ReferenceLookupResult
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

    def test_notes_surface_reference_lookup_quality_and_review_flags(self):
        transcript = TranscriptResult(
            provider="gpt-4o",
            model="gpt-4o-transcribe",
            profile="seminar",
            text="Reference lookup needs review.",
            segments=(
                TranscriptSegment(
                    segment_id="seg_001",
                    text="Reference lookup needs review.",
                ),
            ),
        )
        lookup_result = ReferenceLookupResult(
            reference="Author et al.",
            bibliographic_query="Author et al.",
            source_slide_ids=("slide-1",),
            priority_score=100,
            lookup_url="https://api.openalex.org/works?search=Author",
            doi="10.5555/test",
            title="Matching metadata",
            pdf_url=None,
            cached_pdf_path=None,
            status="metadata_found",
            metadata_source="openalex",
            metadata_quality_score=60,
            review_flags=("conflicting_doi", "pdf_missing"),
        )

        notes = build_enriched_notes(
            transcript,
            reference_lookup_results=(lookup_result,),
        )

        self.assertIn("source: openalex", notes.markdown)
        self.assertIn("quality: 60", notes.markdown)
        self.assertIn("review: conflicting_doi, pdf_missing", notes.markdown)

    def test_notes_include_explicit_additional_research_file_items(self):
        transcript = TranscriptResult(
            provider="gpt-4o",
            model="gpt-4o-transcribe",
            profile="seminar",
            text="External research was provided.",
            segments=(
                TranscriptSegment(
                    segment_id="seg_001",
                    text="External research was provided.",
                ),
            ),
        )
        research_item = AdditionalResearchItem(
            source_path="research/open-web-notes.md",
            title="InTesTiny nanoparticle context",
            summary="RGD targeting appears in the slide figure.",
            url="https://example.org/paper",
            evidence="research/open-web-notes.md",
        )

        notes = build_enriched_notes(
            transcript,
            additional_research_items=(research_item,),
        )

        self.assertIn("InTesTiny nanoparticle context", notes.markdown)
        self.assertIn("https://example.org/paper", notes.markdown)
        self.assertIn("RGD targeting appears", notes.markdown)


if __name__ == "__main__":
    unittest.main()
