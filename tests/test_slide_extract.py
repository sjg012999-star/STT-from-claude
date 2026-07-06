import unittest

from stt_pipeline.knowledge_pack import EvidenceGrade, build_knowledge_pack
from stt_pipeline.slide_extract import SlideOcrInput, extract_slide_evidence


class SlideExtractTest(unittest.TestCase):
    def test_extracts_reference_sentences_figure_context_and_terms(self):
        slide = SlideOcrInput(
            slide_id="slide-27",
            title="The future of AI in IBD clinical practice",
            text_lines=[
                "The future of AI in IBD clinical practice",
                "Road map to implementation requires cost-effectiveness, audit, data standardization, robust study design, reproducibility, and ethical and regulatory standards.",
                "Next-generation AI in IBD: Endo-histo-omics, AI-assisted intestinal barrier, AI-driven remote monitoring and wearables, Large language models",
                "Iacucci et al., Nature Reviews Gastroenterology & Hepatology 21, 510 (2024)",
                "Physicians Patients Regulatory bodies Industry Environment",
            ],
        )

        evidence = extract_slide_evidence(slide)

        self.assertEqual(evidence.slide_id, "slide-27")
        self.assertEqual(
            evidence.references,
            ["Iacucci et al., Nature Reviews Gastroenterology & Hepatology 21, 510 (2024)"],
        )
        self.assertIn(
            "Road map to implementation requires cost-effectiveness, audit, data standardization, robust study design, reproducibility, and ethical and regulatory standards.",
            evidence.full_sentences,
        )
        self.assertIn(
            "Next-generation AI in IBD: Endo-histo-omics, AI-assisted intestinal barrier, AI-driven remote monitoring and wearables, Large language models",
            evidence.figure_contexts,
        )
        self.assertIn("IBD", evidence.named_entities)
        self.assertIn("Large language models", evidence.named_entities)
        self.assertIn("audit", evidence.isolated_keywords)

    def test_ocr_slides_feed_reference_first_knowledge_pack(self):
        slides = [
            SlideOcrInput(
                slide_id="slide-27",
                title="The future of AI in IBD clinical practice",
                text_lines=[
                    "Iacucci et al., Nature Reviews Gastroenterology & Hepatology 21, 510 (2024)",
                    "Road map to implementation requires cost-effectiveness and robust study design.",
                ],
            ),
            SlideOcrInput(
                slide_id="slide-28",
                title="AI implementation barriers",
                text_lines=[
                    "Iacucci et al., Nature Reviews Gastroenterology & Hepatology 21, 510 (2024)",
                    "Ethical and regulatory standards should be audited across clinical settings.",
                ],
            ),
        ]

        pack = build_knowledge_pack(extract_slide_evidence(slide) for slide in slides)

        self.assertEqual(pack.research_tasks[0].evidence_grade, EvidenceGrade.REFERENCE_PDF)
        self.assertEqual(pack.research_tasks[0].reason, "reference appears on 2 slides")


if __name__ == "__main__":
    unittest.main()
