import unittest

from stt_pipeline.knowledge_pack import SlideEvidence, build_knowledge_pack
from stt_pipeline.reference_lookup import (
    build_reference_lookup_plans,
    reference_lookup_plans_to_dict,
)


class ReferenceLookupTest(unittest.TestCase):
    def test_builds_reference_first_lookup_plan_with_doi_and_search_urls(self):
        pack = build_knowledge_pack(
            [
                SlideEvidence(
                    slide_id="slide-27",
                    title="The future of AI in IBD clinical practice",
                    references=[
                        "Iacucci et al., Nat Rev Gastroenterol Hepatol. 2024;21:510. doi:10.1038/s41575-024-00913-8"
                    ],
                ),
                SlideEvidence(
                    slide_id="slide-28",
                    title="Clinical implementation barriers",
                    references=[
                        "Iacucci et al., Nat Rev Gastroenterol Hepatol. 2024;21:510. doi:10.1038/s41575-024-00913-8"
                    ],
                ),
            ]
        )

        plans = build_reference_lookup_plans(pack)
        payload = reference_lookup_plans_to_dict(plans)

        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].source_slide_ids, ("slide-27", "slide-28"))
        self.assertEqual(plans[0].priority_score, 125)
        self.assertEqual(plans[0].doi, "10.1038/s41575-024-00913-8")
        self.assertEqual(plans[0].status, "planned")
        self.assertIn(
            "https://doi.org/10.1038/s41575-024-00913-8",
            plans[0].search_urls,
        )
        self.assertTrue(
            any("api.crossref.org/works" in url for url in plans[0].search_urls)
        )
        self.assertEqual(payload["references"][0]["doi"], "10.1038/s41575-024-00913-8")

    def test_reference_without_doi_keeps_bibliographic_query_and_review_status(self):
        pack = build_knowledge_pack(
            [
                SlideEvidence(
                    slide_id="slide-23",
                    title="Using InTesTinyTM for targeted nanoparticle design",
                    references=["Milojevic et al., ACS Nano 2025 targeted nanoparticle design"],
                )
            ]
        )

        plans = build_reference_lookup_plans(pack)

        self.assertEqual(plans[0].doi, None)
        self.assertEqual(plans[0].status, "needs_lookup")
        self.assertIn("Milojevic et al.", plans[0].bibliographic_query)
        self.assertTrue(
            any("query.bibliographic" in url for url in plans[0].search_urls)
        )


if __name__ == "__main__":
    unittest.main()
