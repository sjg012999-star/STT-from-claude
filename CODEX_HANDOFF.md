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
- Added OpenAI STT adapter and CLI outputs for `transcript.md` / `transcript.json`.
- Added material-pack prompt term extraction for text, Markdown, PPTX, and slide OCR JSON.
- Updated README and PLAN to reflect reference-first, deck-level slide analysis and transcript/slide mutual support.

Live OpenAI STT is wired behind `OpenAiSttTranscriber`, but tests still use fakes and do not call paid or network APIs. Raw slide-image OCR, live web search, LLM correction, summary generation, and PDF parsing execution are not wired yet.

## Current Repo Contents

- `README.md`: high-level project summary and phase checklist.
- `PLAN.md`: architecture, roadmap, risks, and target file layout.
- `CODEX_HANDOFF.md`: branch handoff and continuation instructions.
- `CLAUDE.md`: Claude-specific working notes.
- `AGENTS.md`: general agent working notes.
- `pyproject.toml`: Python package/test metadata.
- `src/stt_pipeline/knowledge_pack.py`: reference-first Knowledge Pack planner.
- `src/stt_pipeline/llm_provider.py`: OpenAI-first LLM request planning.
- `src/stt_pipeline/stt_provider.py`: OpenAI STT request planning, live adapter, and normalized transcript output.
- `src/stt_pipeline/transcript.py`: shared transcript result dataclasses.
- `src/stt_pipeline/materials.py`: material-pack loader for text, Markdown, PPTX, and slide OCR JSON prompt terms.
- `src/stt_pipeline/cli.py`: `run`, `transcribe`, and `bakeoff` command handlers.
- `src/stt_pipeline/slide_extract.py`: OCR-text-to-slide-evidence heuristics.
- `src/stt_pipeline/pdf_tools.py`: command builder for the existing PDF figure/table extraction script.
- `tests/test_knowledge_pack.py`: tests for prioritization, PDF extraction jobs, and transcript-slide alignment.
- `tests/test_slide_extract.py`: tests for OCR text classification into slide evidence.
- `tests/test_pdf_tools.py`: tests for PDF extraction command planning.
- `docs/tooling.md`: GitHub/tooling candidates and integration rules.

## Next Implementation Order

1. Implement deterministic preprocessing command construction and test it without running real audio.
2. Add report output stubs for `transcript.srt` if timestamp/SRT output becomes necessary.
3. Wire LLM correction to normalized transcript output with diff validation.
4. Add basic profile summaries after corrected transcript output exists.
5. Add optional image/PDF material extraction adapters only after fixture-based tests and clear warnings are in place.
6. Connect reference PDF acquisition to the existing figure/table extraction toolchain.
7. Add skipped integration tests for any optional external tool before wiring it into the CLI.

Keep real cloud STT and OpenAI API calls behind adapters. Tests should use fakes and local fixtures, not paid network calls.
OpenAI text model names must come from `OPENAI_MODEL`; use `OPENAI_VISION_MODEL` only when a distinct vision model is needed. Do not hardcode another provider model into the pipeline.
The STT adapter already supports `gpt-4o`, `gpt-4o-mini`, `whisper-1`, and `diarize` provider aliases. Knowledge Pack remains optional; Phase 1 uses compact STT prompt hints, not heavy enrichment.
`stt run ... --pack ./materials` now merges `--terms-file` with prompt terms extracted from `.txt`, `.md`, `.pptx`, and slide OCR `.json`. Raw slide images and PDFs are intentionally not auto-OCRed yet; the material pack records warnings so Claude/Codex does not mistake skipped files for parsed evidence.

## Conflict Guidance

- If `PLAN.md` conflicts, keep the fixed ending with the risk table as the final section.
- If implementation begins in another branch, prefer merging that branch into `codex/phase1-mvp` before adding more code.
- Keep Knowledge Pack enrichment separate from the transcript body. The project design requires source labels for generated notes and diff validation for transcript corrections.
