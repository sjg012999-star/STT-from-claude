import unittest
from pathlib import Path

from stt_pipeline.knowledge_pack import PdfExtractionJob
from stt_pipeline.pdf_tools import FigureTableExtractorConfig, build_extraction_command


class PdfToolsTest(unittest.TestCase):
    def test_builds_portable_existing_skill_command(self):
        config = FigureTableExtractorConfig(
            script_path=Path("tools/pdf-figure-table-extract/scripts/extract-figures-tables.py")
        )
        job = PdfExtractionJob(
            reference="Iacucci et al., Nature Reviews Gastroenterology & Hepatology 21, 510 (2024)",
            source_slide_ids=("slide-27",),
        )

        command = build_extraction_command(
            job,
            pdf_path=Path("references/iacucci-2024.pdf"),
            out_dir=Path("outputs/iacucci-2024"),
            config=config,
        )

        self.assertEqual(
            command,
            (
                "python3",
                "tools/pdf-figure-table-extract/scripts/extract-figures-tables.py",
                "--pdf",
                "references/iacucci-2024.pdf",
                "--out",
                "outputs/iacucci-2024",
                "--reference",
                "Iacucci et al., Nature Reviews Gastroenterology & Hepatology 21, 510 (2024)",
            ),
        )

    def test_page_render_mode_is_available_for_low_confidence_visual_pdfs(self):
        config = FigureTableExtractorConfig(
            script_path=Path("tools/pdf-figure-table-extract/scripts/extract-figures-tables.py"),
            page_render=True,
        )
        job = PdfExtractionJob(reference="unpublished conference slide reference", source_slide_ids=("slide-23",))

        command = build_extraction_command(
            job,
            pdf_path=Path("references/unknown.pdf"),
            out_dir=Path("outputs/unknown"),
            config=config,
        )

        self.assertIn("--page-render", command)


if __name__ == "__main__":
    unittest.main()
