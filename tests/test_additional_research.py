from pathlib import Path
import tempfile
import unittest

from stt_pipeline.additional_research import (
    additional_research_to_dict,
    load_additional_research_files,
)


class AdditionalResearchTest(unittest.TestCase):
    def test_loads_markdown_research_file_as_source_labeled_item(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "open-web-notes.md"
            path.write_text(
                "# InTesTiny nanoparticle context\n\n"
                "Source: https://example.org/paper\n\n"
                "- RGD targeting appears in the slide figure.\n"
                "- The reference needs PDF verification.\n",
                encoding="utf-8",
            )

            items = load_additional_research_files([path])
            payload = additional_research_to_dict(items)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "InTesTiny nanoparticle context")
        self.assertEqual(items[0].url, "https://example.org/paper")
        self.assertIn("RGD targeting", items[0].summary)
        self.assertEqual(items[0].source_label, "additional_research")
        self.assertEqual(payload["items"][0]["title"], "InTesTiny nanoparticle context")

    def test_loads_json_research_items(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "research.json"
            path.write_text(
                """
                {
                  "items": [
                    {
                      "title": "Open web result",
                      "summary": "External source says the figure is from a paper.",
                      "url": "https://example.org/result",
                      "evidence": "search-result-1"
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )

            items = load_additional_research_files([path])

        self.assertEqual(items[0].title, "Open web result")
        self.assertEqual(items[0].evidence, "search-result-1")
        self.assertEqual(items[0].url, "https://example.org/result")


if __name__ == "__main__":
    unittest.main()
