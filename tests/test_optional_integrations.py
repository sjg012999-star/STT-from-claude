from pathlib import Path
import os
import shutil
import tempfile
import unittest

from stt_pipeline.knowledge_pack import SlideEvidence, build_knowledge_pack
from stt_pipeline.local_whisper import MlxWhisperConfig, build_mlx_whisper_command
from stt_pipeline.reference_lookup import (
    ReferenceLookupHttpClient,
    build_reference_lookup_plans,
    lookup_and_cache_references,
)


class OptionalIntegrationsTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("mlx_whisper"), "mlx_whisper CLI is not installed")
    def test_mlx_whisper_command_can_be_built_for_installed_cli(self):
        command = build_mlx_whisper_command(
            Path("sample.wav"),
            Path("out/mlx"),
            config=MlxWhisperConfig(command="mlx_whisper", model="mlx-community/whisper-large-v3-turbo"),
        )

        self.assertEqual(command[0], "mlx_whisper")

    @unittest.skipUnless(
        os.environ.get("STT_RUN_LIVE_REFERENCE_TESTS") == "1",
        "set STT_RUN_LIVE_REFERENCE_TESTS=1 to run live Crossref lookup",
    )
    def test_live_crossref_lookup_can_resolve_reference_metadata(self):
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


if __name__ == "__main__":
    unittest.main()
