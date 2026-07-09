from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

from stt_pipeline.credentials import build_openai_client
from stt_pipeline.llm_provider import build_openai_config_from_env
from stt_pipeline.slide_extract import SlideOcrInput


IMAGE_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".heic": "image/heic",
}


class OpenAiSlideImageOcr:
    def __init__(self, client: Any | None = None, model: str | None = None):
        self._client = client
        self._model = model

    def extract(self, image_path: str | Path) -> SlideOcrInput:
        path = Path(image_path)
        client = self._client or _build_default_openai_client()
        model = self._model or build_openai_config_from_env().vision_model
        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Extract visible slide text from this conference slide photo. "
                                "Preserve references, long sentences, axis labels, legends, "
                                "chemical names, acronyms, and named entities. Return JSON only."
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": _image_data_url(path),
                        },
                    ],
                }
            ],
            text={"format": _slide_ocr_json_schema()},
        )
        payload = json.loads(_response_output_text(response))
        text_lines = tuple(_clean_line(value) for value in payload.get("text_lines", []))
        text_lines = tuple(value for value in text_lines if value)
        title = _clean_line(payload.get("title", "")) or (text_lines[0] if text_lines else path.stem)
        return SlideOcrInput(
            slide_id=_slide_id(path),
            title=title,
            text_lines=list(text_lines),
            source_path=str(path),
        )


def _image_data_url(path: Path) -> str:
    mime_type = IMAGE_MIME_TYPES.get(path.suffix.casefold(), "application/octet-stream")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"{mime_type};base64,{encoded}".join(("data:", ""))


def _slide_ocr_json_schema() -> dict[str, object]:
    return {
        "type": "json_schema",
        "name": "slide_ocr",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "text_lines": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "text_lines"],
            "additionalProperties": False,
        },
    }


def _response_output_text(response: Any) -> str:
    if isinstance(response, dict):
        if "output_text" in response:
            return str(response["output_text"])
        output = response.get("output") or []
    else:
        output_text = getattr(response, "output_text", None)
        if output_text is not None:
            return str(output_text)
        output = getattr(response, "output", None) or []

    for item in output:
        content = _get_value(item, "content", []) or []
        for part in content:
            if _get_value(part, "type", "") == "output_text":
                return str(_get_value(part, "text", ""))
    raise ValueError("OpenAI image OCR response did not include output_text")


def _get_value(source: Any, key: str, default: Any) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _slide_id(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", path.stem).strip("-") or "slide"


def _clean_line(value: object) -> str:
    return " ".join(str(value).split())


def _build_default_openai_client() -> Any:
    return build_openai_client("OpenAI slide image OCR")
