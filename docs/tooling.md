# Tooling Notes

This project should keep OCR, PDF parsing, web search, STT, and LLM calls behind adapters. Tests should use deterministic fixtures, not live services or paid APIs.

`src/stt_pipeline/reference_lookup.py` creates deterministic DOI/Crossref/OpenAlex/Semantic Scholar lookup plans and can, behind `--lookup-references`, perform metadata lookup, publisher-specific PDF fallback, metadata quality flagging, and open PDF caching. Tests use fake HTTP clients; do not add live network tests to the default suite.

`src/stt_pipeline/additional_research.py` loads explicit `.md`, `.txt`, or `.json` research notes from `--additional-research-file`. This is the current safe bridge for broad web/reference search results: collect them outside the default STT path, then pass them in as source-labeled additional evidence. Do not turn live web search into a default dependency.

`src/stt_pipeline/web_research.py` provides a generic JSON endpoint adapter for `--web-research-query`. It requires an explicit `--web-research-endpoint`, writes `web_research_results.json`, and merges normalized results into additional research evidence. Keep provider-specific search APIs behind this adapter or a separate explicit integration; never call live web search from the default STT path.

`src/stt_pipeline/review.py` renders `review_queue.html` as a self-contained static file. It deliberately uses no Gradio/server dependency: the browser updates item statuses in memory and downloads a queue-shaped `review_decisions.json` that `--review-decisions-file` already accepts. Add a heavier review framework only after real review samples demonstrate a need for audio playback or server-side persistence.

Optional integration tests live in `tests/test_optional_integrations.py`. They skip by default unless `STT_RUN_LIVE_REFERENCE_TESTS=1` is set or the configured PDF extractor inputs are available.
Set `STT_PDF_EXTRACTOR_SCRIPT` and `STT_PDF_SAMPLE` together to run the optional PDF extractor integration check. These checks are smoke tests only; keep deterministic unit tests as the default gate.

## Current Default Path

Use the existing local PDF figure/table extraction workflow first:

- PyMuPDF: page rendering, crop generation, and PDF text geometry.
- pdfplumber: PDF text and table candidate extraction.
- camelot-py: tighter table region extraction where digital table structure is available.

The adapter in `src/stt_pipeline/pdf_tools.py` builds the command for the existing script and the CLI can execute it only behind `--extract-pdfs --pdf-extractor-script ...`. Tests use injected runners and never invoke the real external tools.

## Candidate GitHub Tools

These are useful candidates, but none should be added as hard dependencies until a focused integration task chooses one.

| Tool | Candidate use | Notes |
|---|---|---|
| Camelot (`camelot-dev/camelot`) | Table extraction from PDFs | Already aligned with the current skill. Current Camelot supports multiple parsers, quality metrics, export formats, CLI usage, and optional OCR/ML backends. |
| PDFFigures2 (`allenai/pdffigures2`) | Extract captioned figures/tables and crops from scholarly PDFs | Strong match for reference-grounded figure/table crops. It is Scala/JVM-based and the upstream README notes a focus on computer science documents, so keep it optional. |
| GROBID (`grobidOrg/grobid`) | Parse scholarly metadata and bibliographic references | Good candidate for normalizing slide reference strings into structured paper metadata before PDF lookup. Usually runs as a service/container, so it belongs behind an adapter. |
| Docling (`docling-project/docling`) | General document conversion and layout/table extraction | Useful if slide/PDF ingestion expands beyond simple scholarly PDFs. Heavier than the current narrow path, so evaluate later. |

## Integration Rule

Add new tools in this order:

1. Define a small adapter interface and fixture-based tests.
2. Build command/API request objects without invoking the tool.
3. Add an optional integration test that is skipped unless the tool is installed.
4. Only then wire it into the CLI.

Do not replace the current PyMuPDF/pdfplumber/Camelot path until a real sample set shows a better result.
