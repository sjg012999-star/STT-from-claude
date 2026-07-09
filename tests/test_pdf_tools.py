from pathlib import Path
import tempfile
import unittest

from stt_pipeline.knowledge_pack import PdfExtractionJob
from stt_pipeline.pdf_tools import (
    FigureTableExtractorConfig,
    build_extraction_command,
    run_pdf_extraction_jobs,
)


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

    def test_runs_extraction_jobs_with_injected_runner_and_manifest(self):
        calls = []

        def runner(command):
            calls.append(command)

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pdf_path = root / "iacucci-2024.pdf"
            pdf_path.write_bytes(b"%PDF-1.7 fake")
            config = FigureTableExtractorConfig(
                script_path=Path("tools/pdf-figure-table-extract/scripts/extract-figures-tables.py")
            )
            jobs = (
                PdfExtractionJob(
                    reference="Iacucci et al., Nature Reviews Gastroenterology & Hepatology 21, 510 (2024)",
                    source_slide_ids=("slide-27",),
                ),
            )

            results = run_pdf_extraction_jobs(
                jobs,
                pdf_paths=(pdf_path,),
                out_dir=root / "pdf-extract",
                config=config,
                runner=runner,
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "planned")
        self.assertEqual(results[0].pdf_path, pdf_path)
        self.assertEqual(calls[0], results[0].command)
        self.assertIn("iacucci-2024", str(results[0].out_dir))


if __name__ == "__main__":
    unittest.main()
