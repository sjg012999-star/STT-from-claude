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

No real OCR, STT, web search, Claude API, or PDF parsing calls are wired yet. The current code is a deterministic planning layer that can be tested without network or paid APIs.

## Current Repo Contents

- `README.md`: high-level project summary and phase checklist.
- `PLAN.md`: architecture, roadmap, risks, and target file layout.
- `CODEX_HANDOFF.md`: branch handoff and continuation instructions.
- `CLAUDE.md`: Claude-specific working notes.
- `AGENTS.md`: general agent working notes.
- `pyproject.toml`: Python package/test metadata.
- `src/stt_pipeline/knowledge_pack.py`: reference-first Knowledge Pack planner.
- `tests/test_knowledge_pack.py`: tests for prioritization, PDF extraction jobs, and transcript-slide alignment.

## Next Implementation Order

1. Add Python project scaffold: `pyproject.toml`, `src/stt_pipeline/`, `tests/`.
2. Implement config/profile loading before external API calls.
3. Add slide extraction adapters that can accept OCR text now and later real PPT/photo OCR.
4. Connect reference PDF acquisition to the existing figure/table extraction toolchain.
5. Implement deterministic preprocessing command construction and test it without running real audio.
6. Implement STT provider interfaces with fake providers first.
7. Add the Phase 1 bake-off CLI around provider adapters.
8. Add report output stubs for `transcript.md`, `transcript.json`, and `transcript.srt`.

Keep real cloud STT and Claude API calls behind adapters. Tests should use fakes and local fixtures, not paid network calls.

## Conflict Guidance

- If `PLAN.md` conflicts, keep the fixed ending with the risk table as the final section.
- If implementation begins in another branch, prefer merging that branch into `codex/phase1-mvp` before adding more code.
- Keep Knowledge Pack enrichment separate from the transcript body. The project design requires source labels for generated notes and diff validation for transcript corrections.
