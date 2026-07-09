# Codex Handoff - 2026-07-06

## Latest Checkpoint - 2026-07-10

- Static review UI implementation, CLI wiring, tests, and documentation are included on `codex/phase1-mvp`.
- Browser QA confirmed desktop interactions, mobile layout without horizontal overflow, and decision JSON generation after status changes.
- The QA pass found and fixed both an escaped-newline JavaScript bug and a fragile programmatic download path; regression assertions cover the generated script and native download link.

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
- Added optional local `mlx-whisper` fallback adapter and provider routing.
- Added material-pack prompt term extraction for text, Markdown, PPTX, and slide OCR JSON.
- Added optional ffmpeg preprocessing, audio chunking, SRT output, OpenAI structured correction, and basic Markdown summary output.
- Added optional OpenAI vision OCR for slide photos via `--ocr-images`.
- Added deterministic reference lookup planning via `--plan-reference-search`.
- Added live Crossref reference lookup and open PDF caching via `--lookup-references`.
- Added explicit PDF figure/table extraction command execution via `--extract-pdfs`.
- Added chunked transcript correction options for long recordings.
- Added correction-pair glossary accumulation via `--save-glossary`; TSV can be reused as `--terms-file`.
- Expanded deterministic profile summaries for seminar, lecture, and meeting outputs.
- Added source-separated enriched notes output via `--enrich-notes`.
- Added OpenAI LLM source-labeled rich summary output via `--llm-summarize`.
- Added Semantic Scholar fallback, publisher-specific PDF fallback, metadata quality scores, and review flags to reference lookup results.
- Added explicit additional research file input via `--additional-research-file`; loaded research notes are kept separate from STT prompt terms and passed only to source-labeled notes/rich summaries.
- Added human review queue support via `--write-review-queue`; accepted glossary candidates can be applied with `--review-decisions-file`.
- Added dependency-free static review UI generation: `--write-review-queue` now writes `review_queue.html`, and `stt review-ui` can regenerate it from an existing queue.
- Added skipped-by-default optional integration checks for live reference/publisher fallback and configured PDF extractor scripts.
- Added generic live web/reference search adapter via `--web-research-query` plus explicit `--web-research-endpoint`; results are merged only as `additional_research`.
- Updated README and PLAN to reflect reference-first, deck-level slide analysis and transcript/slide mutual support.

