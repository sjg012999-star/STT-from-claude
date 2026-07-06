import unittest

from stt_pipeline.knowledge_pack import (
    EvidenceGrade,
    SlideEvidence,
    TranscriptSegment,
    build_knowledge_pack,
)


class KnowledgePackTest(unittest.TestCase):
    def test_reference_repeated_across_slides_is_top_research_task(self):
        deck = [
            SlideEvidence(
                slide_id="slide-27",
                title="The future of AI in IBD clinical practice",
                references=[
                    "Iacucci et al., Nature Reviews Gastroenterology & Hepatology 21, 510 (2024)"
                ],
                full_sentences=[
                    "Road map to implementation requires cost-effectiveness, audit, data standardization, robust study design, reproducibility, and ethical and regulatory standards."
                ],
                named_entities=["IBD", "large language models"],
                isolated_keywords=["audit", "industry", "environment"],
            ),
            SlideEvidence(
                slide_id="slide-28",
                title="Clinical implementation barriers",
                references=[
                    "Iacucci et al., Nature Reviews Gastroenterology & Hepatology 21, 510 (2024)"
                ],
                full_sentences=[
                    "Expectations and concerns differ between physicians, patients, regulatory bodies, industry, and environment."
                ],
                named_entities=["physicians", "patients"],
                isolated_keywords=["reproducibility"],
            ),
        ]

        pack = build_knowledge_pack(deck)

        top_task = pack.research_tasks[0]
        self.assertEqual(
            top_task.query,
            "Iacucci et al., Nature Reviews Gastroenterology & Hepatology 21, 510 (2024)",
        )
        self.assertIs(top_task.evidence_grade, EvidenceGrade.REFERENCE_PDF)
        self.assertEqual(top_task.reason, "reference appears on 2 slides")
        self.assertEqual(top_task.source_slide_ids, ("slide-27", "slide-28"))

    def test_full_sentence_outweighs_isolated_keyword_for_research_tasks(self):
        deck = [
            SlideEvidence(
                slide_id="slide-23",
                title="Using InTesTinyTM for targeted nanoparticle design",
                full_sentences=[
                    "NHS-PEG5k-cRGD cyclo(Arg-Gly-Asp-D-Tyr-Lys) was compared across healthy and IBD intestinal media."
                ],
                named_entities=["InTesTiny", "SPION", "NHS-PEG5k-cRGD"],
                isolated_keywords=["healthy", "IBD", "control"],
            )
        ]

        pack = build_knowledge_pack(deck)

        queries = [task.query for task in pack.research_tasks]
        self.assertLess(
            queries.index(
                "NHS-PEG5k-cRGD cyclo(Arg-Gly-Asp-D-Tyr-Lys) was compared across healthy and IBD intestinal media."
            ),
            queries.index("InTesTiny"),
        )
        self.assertLess(queries.index("InTesTiny"), queries.index("healthy"))

    def test_transcript_terms_raise_slide_alignment_without_rewriting_slide_facts(self):
        deck = [
            SlideEvidence(
                slide_id="slide-23",
                title="Using InTesTinyTM for targeted nanoparticle design",
                full_sentences=[
                    "NHS-PEG5k-cRGD cyclo(Arg-Gly-Asp-D-Tyr-Lys) was compared across healthy and IBD intestinal media."
                ],
                named_entities=["InTesTiny", "SPION", "cRGD", "hydrodynamic diameter"],
            ),
            SlideEvidence(
                slide_id="slide-27",
                title="The future of AI in IBD clinical practice",
                full_sentences=[
                    "Road map to implementation requires cost-effectiveness, audit, data standardization, robust study design, reproducibility, and ethical and regulatory standards."
                ],
                named_entities=["large language models", "IBD"],
            ),
        ]
        transcript = [
            TranscriptSegment(
                segment_id="seg-001",
                text="The key point here is that cRGD stabilizes the SPION hydrodynamic diameter in IBD-like intestinal media.",
            )
        ]

        pack = build_knowledge_pack(deck, transcript)

        match = pack.slide_transcript_links[0]
        self.assertEqual(match.slide_id, "slide-23")
        self.assertEqual(match.segment_id, "seg-001")
        self.assertGreaterEqual(
            set(match.matched_terms), {"cRGD", "SPION", "hydrodynamic diameter"}
        )
        self.assertEqual(
            pack.enrichment_sections,
            (
                "speaker_transcript",
                "slide_text",
                "reference_pdf",
                "additional_research",
                "needs_review",
            ),
        )

    def test_references_create_pdf_figure_table_extraction_jobs(self):
        deck = [
            SlideEvidence(
                slide_id="slide-27",
                title="The future of AI in IBD clinical practice",
                references=[
                    "Iacucci et al., Nature Reviews Gastroenterology & Hepatology 21, 510 (2024)"
                ],
                full_sentences=[
                    "Road map to implementation requires cost-effectiveness, audit, data standardization, robust study design, reproducibility, and ethical and regulatory standards."
                ],
            )
        ]

        pack = build_knowledge_pack(deck)

        self.assertEqual(len(pack.pdf_extraction_jobs), 1)
        job = pack.pdf_extraction_jobs[0]
        self.assertEqual(
            job.reference,
            "Iacucci et al., Nature Reviews Gastroenterology & Hepatology 21, 510 (2024)",
        )
        self.assertEqual(job.source_slide_ids, ("slide-27",))
        self.assertEqual(job.tools, ("pymupdf", "pdfplumber", "camelot-py"))
        self.assertEqual(
            job.goal,
            "extract figure/table captions, crops, and table cells from the source PDF",
        )


if __name__ == "__main__":
    unittest.main()
