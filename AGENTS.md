# Agent Notes

Read `CODEX_HANDOFF.md` before making changes.

Active continuation branch: `codex/phase1-mvp`.

Project intent:

- Build a conference, lecture, and meeting STT pipeline for Zoom H1e recordings.
- Prefer cloud STT for quality and speed, with local `mlx-whisper` only as fallback.
- Keep one pipeline with profile-specific settings rather than separate STT models per use case.
- Treat transcript correction and AI enrichment as separate layers with explicit provenance.
- Use OpenAI-first LLM/vision providers for new implementation work unless the user explicitly requests another provider.

Development guidance:

- Keep implementation focused on Phase 1 until the CLI can produce transcript outputs from a seminar recording path.
- Preserve the Knowledge Pack evidence order: reference PDF, slide sentence, figure/table context, named entity, isolated keyword.
- Treat the deck as one integrated source; repeated references across slides increase priority.
- Use transcript text to interpret slides and slide terms to improve STT, but keep source sections separate.
- Read `docs/tooling.md` before adding OCR/PDF dependencies.
- Do not call paid or network APIs in tests; use fakes and fixtures.
- Add small, testable modules rather than a single large script.
- Avoid committing real recordings, API keys, generated transcripts from private sessions, or conference materials.
