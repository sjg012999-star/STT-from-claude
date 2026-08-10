---
name: conference-stt
description: Transcribe and conservatively context-correct Korean or English conference, seminar, lecture, and meeting audio with the STT-from-claude CLI while preserving raw outputs. Use for Slack audio attachments and local M4A, WAV, MP3, or similar recordings, especially technical or pharmaceutical talks with supplied topic, speaker, slide, glossary, or organization context.
---

# Conference STT

Use the existing `stt-conference` pipeline as the transcription engine. Keep the
cloud STT output immutable, then create any context-aware correction as a
separate, auditable version.

## Resolve the Runtime

1. Work on the Mac that runs Hermes and received the audio attachment.
2. Prefer an existing `stt` executable after confirming that `stt --help`
   exposes `transcribe`, `run`, and the expected profile options.
3. Otherwise, use the checkout selected by `STT_CONFERENCE_REPO` or an existing
   checkout whose Git remote is
   `https://github.com/sjg012999-star/STT-from-claude.git`.
4. From a checkout, prefer `<repo>/.venv/bin/stt`. Do not assume that the
   repository path on another Mac matches the path on the source Mac.
5. If neither the CLI nor a checkout exists, stop and request approval to clone
   the `codex/phase1-mvp` branch and perform the one-time installation. Do not
   silently install packages during a transcription request.
6. For one-time setup, create a Python 3.11+ virtual environment and use a
   regular package install, not an editable install:

   ```bash
   python3 -m venv .venv
   .venv/bin/python -m pip install '.[gemini,pdf]'
   ```

7. Require `OPENAI_API_KEY` or the macOS Keychain service
   `stt-conference-openai`. Never request, display, log, or return a secret in
   Slack. If credentials are absent, tell the user to configure them locally.
8. Require `ffmpeg` only when preprocessing or external chunking is necessary.

## Prepare the Job

1. Resolve every incoming attachment to an existing absolute local path.
2. Create a durable job directory under the active workspace or
   `STT_CONFERENCE_OUTPUT_ROOT`. Do not use a Slack/Hermes cache directory or
   `/tmp` as the final output location.
3. Copy the original attachment byte-for-byte into `source/`; never move,
   rename, re-encode, or overwrite the only source copy.
4. Record the copied source path and SHA-256 before processing.
5. Put user-supplied proper nouns and topic context into `context_terms.txt`,
   one concise term per line. Use only context the user supplied or material
   that is actually available. Do not infer a talk's claims from its title.
6. Select the profile from the request:
   - conference or seminar talk: `seminar`
   - general lecture: `lecture`
   - meeting: `meeting`
   Default to `seminar` only when the recording is clearly a presentation.

## Produce the Raw Transcript

Write the provider output to a dedicated `V0_raw/` directory:

```bash
stt transcribe AUDIO_PATH \
  --profile seminar \
  --provider gpt-transcribe \
  --terms-file CONTEXT_TERMS \
  --output OUTPUT_ROOT/V0_raw
```

Adjust this command conservatively:

- Omit `--terms-file` when no grounded terms are available.
- Use `gpt-transcribe` for seminar and lecture transcription by default. Keep
  `gpt-4o` only as an explicit legacy fallback; meeting diarization still uses
  the whole file with `--provider diarize`.
- Prefer whole-file transcription when the provider accepts the input.
- Add `--preprocess` only when normalization is useful.
- Add `--chunk-audio --chunk-seconds 600` only when file-size or duration
  constraints require external chunking.
- Never combine `--chunk-audio` with the `diarize` provider. Use the whole
  meeting file with `--provider diarize`.
- Use `--pack MATERIALS_DIR` only when the user supplied slides, OCR JSON,
  Markdown, text, or PPTX material.
- Do not enable `--correct`, `--llm-summarize`, `--ocr-images`,
  `--lookup-references`, or other additional paid/network processing unless the
  user explicitly requests and authorizes it.
- Treat an explicit request to transcribe as authorization for the selected
  cloud STT call, but report the provider and avoid duplicate calls.

Do not modify files under `V0_raw/` after the CLI finishes.

## Create the Context-Corrected Version

When the user requests contextual correction, use the current agent session to
create `V1_context_corrected/` without calling the optional paid `--correct`
path by default:

1. Read `V0_raw/transcript.md` and the available user context.
2. Correct only probable ASR errors supported by transcript context, supplied
   terms, slides, or references.
3. Preserve meaning, sequence, timestamps, speaker uncertainty, numbers, and
   negation. Do not add facts that are absent from the recording.
4. Process long transcripts in bounded overlapping sections. Apply only
   replacements whose original text exists exactly in V0.
5. Write:
   - `transcript_corrected.md`
   - `correction_log.md` with original text, corrected text, evidence, and
     confidence
   - `summary.md` with source-separated takeaways and a needs-review section
6. Leave low-confidence names, figures, acronyms, and inaudible passages
   unchanged and list them under needs review.
7. Never describe the corrected version as verbatim audio.

## Verify and Deliver

Before reporting completion:

1. Confirm that the CLI exited successfully and that these V0 files exist and
   are non-empty:
   - `transcript.md`
   - `transcript.json`
   - `transcript.srt`
   - `run_manifest.json`
2. Recompute the source SHA-256 and confirm that it matches the pre-run value.
3. Confirm that `V0_raw/` was not changed while creating V1.
4. Check every correction-log source string against V0 and retain unresolved
   items for human review.
5. Report the source filename, profile, provider, optional flags, output
   directory, correction basis, and remaining uncertainties.
6. In Slack, return the absolute paths to the raw transcript, corrected
   transcript, correction log, and summary so Hermes uploads them as files.
   Do not paste a long transcript into the chat.
7. Never commit recordings, transcripts, API keys, private slides, or generated
   session artifacts to Git.

## Example Request

> Transcribe the attached M4A with the conference STT workflow. It is a Korean
> seminar about applying AX in a pharmaceutical factory. Preserve the raw
> transcript and return a separate context-corrected transcript and correction
> log.
