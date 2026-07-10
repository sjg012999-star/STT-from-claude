# Agent Notes

Read `CODEX_HANDOFF.md` before making changes.

Active continuation branch: `codex/phase1-mvp`.

Project intent:

- Build a conference, lecture, and meeting STT pipeline for Zoom H1e recordings.
- Use cloud STT for quality and speed; do not add local model dependencies by default.
- Use the Platform API key for `gpt-4o-transcribe` STT only by default.
- Perform transcript correction, summarization, slide interpretation, and evidence synthesis in the active Codex ChatGPT-sign-in/OAuth session. Do not call paid Responses API post-processing unless the user explicitly opts in.
- ChatGPT-sign-in work consumes plan usage or credits rather than Platform API spend; prefer the current long-running Codex task over many cold `codex exec` invocations.
- Keep one pipeline with profile-specific settings rather than separate STT models per use case.
- Treat transcript correction and AI enrichment as separate layers with explicit provenance.
- Use OpenAI-first LLM/vision providers for new implementation work unless the user explicitly requests another provider.
- Preserve transcript versions: `V0_raw` is immutable, `V1_context_only` is the legacy July 7 comparison, `V1_conference_aware` is the current all-date baseline, and `V2_material_grounded` is reserved for slide/PDF evidence.

Development guidance:

- Keep implementation focused on Phase 1 until the CLI can produce transcript outputs from a seminar recording path.
- Preserve the Knowledge Pack evidence order: reference PDF, slide sentence, figure/table context, named entity, isolated keyword.
- Treat the deck as one integrated source; repeated references across slides increase priority.
- Use transcript text to interpret slides and slide terms to improve STT, but keep source sections separate.
- Read `docs/tooling.md` before adding OCR/PDF dependencies.
- Do not call paid or network APIs in tests; use fakes and fixtures.
- Add small, testable modules rather than a single large script.
- For CRS context correction, use `conference-jobs` and `conference-apply`; the apply step must accept only Codex ChatGPT OAuth provenance and exact source substrings.
- Avoid committing real recordings, API keys, generated transcripts from private sessions, or conference materials.
