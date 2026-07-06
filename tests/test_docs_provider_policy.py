from pathlib import Path
import unittest


class DocsProviderPolicyTest(unittest.TestCase):
    def test_project_docs_do_not_wire_claude_api(self):
        docs = [
            Path("README.md"),
            Path("PLAN.md"),
            Path("CODEX_HANDOFF.md"),
            Path("AGENTS.md"),
        ]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in docs)

        forbidden = [
            "Claude API",
            "Claude 비전",
            "Claude 웹 검색",
            "claude-opus",
            "Claude 교정",
        ]
        for value in forbidden:
            self.assertNotIn(value, combined)

        self.assertIn("OpenAI", combined)


if __name__ == "__main__":
    unittest.main()
