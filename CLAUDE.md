# Claude Working Notes

This repository started in Claude on `claude/stt-conference-system-6bt09c`. Codex continued safely on `codex/phase1-mvp`.

When resuming:

1. Use `codex/phase1-mvp` as the active branch, or merge it before making new changes.
2. Read `CODEX_HANDOFF.md` and `PLAN.md` before editing.
3. Do not force-push or overwrite `claude/stt-conference-system-6bt09c`.
4. Keep Phase 1 narrow: scaffold the Python CLI package, then implement the STT bake-off path first.
5. Put cloud STT and LLM calls behind adapters so tests can run with fakes.
6. Preserve the safety rules in `PLAN.md`: correction diff validation, source-labeled enrichment, and transcript-body separation from AI research notes.

The repo currently has planning docs only; no working package has been implemented yet.