Live OpenAI STT is wired behind `OpenAiSttTranscriber`, local `mlx-whisper` is routed only when `--provider mlx-whisper` is selected, optional OpenAI transcript correction is wired behind `OpenAiTranscriptCorrector`, optional slide-photo OCR is wired behind `OpenAiSlideImageOcr`, reference lookup planning is deterministic behind `--plan-reference-search`, live Crossref/OpenAlex/Semantic Scholar lookup plus publisher PDF fallback/open PDF caching is behind `--lookup-references`, optional PDF figure/table extraction execution is wired behind explicit CLI flags, deterministic source-separated notes are wired behind `--enrich-notes`, explicit external research files are wired behind `--additional-research-file`, explicit web search endpoint calls are wired behind `--web-research-query`, review queues are wired behind `--write-review-queue`, accepted glossary decisions are wired through `--review-decisions-file`, and OpenAI source-labeled rich summaries are wired behind `--llm-summarize`. Tests still use fakes and do not call paid or network APIs.

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
- `src/stt_pipeline/local_whisper.py`: optional `mlx_whisper` command adapter and JSON normalizer.
- `src/stt_pipeline/transcript.py`: shared transcript result dataclasses.
- `src/stt_pipeline/audio_chunks.py`: ffmpeg segment planning plus chunk transcript timestamp merging.
- `src/stt_pipeline/materials.py`: material-pack loader for text, Markdown, PPTX, and slide OCR JSON prompt terms.
- `src/stt_pipeline/additional_research.py`: explicit additional research note loader for `.md`, `.txt`, and `.json` source-labeled evidence.
- `src/stt_pipeline/web_research.py`: generic JSON endpoint search adapter for explicit `--web-research-query` inputs.
- `src/stt_pipeline/preprocess.py`: deterministic ffmpeg preprocess command builder and runner.
- `src/stt_pipeline/report.py`: SRT rendering from timestamped transcript segments.
- `src/stt_pipeline/correct.py`: OpenAI structured correction adapter plus exact-change validation.
- `src/stt_pipeline/glossary.py`: TSV glossary accumulation from applied corrections.
- `src/stt_pipeline/review.py`: human review queue builder, validated queue loader, and dependency-free static review HTML renderer.
- `src/stt_pipeline/summarize.py`: basic source-separated Markdown summary generation.
- `src/stt_pipeline/rich_summary.py`: OpenAI structured rich summary adapter with source-label validation.
- `src/stt_pipeline/notes.py`: deterministic source-separated enriched notes generation.
- `src/stt_pipeline/vision_ocr.py`: OpenAI vision slide-photo OCR adapter using Responses API image inputs.
- `src/stt_pipeline/cli.py`: `run`, `transcribe`, `bakeoff`, and `review-ui` command handlers.
- `src/stt_pipeline/slide_extract.py`: OCR-text-to-slide-evidence heuristics.
- `src/stt_pipeline/reference_lookup.py`: DOI/Crossref/OpenAlex/Semantic Scholar lookup planning plus metadata quality scoring, publisher PDF fallback, and open PDF cache adapter.
- `src/stt_pipeline/pdf_tools.py`: command builder for the existing PDF figure/table extraction script.
- `tests/test_knowledge_pack.py`: tests for prioritization, PDF extraction jobs, and transcript-slide alignment.
- `tests/test_local_whisper.py`: tests for optional `mlx_whisper` command planning and JSON normalization.
- `tests/test_audio_chunks.py`: tests for ffmpeg chunk planning and merged transcript offsets.
- `tests/test_additional_research.py`: tests for explicit Markdown/JSON research-note ingestion.
- `tests/test_web_research.py`: tests for provider-neutral web research URL building and result normalization.
- `tests/test_slide_extract.py`: tests for OCR text classification into slide evidence.
- `tests/test_reference_lookup.py`: tests for DOI extraction, reference lookup planning, fake Crossref/OpenAlex/Semantic Scholar metadata, publisher fallback, review flags, and PDF cache.
- `tests/test_pdf_tools.py`: tests for PDF extraction command planning.
- `tests/test_review.py`: tests for review queue generation and accepted glossary decision filtering.
- `tests/test_rich_summary.py`: tests for structured rich summary rendering and source-label rejection.
- `tests/test_glossary.py`: tests for correction-pair glossary build/merge/read/write.
- `tests/test_optional_integrations.py`: skipped-by-default checks for optional `mlx_whisper`, live reference/publisher lookup, and configured PDF extractor scripts.
- `docs/tooling.md`: GitHub/tooling candidates and integration rules.

## Next Implementation Order

1. Add provider-specific web search integrations only behind explicit flags/config, if a real endpoint is chosen.
2. Test the static review UI on real non-private samples; add Gradio and low-confidence audio links only if that workflow proves insufficient.
3. Expand publisher fallback coverage only after optional integration samples prove value.

