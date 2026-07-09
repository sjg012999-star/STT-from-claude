from pathlib import Path
import os
import subprocess
import tempfile
import unittest

from stt_pipeline.knowledge_pack import PdfExtractionJob, SlideEvidence, build_knowledge_pack
from stt_pipeline.pdf_tools import FigureTableExtractorConfig, run_pdf_extraction_jobs
from stt_pipeline.reference_lookup import (
    ReferenceLookupHttpClient,
    build_reference_lookup_plans,
    lookup_and_cache_references,
)


class OptionalIntegrationsTest(unittest.TestCase):
    @unittest.skipUnless(
        os.environ.get("STT_RUN_LIVE_REFERENCE_TESTS") == "1",
        "set STT_RUN_LIVE_REFERENCE_TESTS=1 to run live reference lookup",
    )
    def test_live_reference_lookup_can_resolve_reference_metadata(self):
        pack = build_knowledge_pack(
            [
                SlideEvidence(
                    slide_id="slide-27",
                    title="The future of AI in IBD clinical practice",
                    references=[
                        "Iacucci et al., Nat Rev Gastroenterol Hepatol. 2024;21:510. doi:10.1038/s41575-024-00913-8"
                    ],
                )
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            results = lookup_and_cache_references(
                build_reference_lookup_plans(pack),
                cache_dir=Path(tmpdir) / "reference_cache",
                http_client=ReferenceLookupHttpClient(),
            )

        self.assertIn(results[0].status, {"metadata_found", "downloaded"})
        self.assertTrue(results[0].title)

    @unittest.skipUnless(
        os.environ.get("STT_RUN_LIVE_REFERENCE_TESTS") == "1",
        "set STT_RUN_LIVE_REFERENCE_TESTS=1 to run live publisher fallback lookup",
    )
    def test_live_reference_lookup_exposes_publisher_pdf_fallback_candidates(self):
        pack = build_knowledge_pack(
            [
                SlideEvidence(
                    slide_id="slide-mdpi",
                    title="Publisher fallback smoke test",
                    references=[
                        "Author et al., Pharmaceutics 2020. doi:10.3390/pharmaceutics12020123"
                    ],
                )
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            results = lookup_and_cache_references(
                build_reference_lookup_plans(pack),
                cache_dir=Path(tmpdir) / "reference_cache",
                http_client=ReferenceLookupHttpClient(),
            )

        self.assertTrue(results[0].publisher_pdf_urls)
        self.assertTrue(
            any("mdpi.com" in url for url in results[0].publisher_pdf_urls)
        )

    @unittest.skipUnless(
        os.environ.get("STT_PDF_EXTRACTOR_SCRIPT") and os.environ.get("STT_PDF_SAMPLE"),
        "set STT_PDF_EXTRACTOR_SCRIPT and STT_PDF_SAMPLE to run PDF extractor integration",
    )
    def test_configured_pdf_extractor_script_can_process_sample_pdf(self):
        script_path = Path(os.environ["STT_PDF_EXTRACTOR_SCRIPT"])
        sample_pdf = Path(os.environ["STT_PDF_SAMPLE"])

        def runner(command):
            subprocess.run(command, check=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            results = run_pdf_extraction_jobs(
                (
                    PdfExtractionJob(
                        reference="optional integration sample",
                        source_slide_ids=("integration",),
                    ),
                ),
                pdf_paths=(sample_pdf,),
                out_dir=Path(tmpdir) / "pdf_extract",
                config=FigureTableExtractorConfig(script_path=script_path),
                runner=runner,
            )

        self.assertEqual(results[0].status, "planned")
        self.assertEqual(results[0].pdf_path, sample_pdf)


if __name__ == "__main__":
    unittest.main()
