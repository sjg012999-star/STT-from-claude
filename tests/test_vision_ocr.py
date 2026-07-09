import json
import tempfile
import unittest
from pathlib import Path

from stt_pipeline.vision_ocr import OpenAiSlideImageOcr


class FakeResponses:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return {"output_text": json.dumps(self.payload)}


class FakeClient:
    def __init__(self, payload):
        self.responses = FakeResponses(payload)


class VisionOcrTest(unittest.TestCase):
    def test_openai_image_ocr_returns_slide_input_from_base64_image(self):
        client = FakeClient(
            {
                "title": "The future of AI in IBD clinical practice",
                "text_lines": [
                    "The future of AI in IBD clinical practice",
                    "Iacucci et al., Nature Reviews Gastroenterology & Hepatology 21, 510 (2024)",
                ],
            }
        )
        extractor = OpenAiSlideImageOcr(client=client, model="gpt-vision")
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "slide-27.jpg"
            image_path.write_bytes(b"\xff\xd8fake jpeg")

            slide = extractor.extract(image_path)

        self.assertEqual(slide.slide_id, "slide-27")
        self.assertEqual(slide.title, "The future of AI in IBD clinical practice")
        self.assertIn("Iacucci et al.", slide.text_lines[1])
        call = client.responses.calls[0]
        self.assertEqual(call["model"], "gpt-vision")
        self.assertEqual(call["input"][0]["content"][1]["type"], "input_image")
        self.assertIn("data:image/jpeg;base64,", call["input"][0]["content"][1]["image_url"])
        self.assertEqual(call["text"]["format"]["type"], "json_schema")


if __name__ == "__main__":
    unittest.main()
