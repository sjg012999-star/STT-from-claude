# Codex Handoff - 2026-07-06

## Branch State

- Original Claude branch: `claude/stt-conference-system-6bt09c`
- Codex continuation branch: `codex/phase1-mvp`
- Current safe base: continue from `codex/phase1-mvp`

Do not force-push or overwrite the original Claude branch. If Claude resumes work later, start from `codex/phase1-mvp` or merge this branch first.

## What Codex Changed

- Created `codex/phase1-mvp` from `claude/stt-conference-system-6bt09c`.
- Removed a broken trailing fragment from the end of `PLAN.md`.
- Added this handoff file plus agent notes so future Claude/Codex sessions can recover context quickly.
- Added a tested Phase 1 Knowledge Pack scaffold in `src/stt_pipeline/knowledge_pack.py`.
- Updated README and PLAN to reflect reference-first, deck-level slide analysis and transcript/slide mutual support.

No real OCR, STT, web search, OpenAI API, or PDF parsing calls are wired yet. The current code is a deterministic planning layer that can be tested without network or paid APIs.

## Current Repo Contents

- `README.md`: high-level project summary and phase checklist.
- `PLAN.md`: architecture, roadmap, risks, and target file layout.
- `CODEX_HANDOFF.md`: branch handoff and continuation instructions.
- `CLAUDE.md`: Claude-specific working notes.
- `AGENTS.md`: general agent working notes.
- `pyproject.toml`: Python package/test metadata.
- `src/stt_pipeline/knowledge_pack.py`: reference-first Knowledge Pack planner.
- `src/stt_pipeline/llm_provider.py`: OpenAI-first LLM request planning.
- `src/stt_pipeline/slide_extract.py`: OCR-text-to-slide-evidence heuristics.
- `src/stt_pipeline/pdf_tools.py`: command builder for the existing PDF figure/table extraction script.
- `tests/test_knowledge_pack.py`: tests for prioritization, PDF extraction jobs, and transcript-slide alignment.
- `tests/test_slide_extract.py`: tests for OCR text classification into slide evidence.
- `tests/test_pdf_tools.py`: tests for PDF extraction command planning.
- `docs/tooling.md`: GitHub/tooling candidates and integration rules.

## Next Implementation Order

1. Add Python project scaffold: `pyproject.toml`, `src/stt_pipeline/`, `tests/`.
2. Implement config/profile loading before external API calls.
3. Add real PPT/photo OCR adapters that produce `SlideOcrInput` fixtures.
4. Connect reference PDF acquisition to the existing figure/table extraction toolchain.
5. Add skipped integration tests for any optional external tool before wiring it into the CLI.
6. Implement deterministic preprocessing command construction and test it without running real audio.
7. Implement STT provider interfaces with fake providers first.
8. Add the Phase 1 bake-off CLI around provider adapters.
9. Add report output stubs for `transcript.md`, `transcript.json`, and `transcript.srt`.

Keep real cloud STT and OpenAI API calls behind adapters. Tests should use fakes and local fixtures, not paid network calls.
OpenAI text model names must come from `OPENAI_MODEL`; use `OPENAI_VISION_MODEL` only when a distinct vision model is needed. Do not hardcode another provider model into the pipeline.

## Conflict Guidance

- If `PLAN.md` conflicts, keep the fixed ending with the risk table as the final section.
- If implementation begins in another branch, prefer merging that branch into `codex/phase1-mvp` before adding more code.
- Keep Knowledge Pack enrichment separate from the transcript body. The project design requires source labels for generated notes and diff validation for transcript corrections.
