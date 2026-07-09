import unittest

from stt_pipeline.web_research import (
    WebResearchConfig,
    build_web_research_url,
    search_web_research,
    web_research_to_dict,
)


class FakeWebResearchClient:
    def __init__(self):
        self.urls = []

    def get_json(self, url):
        self.urls.append(url)
        return {
            "items": [
                {
                    "title": "InTesTiny nanoparticle paper",
                    "url": "https://example.org/intestiny",
                    "snippet": "RGD targeting appears in the nanoparticle design.",
                }
            ]
        }


class WebResearchTest(unittest.TestCase):
    def test_builds_search_url_without_assuming_provider(self):
        url = build_web_research_url(
            "https://search.example.test/api",
            query="InTesTiny RGD nanoparticle",
            limit=3,
        )

        self.assertEqual(
            url,
            "https://search.example.test/api?q=InTesTiny%20RGD%20nanoparticle&limit=3",
        )

    def test_search_normalizes_generic_json_results_to_additional_research(self):
        client = FakeWebResearchClient()

        items = search_web_research(
            "InTesTiny RGD nanoparticle",
            config=WebResearchConfig(endpoint="https://search.example.test/api", limit=3),
            http_client=client,
        )
        payload = web_research_to_dict(items)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "InTesTiny nanoparticle paper")
        self.assertEqual(items[0].url, "https://example.org/intestiny")
        self.assertIn("RGD targeting", items[0].summary)
        self.assertEqual(items[0].source_path, "web:InTesTiny RGD nanoparticle")
        self.assertIn("limit=3", client.urls[0])
        self.assertEqual(payload["items"][0]["source_label"], "additional_research")


if __name__ == "__main__":
    unittest.main()
