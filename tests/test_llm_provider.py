import unittest

from stt_pipeline.llm_provider import (
    LlmTask,
    OpenAiLlmConfig,
    build_openai_config_from_env,
    build_llm_request_plan,
)


class LlmProviderTest(unittest.TestCase):
    def test_openai_is_default_provider_for_correction_summary_and_vision(self):
        config = OpenAiLlmConfig(text_model="gpt-configured-text", vision_model="gpt-configured-vision")

        correction = build_llm_request_plan(LlmTask.CORRECT_TRANSCRIPT, config=config)
        summary = build_llm_request_plan(LlmTask.SUMMARIZE_TRANSCRIPT, config=config)
        vision = build_llm_request_plan(LlmTask.EXTRACT_SLIDE_TEXT, config=config)

        self.assertEqual(correction.provider, "openai")
        self.assertEqual(summary.provider, "openai")
        self.assertEqual(vision.provider, "openai")
        self.assertEqual(correction.model, "gpt-configured-text")
        self.assertEqual(summary.model, "gpt-configured-text")
        self.assertEqual(vision.model, "gpt-configured-vision")

    def test_structured_tasks_keep_source_boundaries(self):
        plan = build_llm_request_plan(
            LlmTask.CORRECT_TRANSCRIPT,
            config=OpenAiLlmConfig(text_model="gpt-text", vision_model="gpt-vision"),
        )

        self.assertIn("structured_json", plan.required_capabilities)
        self.assertIn("diff_validation", plan.postprocessing_steps)
        self.assertIn("do_not_rewrite_unlisted_changes", plan.safety_rules)

    def test_openai_model_names_are_loaded_from_environment(self):
        config = build_openai_config_from_env(
            {
                "OPENAI_MODEL": "gpt-selected-text",
                "OPENAI_VISION_MODEL": "gpt-selected-vision",
            }
        )

        self.assertEqual(config.provider, "openai")
        self.assertEqual(config.text_model, "gpt-selected-text")
        self.assertEqual(config.vision_model, "gpt-selected-vision")

    def test_openai_text_model_is_required(self):
        with self.assertRaisesRegex(ValueError, "OPENAI_MODEL"):
            build_openai_config_from_env({})


if __name__ == "__main__":
    unittest.main()
