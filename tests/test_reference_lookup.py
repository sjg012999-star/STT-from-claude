import unittest
import tempfile
from pathlib import Path

from stt_pipeline.knowledge_pack import SlideEvidence, build_knowledge_pack
from stt_pipeline.reference_lookup import (
    build_reference_lookup_plans,
    lookup_and_cache_references,
    reference_lookup_plans_to_dict,
    reference_lookup_results_to_dict,
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

    def test_lookup_downloads_open_pdf_from_crossref_metadata(self):
        class FakeHttpClient:
            def __init__(self):
                self.json_urls = []
                self.download_urls = []

            def get_json(self, url):
                self.json_urls.append(url)
                return {
                    "message": {
                        "title": ["Artificial intelligence in IBD clinical practice"],
                        "DOI": "10.1038/s41575-024-00913-8",
                        "link": [
                            {
                                "URL": "https://example.org/iacucci-2024.pdf",
                                "content-type": "application/pdf",
                            }
                        ],
                    }
                }

            def download(self, url):
                self.download_urls.append(url)
                return b"%PDF-1.7 fake paper"

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
        plans = build_reference_lookup_plans(pack)
        client = FakeHttpClient()

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "reference_cache"
            results = lookup_and_cache_references(
                plans,
                cache_dir=cache_dir,
                http_client=client,
            )
            payload = reference_lookup_results_to_dict(results)
            cached_bytes = results[0].cached_pdf_path.read_bytes()

        self.assertEqual(results[0].status, "downloaded")
        self.assertEqual(results[0].title, "Artificial intelligence in IBD clinical practice")
        self.assertEqual(results[0].pdf_url, "https://example.org/iacucci-2024.pdf")
        self.assertEqual(results[0].cached_pdf_path.name, "10-1038-s41575-024-00913-8.pdf")
        self.assertEqual(cached_bytes, b"%PDF-1.7 fake paper")
        self.assertIn("api.crossref.org/works", client.json_urls[0])
        self.assertEqual(client.download_urls, ["https://example.org/iacucci-2024.pdf"])
        self.assertEqual(payload["references"][0]["status"], "downloaded")

    def test_lookup_records_metadata_without_pdf_as_needs_pdf(self):
        class FakeHttpClient:
            def get_json(self, url):
                return {"message": {"title": ["No PDF paper"], "DOI": "10.1000/test"}}

            def download(self, url):
                raise AssertionError("download should not be called")

        pack = build_knowledge_pack(
            [
                SlideEvidence(
                    slide_id="slide-1",
                    title="No PDF",
                    references=["Author et al. Journal 2026 doi:10.1000/test"],
                )
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            results = lookup_and_cache_references(
                build_reference_lookup_plans(pack),
                cache_dir=Path(tmpdir) / "reference_cache",
                http_client=FakeHttpClient(),
            )

        self.assertEqual(results[0].status, "metadata_found")
        self.assertEqual(results[0].cached_pdf_path, None)

    def test_lookup_falls_back_to_openalex_when_crossref_has_no_pdf(self):
        class FakeHttpClient:
            def __init__(self):
                self.json_urls = []
                self.download_urls = []

            def get_json(self, url):
                self.json_urls.append(url)
                if "api.crossref.org" in url:
                    return {"message": {"title": ["Crossref title"], "DOI": "10.1000/test"}}
                return {
                    "results": [
                        {
                            "title": "OpenAlex title",
                            "doi": "https://doi.org/10.1000/test",
                            "primary_location": {
                                "pdf_url": "https://example.org/openalex.pdf",
                            },
                        }
                    ]
                }

            def download(self, url):
                self.download_urls.append(url)
                return b"%PDF-1.7 from openalex"

        pack = build_knowledge_pack(
            [
                SlideEvidence(
                    slide_id="slide-1",
                    title="Fallback",
                    references=["Author et al. Journal 2026 doi:10.1000/test"],
                )
            ]
        )
        client = FakeHttpClient()

        with tempfile.TemporaryDirectory() as tmpdir:
            results = lookup_and_cache_references(
                build_reference_lookup_plans(pack),
                cache_dir=Path(tmpdir) / "reference_cache",
                http_client=client,
            )
            cached_bytes = results[0].cached_pdf_path.read_bytes()

        self.assertEqual(results[0].status, "downloaded")
        self.assertEqual(results[0].title, "OpenAlex title")
        self.assertIn("api.crossref.org", client.json_urls[0])
        self.assertIn("api.openalex.org", client.json_urls[1])
        self.assertEqual(client.download_urls, ["https://example.org/openalex.pdf"])
        self.assertEqual(cached_bytes, b"%PDF-1.7 from openalex")

    def test_lookup_falls_back_to_openalex_when_crossref_errors(self):
        class FakeHttpClient:
            def __init__(self):
                self.json_urls = []

            def get_json(self, url):
                self.json_urls.append(url)
                if "api.crossref.org" in url:
                    raise RuntimeError("crossref unavailable")
                return {
                    "results": [
                        {
                            "title": "OpenAlex metadata",
                            "doi": "https://doi.org/10.1000/test",
                        }
                    ]
                }

            def download(self, url):
                raise AssertionError("download should not be called without a PDF URL")

        pack = build_knowledge_pack(
            [
                SlideEvidence(
                    slide_id="slide-1",
                    title="Fallback",
                    references=["Author et al. Journal 2026 doi:10.1000/test"],
                )
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            results = lookup_and_cache_references(
                build_reference_lookup_plans(pack),
                cache_dir=Path(tmpdir) / "reference_cache",
                http_client=FakeHttpClient(),
            )

        self.assertEqual(results[0].status, "metadata_found")
        self.assertEqual(results[0].title, "OpenAlex metadata")
        self.assertIsNone(results[0].error)


if __name__ == "__main__":
    unittest.main()