Keep real cloud STT and OpenAI API calls behind adapters. Tests should use fakes and local fixtures, not paid network calls.
OpenAI text model names must come from `OPENAI_MODEL`; use `OPENAI_VISION_MODEL` only when a distinct vision model is needed. Do not hardcode another provider model into the pipeline.
The STT router supports `gpt-4o`, `gpt-4o-mini`, `whisper-1`, `diarize`, and `mlx-whisper` provider aliases. Knowledge Pack remains optional; Phase 1 uses compact STT prompt hints, not heavy enrichment.
Use `--provider mlx-whisper` only when the local `mlx_whisper` CLI is installed. Configure it with `MLX_WHISPER_COMMAND` and `MLX_WHISPER_MODEL`; it is an offline fallback, not the default quality path.
`stt run ... --pack ./materials` now merges `--terms-file` with prompt terms extracted from `.txt`, `.md`, `.pptx`, slide OCR `.json`, and slide photos when `--ocr-images` is passed. PDFs are not mixed into prompt terms; they are tracked as `pdf_sources` and can be processed with `--extract-pdfs --pdf-extractor-script ...`.
Use `--plan-reference-search` to write `reference_lookup_jobs.json` with DOI, Crossref, OpenAlex, and DOI URL candidates. This does not perform network lookup or download.
Use `--lookup-references` to perform live Crossref/OpenAlex/Semantic Scholar metadata lookup, try publisher-specific PDF fallback URLs, and cache open PDF links into `reference_cache/*.pdf`. It also writes `reference_lookup_results.json` with `metadata_source`, `metadata_quality_score`, `review_flags`, and `publisher_pdf_urls`; when combined with `--extract-pdfs`, cached PDFs are passed to the figure/table extraction workflow.
Use `--preprocess` to run ffmpeg before STT. Use `--correct` only when `OPENAI_MODEL` is set; it asks for structured correction JSON and applies only exact declared replacements. Use `--summarize` for the basic Markdown summary.
Use `--chunk-audio --chunk-seconds 600` for long recordings that may exceed STT file upload limits. Chunking runs after preprocessing, writes `audio_chunks/chunk_*.wav`, transcribes each chunk, and offsets timestamps before writing the combined transcript.
Use `--correction-chunk-size` and `--correction-overlap` for long recordings; chunk provenance is written to `corrections.json` and `run_manifest.json`.
Use `--save-glossary ./glossary.tsv` with `--correct` to accumulate applied correction pairs. The saved TSV can be passed back as `--terms-file`; only the `corrected` column is used as prompt terms.
Use `--write-review-queue` to write `review_queue.json` and `review_queue.html` containing glossary candidates and reference metadata that needs human review. The HTML supports search, filtering, approval/rejection, and downloads `review_decisions.json`; pass that file back with `--review-decisions-file` alongside `--save-glossary` to save only accepted candidates. Use `stt review-ui path/to/review_queue.json --output path/to/review_queue.html` to regenerate the UI without rerunning STT.
`--summarize` currently uses deterministic profile templates, not an LLM summarizer.
`--llm-summarize` uses `OPENAI_MODEL` through `OpenAiRichSummarizer` and writes `rich_summary.md`. It requires every generated item to carry one of the allowed source labels: `speaker_transcript`, `slide_text`, `reference_pdf`, or `additional_research`.
`--additional-research-file` can be passed multiple times with `.md`, `.txt`, or `.json` research notes. It writes `additional_research.json` and passes those items to `notes.md` and `rich_summary.md` as `additional_research`; it does not affect STT prompt terms.
`--web-research-query` requires `--web-research-endpoint`. The endpoint should return JSON arrays under `items`, `results`, `organic`, or `webPages.value`; normalized results are written to `web_research_results.json` and merged into `additional_research.json`. This is explicit additional evidence only, not a default STT dependency.
`--enrich-notes` writes `notes.md` with explicit source sections: speaker transcript, slide text, reference PDF, additional research, and needs review. If `--plan-reference-search` is used, additional research includes planned lookup URLs; if `--lookup-references` is used, it includes lookup status, metadata source, quality score, review flags, title, and cached PDF path when available. If `--additional-research-file` is used, external research items appear in the same section with source path, URL, evidence, and summary.
Use `--ocr-images` only when `OPENAI_MODEL`/`OPENAI_VISION_MODEL` are configured and slide-photo OCR cost is acceptable.
Use `--extract-pdfs` only with an explicit extractor script path. The command runner executes the existing figure/table workflow and writes `pdf_extraction_jobs.json`; tests use fake runners.

## Conflict Guidance

- If `PLAN.md` conflicts, keep the fixed ending with the risk table as the final section.
- If implementation begins in another branch, prefer merging that branch into `codex/phase1-mvp` before adding more code.
- Keep Knowledge Pack enrichment separate from the transcript body. The project design requires source labels for generated notes and diff validation for transcript corrections.
