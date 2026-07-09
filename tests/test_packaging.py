from pathlib import Path
import tomllib
import unittest


class PackagingTest(unittest.TestCase):
    def test_cli_entrypoint_and_openai_dependency_are_declared(self):
        pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

        self.assertIn("openai>=1.0", pyproject["project"]["dependencies"])
        self.assertIn(
            "google-genai>=1.0",
            pyproject["project"]["optional-dependencies"]["gemini"],
        )
        self.assertEqual(
            pyproject["project"]["scripts"]["stt"],
            "stt_pipeline.cli:main",
        )


if __name__ == "__main__":
    unittest.main()
