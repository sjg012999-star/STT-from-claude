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
- Added optional ffmpeg preprocessing, SRT output, OpenAI structured correction, and basic Markdown summary output.
- Added optional OpenAI vision OCR for slide photos via `--ocr-images`.
- Added deterministic reference lookup planning via `--plan-reference-search`.
- Added explicit PDF figure/table extraction command execution via `--extract-pdfs`.
- Added chunked transcript correction options for long recordings.
- Expanded deterministic profile summaries for seminar, lecture, and meeting outputs.
- Added source-separated enriched notes output via `--enrich-notes`.
- Added OpenAI LLM source-labeled rich summary output via `--llm-summarize`.
- Updated README and PLAN to reflect reference-first, deck-level slide analysis and transcript/slide mutual support.

Live OpenAI STT is wired behind `OpenAiSttTranscriber`, optional OpenAI transcript correction is wired behind `OpenAiTranscriptCorrector`, optional slide-photo OCR is wired behind `OpenAiSlideImageOcr`, reference lookup planning is deterministic behind `--plan-reference-search`, optional PDF figure/table extraction execution is wired behind explicit CLI flags, deterministic source-separated notes are wired behind `--enrich-notes`, and OpenAI source-labeled rich summaries are wired behind `--llm-summarize`. Tests still use fakes and do not call paid or network APIs. Live web search/download is not wired yet.

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
- `src/stt_pipeline/preprocess.py`: deterministic ffmpeg preprocess command builder and runner.
- `src/stt_pipeline/report.py`: SRT rendering from timestamped transcript segments.
- `src/stt_pipeline/correct.py`: OpenAI structured correction adapter plus exact-change validation.
- `src/stt_pipeline/summarize.py`: basic source-separated Markdown summary generation.
- `src/stt_pipeline/rich_summary.py`: OpenAI structured rich summary adapter with source-label validation.
- `src/stt_pipeline/notes.py`: deterministic source-separated enriched notes generation.
- `src/stt_pipeline/vision_ocr.py`: OpenAI vision slide-photo OCR adapter using Responses API image inputs.
- `src/stt_pipeline/cli.py`: `run`, `transcribe`, and `bakeoff` command handlers.
- `src/stt_pipeline/slide_extract.py`: OCR-text-to-slide-evidence heuristics.
- `src/stt_pipeline/reference_lookup.py`: deterministic DOI/Crossref/OpenAlex lookup planning.
- `src/stt_pipeline/pdf_tools.py`: command builder for the existing PDF figure/table extraction script.
- `tests/test_knowledge_pack.py`: tests for prioritization, PDF extraction jobs, and transcript-slide alignment.
- `tests/test_slide_extract.py`: tests for OCR text classification into slide evidence.
- `tests/test_reference_lookup.py`: tests for DOI extraction and reference lookup planning.
- `tests/test_pdf_tools.py`: tests for PDF extraction command planning.
- `tests/test_rich_summary.py`: tests for structured rich summary rendering and source-label rejection.
- `docs/tooling.md`: GitHub/tooling candidates and integration rules.

## Next Implementation Order

1. Add live reference PDF lookup/download behind the existing `reference_lookup.py` adapter boundary.
2. Add live reference PDF download/cache after deterministic lookup planning.
3. Add skipped integration tests for any optional external tool before wiring it into the CLI.
4. Add local `mlx-whisper` fallback only after adapter tests exist.

Keep real cloud STT and OpenAI API calls behind adapters. Tests should use fakes and local fixtures, not paid network calls.
OpenAI text model names must come from `OPENAI_MODEL`; use `OPENAI_VISION_MODEL` only when a distinct vision model is needed. Do not hardcode another provider model into the pipeline.
The STT adapter already supports `gpt-4o`, `gpt-4o-mini`, `whisper-1`, and `diarize` provider aliases. Knowledge Pack remains optional; Phase 1 uses compact STT prompt hints, not heavy enrichment.
`stt run ... --pack ./materials` now merges `--terms-file` with prompt terms extracted from `.txt`, `.md`, `.pptx`, slide OCR `.json`, and slide photos when `--ocr-images` is passed. PDFs are not mixed into prompt terms; they are tracked as `pdf_sources` and can be processed with `--extract-pdfs --pdf-extractor-script ...`.
Use `--plan-reference-search` to write `reference_lookup_jobs.json` with DOI, Crossref, OpenAlex, and DOI URL candidates. This does not perform network lookup or download yet.
Use `--preprocess` to run ffmpeg before STT. Use `--correct` only when `OPENAI_MODEL` is set; it asks for structured correction JSON and applies only exact declared replacements. Use `--summarize` for the basic Markdown summary.
Use `--correction-chunk-size` and `--correction-overlap` for long recordings; chunk provenance is written to `corrections.json` and `run_manifest.json`.
`--summarize` currently uses deterministic profile templates, not an LLM summarizer.
`--llm-summarize` uses `OPENAI_MODEL` through `OpenAiRichSummarizer` and writes `rich_summary.md`. It requires every generated item to carry one of the allowed source labels: `speaker_transcript`, `slide_text`, `reference_pdf`, or `additional_research`.
`--enrich-notes` writes `notes.md` with explicit source sections: speaker transcript, slide text, reference PDF, additional research, and needs review. If `--plan-reference-search` is also used, the additional research section includes the lookup URLs as planned evidence, not confirmed findings.
Use `--ocr-images` only when `OPENAI_MODEL`/`OPENAI_VISION_MODEL` are configured and slide-photo OCR cost is acceptable.
Use `--extract-pdfs` only with an explicit extractor script path. The command runner executes the existing figure/table workflow and writes `pdf_extraction_jobs.json`; tests use fake runners.

## Conflict Guidance

- If `PLAN.md` conflicts, keep the fixed ending with the risk table as the final section.
- If implementation begins in another branch, prefer merging that branch into `codex/phase1-mvp` before adding more code.
- Keep Knowledge Pack enrichment separate from the transcript body. The project design requires source labels for generated notes and diff validation for transcript corrections.
