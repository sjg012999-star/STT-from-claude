import tempfile
import unittest
import zipfile
from pathlib import Path

from stt_pipeline.materials import load_material_pack


class MaterialsTest(unittest.TestCase):
    def test_loads_text_materials_as_prompt_terms(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            materials_dir = root / "materials"
            materials_dir.mkdir()
            (materials_dir / "slide-notes.md").write_text(
                "\n".join(
                    [
                        "The future of AI in IBD clinical practice",
                        "Road map to implementation requires cost-effectiveness, audit, data standardization, robust study design, reproducibility, and ethical and regulatory standards.",
                        "Iacucci et al., Nature Reviews Gastroenterology & Hepatology 21, 510 (2024)",
                    ]
                ),
                encoding="utf-8",
            )

            pack = load_material_pack([materials_dir])

        self.assertEqual(pack.source_count, 1)
        self.assertEqual(pack.slide_count, 1)
        self.assertIn("IBD", pack.prompt_terms)
        self.assertIn(
            "Iacucci et al., Nature Reviews Gastroenterology & Hepatology 21, 510 (2024)",
            pack.prompt_terms,
        )
        self.assertEqual(pack.warnings, ())

    def test_loads_pptx_text_without_extra_dependencies(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            deck_path = Path(tmpdir) / "deck.pptx"
            slide_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:sp><p:txBody><a:p><a:r><a:t>Using InTesTinyTM for targeted nanoparticle design</a:t></a:r></a:p></p:txBody></p:sp>
      <p:sp><p:txBody><a:p><a:r><a:t>NHS-PEG5k-cRGD cyclo(Arg-Gly-Asp-D-Tyr-Lys) was compared across healthy and IBD intestinal media.</a:t></a:r></a:p></p:txBody></p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>
"""
            with zipfile.ZipFile(deck_path, "w") as archive:
                archive.writestr("ppt/slides/slide1.xml", slide_xml)

            pack = load_material_pack([deck_path])

        self.assertEqual(pack.source_count, 1)
        self.assertEqual(pack.slide_count, 1)
        self.assertIn("InTesTinyTM", pack.prompt_terms)
        self.assertIn("NHS-PEG5k-cRGD", pack.prompt_terms)
        self.assertEqual(pack.warnings, ())


if __name__ == "__main__":
    unittest.main()
