from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum


class LlmTask(Enum):
    CORRECT_TRANSCRIPT = "correct_transcript"
    SUMMARIZE_TRANSCRIPT = "summarize_transcript"
    EXTRACT_SLIDE_TEXT = "extract_slide_text"
    ENRICH_NOTES = "enrich_notes"


@dataclass(frozen=True)
class OpenAiLlmConfig:
    text_model: str
    vision_model: str
    provider: str = "openai"


@dataclass(frozen=True)
class LlmRequestPlan:
    provider: str
    model: str
    task: LlmTask
    required_capabilities: tuple[str, ...]
    safety_rules: tuple[str, ...]
    postprocessing_steps: tuple[str, ...]


def build_openai_config_from_env(
    env: Mapping[str, str] | None = None,
) -> OpenAiLlmConfig:
    source = os.environ if env is None else env
    text_model = source.get("OPENAI_MODEL", "").strip()
    if not text_model:
        raise ValueError("OPENAI_MODEL is required for OpenAI LLM tasks")

    vision_model = (source.get("OPENAI_VISION_MODEL") or text_model).strip()
    return OpenAiLlmConfig(text_model=text_model, vision_model=vision_model)


def build_llm_request_plan(
    task: LlmTask,
    *,
    config: OpenAiLlmConfig,
) -> LlmRequestPlan:
    if task is LlmTask.EXTRACT_SLIDE_TEXT:
        model = config.vision_model
        capabilities = ("vision_input", "structured_json")
        safety_rules = ("mark_uncertain_ocr", "preserve_source_labels")
        postprocessing = ("ocr_confidence_review",)
    elif task is LlmTask.CORRECT_TRANSCRIPT:
        model = config.text_model
        capabilities = ("structured_json",)
        safety_rules = (
            "do_not_rewrite_unlisted_changes",
            "preserve_speaker_wording",
            "mark_low_confidence_corrections",
        )
        postprocessing = ("diff_validation",)
    elif task is LlmTask.SUMMARIZE_TRANSCRIPT:
        model = config.text_model
        capabilities = ("long_context", "structured_json")
        safety_rules = ("separate_summary_from_transcript", "preserve_source_labels")
        postprocessing = ("source_section_validation",)
    else:
        model = config.text_model
        capabilities = ("web_or_reference_context", "structured_json")
        safety_rules = ("cite_reference_grounding", "preserve_source_labels")
        postprocessing = ("citation_presence_check",)

    return LlmRequestPlan(
        provider=config.provider,
        model=model,
        task=task,
        required_capabilities=capabilities,
        safety_rules=safety_rules,
        postprocessing_steps=postprocessing,
    )
