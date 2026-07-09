from pathlib import Path
import json
import tempfile
import unittest

from stt_pipeline.cli import main
from stt_pipeline.correct import Correction, CorrectionReport
from stt_pipeline.transcript import TranscriptResult, TranscriptSegment


class FakeTranscriber:
    def __init__(self):
        self.calls = []

    def transcribe(self, audio_path, *, provider=None, profile="seminar", prompt_terms=()):
        self.calls.append(
            {
                "audio_path": Path(audio_path),
                "provider": provider,
                "profile": profile,
                "prompt_terms": tuple(prompt_terms),
            }
        )
        selected_provider = provider or "gpt-4o"
        return TranscriptResult(
            provider=selected_provider,
            model=f"model-for-{selected_provider}",
            profile=profile,
            text=f"Transcript from {selected_provider}",
            segments=(
                TranscriptSegment(
                    segment_id="seg_001",
                    text=f"Transcript from {selected_provider}",
                    start_seconds=0.0,
                    end_seconds=3.0,
                    speaker="Speaker 1" if selected_provider == "diarize" else None,
                ),
            ),
            usage_seconds=3.0,
        )


class FakeCorrector:
    def __init__(self):
        self.calls = []

    def correct(self, result, *, prompt_terms=()):
        self.calls.append({"result": result, "prompt_terms": tuple(prompt_terms)})
        corrected = TranscriptResult(
            provider=result.provider,
            model=result.model,
            profile=result.profile,
            text=result.text.replace("Transcript", "Corrected transcript"),
            segments=tuple(
                TranscriptSegment(
                    segment_id=segment.segment_id,
                    text=segment.text.replace("Transcript", "Corrected transcript"),
                    start_seconds=segment.start_seconds,
                    end_seconds=segment.end_seconds,
                    speaker=segment.speaker,
                )
                for segment in result.segments
            ),
            usage_seconds=result.usage_seconds,
        )
        return CorrectionReport(
            corrected_result=corrected,
            applied_corrections=(
                Correction(
                    segment_id="seg_001",
                    original="Transcript",
                    corrected="Corrected transcript",
                    reason="test correction",
                    confidence="high",
                ),
            ),
            rejected_corrections=(),
        )


class FakeImageOcr:
    def __init__(self):
        self.calls = []

    def extract(self, image_path):
        from stt_pipeline.slide_extract import SlideOcrInput

        self.calls.append(Path(image_path))
        return SlideOcrInput(
            slide_id=Path(image_path).stem,
            title="The future of AI in IBD clinical practice",
            text_lines=[
                "The future of AI in IBD clinical practice",
                "Iacucci et al., Nature Reviews Gastroenterology & Hepatology 21, 510 (2024)",
            ],
            source_path=str(image_path),
        )


class FakeRichSummarizer:
    def __init__(self):
        self.calls = []

    def summarize(
        self,
        result,
        *,
        prompt_terms=(),
        material_pack=None,
        pdf_results=(),
        reference_lookup_plans=(),
        correction_report=None,
    ):
        from stt_pipeline.rich_summary import RichSummaryResult

        self.calls.append(
            {
                "result": result,
                "prompt_terms": tuple(prompt_terms),
                "material_pack": material_pack,
                "pdf_results": tuple(pdf_results),
                "reference_lookup_plans": tuple(reference_lookup_plans),
                "correction_report": correction_report,
            }
        )
        return RichSummaryResult(
            markdown="# Rich Summary\n\n## Key Findings\n\n- [speaker_transcript] Test rich summary. _(evidence: seg_001)_\n",
            section_count=1,
            item_count=1,
        )


class CliTest(unittest.TestCase):
    def test_transcribe_writes_json_and_markdown_with_terms(self):
        transcriber = FakeTranscriber()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            audio_path = root / "sample.wav"
            terms_path = root / "terms.txt"
            output_dir = root / "out"
            audio_path.write_bytes(b"fake audio")
            terms_path.write_text("InTesTiny\nIBD\n", encoding="utf-8")

            exit_code = main(
                [
                    "transcribe",
                    str(audio_path),
                    "--profile",
                    "seminar",
                    "--provider",
                    "gpt-4o",
                    "--terms-file",
                    str(terms_path),
                    "--output",
                    str(output_dir),
                ],
                transcriber=transcriber,
            )

            payload = json.loads((output_dir / "transcript.json").read_text(encoding="utf-8"))
            markdown = (output_dir / "transcript.md").read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual(transcriber.calls[0]["prompt_terms"], ("InTesTiny", "IBD"))
        self.assertEqual(payload["provider"], "gpt-4o")
        self.assertEqual(payload["segments"][0]["segment_id"], "seg_001")
        self.assertIn("# Transcript", markdown)
        self.assertIn("Transcript from gpt-4o", markdown)

    def test_bakeoff_writes_provider_outputs_and_report(self):
        transcriber = FakeTranscriber()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            audio_path = root / "sample.wav"
            output_dir = root / "bakeoff"
            audio_path.write_bytes(b"fake audio")

            exit_code = main(
                [
                    "bakeoff",
                    str(audio_path),
                    "--profile",
                    "seminar",
                    "--providers",
                    "whisper-1,gpt-4o-mini",
                    "--output",
                    str(output_dir),
                ],
                transcriber=transcriber,
            )

            whisper_payload = json.loads(
                (output_dir / "whisper-1.json").read_text(encoding="utf-8")
            )
            report = (output_dir / "bakeoff_report.md").read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual([call["provider"] for call in transcriber.calls], ["whisper-1", "gpt-4o-mini"])
        self.assertEqual(whisper_payload["model"], "model-for-whisper-1")
        self.assertIn("whisper-1", report)
        self.assertIn("gpt-4o-mini", report)

    def test_run_uses_material_pack_and_writes_prompt_terms(self):
        transcriber = FakeTranscriber()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            audio_path = root / "seminar.wav"
            materials_dir = root / "materials"
            output_dir = root / "out"
            audio_path.write_bytes(b"fake audio")
            materials_dir.mkdir()
            (materials_dir / "slides.md").write_text(
                "\n".join(
                    [
                        "Using InTesTinyTM for targeted nanoparticle design",
                        "NHS-PEG5k-cRGD cyclo(Arg-Gly-Asp-D-Tyr-Lys) was compared across healthy and IBD intestinal media.",
                    ]
                ),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "run",
                    str(audio_path),
                    "--profile",
                    "seminar",
                    "--provider",
                    "gpt-4o",
                    "--pack",
                    str(materials_dir),
                    "--output",
                    str(output_dir),
                ],
                transcriber=transcriber,
            )

            prompt_terms = (output_dir / "prompt_terms.txt").read_text(encoding="utf-8")
            pack_json = json.loads((output_dir / "knowledge_pack.json").read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertIn("InTesTinyTM", transcriber.calls[0]["prompt_terms"])
        self.assertIn("NHS-PEG5k-cRGD", prompt_terms)
        self.assertEqual(pack_json["slide_count"], 1)

    def test_run_can_preprocess_audio_and_writes_srt(self):
        transcriber = FakeTranscriber()
        runner_calls = []

        def runner(command):
            runner_calls.append(command)
            Path(command[-1]).write_bytes(b"preprocessed audio")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            audio_path = root / "raw.wav"
            output_dir = root / "out"
            audio_path.write_bytes(b"raw audio")

            exit_code = main(
                [
                    "run",
                    str(audio_path),
                    "--profile",
                    "seminar",
                    "--provider",
                    "gpt-4o",
                    "--preprocess",
                    "--output",
                    str(output_dir),
                ],
                transcriber=transcriber,
                command_runner=runner,
            )

            manifest = json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8"))
            srt = (output_dir / "transcript.srt").read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual(transcriber.calls[0]["audio_path"], output_dir / "preprocessed.wav")
        self.assertEqual(runner_calls[0][0], "ffmpeg")
        self.assertTrue(manifest["preprocess"]["enabled"])
        self.assertIn("00:00:00,000 --> 00:00:03,000", srt)

    def test_run_can_write_corrected_transcript_and_summary(self):
        transcriber = FakeTranscriber()
        corrector = FakeCorrector()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            audio_path = root / "sample.wav"
            output_dir = root / "out"
            audio_path.write_bytes(b"fake audio")

            exit_code = main(
                [
                    "run",
                    str(audio_path),
                    "--profile",
                    "seminar",
                    "--provider",
                    "gpt-4o",
                    "--correct",
                    "--summarize",
                    "--output",
                    str(output_dir),
                ],
                transcriber=transcriber,
                corrector=corrector,
            )

            corrected = (output_dir / "corrected_transcript.md").read_text(encoding="utf-8")
            corrections = json.loads((output_dir / "corrections.json").read_text(encoding="utf-8"))
            summary = (output_dir / "summary.md").read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn("Corrected transcript from gpt-4o", corrected)
        self.assertEqual(corrections["applied_corrections"][0]["corrected"], "Corrected transcript")
        self.assertIn("# Seminar Summary", summary)
        self.assertEqual(corrector.calls[0]["prompt_terms"], ())

    def test_run_can_configure_correction_chunking(self):
        transcriber = FakeTranscriber()
        corrector = FakeCorrector()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            audio_path = root / "sample.wav"
            output_dir = root / "out"
            audio_path.write_bytes(b"fake audio")

            exit_code = main(
                [
                    "run",
                    str(audio_path),
                    "--profile",
                    "seminar",
                    "--provider",
                    "gpt-4o",
                    "--correct",
                    "--correction-chunk-size",
                    "12",
                    "--correction-overlap",
                    "2",
                    "--output",
                    str(output_dir),
                ],
                transcriber=transcriber,
                corrector=corrector,
            )

            manifest = json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(manifest["correction"]["chunk_size"], 12)
        self.assertEqual(manifest["correction"]["overlap"], 2)

    def test_run_can_ocr_image_materials(self):
        transcriber = FakeTranscriber()
        image_ocr = FakeImageOcr()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            audio_path = root / "sample.wav"
            materials_dir = root / "materials"
            output_dir = root / "out"
            audio_path.write_bytes(b"fake audio")
            materials_dir.mkdir()
            image_path = materials_dir / "slide-27.jpg"
            image_path.write_bytes(b"fake image")

            exit_code = main(
                [
                    "run",
                    str(audio_path),
                    "--profile",
                    "seminar",
                    "--provider",
                    "gpt-4o",
                    "--pack",
                    str(materials_dir),
                    "--ocr-images",
                    "--output",
                    str(output_dir),
                ],
                transcriber=transcriber,
                image_ocr=image_ocr,
            )

            pack_json = json.loads((output_dir / "knowledge_pack.json").read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(image_ocr.calls, [image_path])
        self.assertEqual(pack_json["slide_count"], 1)
        self.assertIn("Iacucci et al.", "\n".join(transcriber.calls[0]["prompt_terms"]))

    def test_run_can_extract_pdf_materials_with_explicit_flag(self):
        transcriber = FakeTranscriber()
        runner_calls = []

        def runner(command):
            runner_calls.append(command)

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            audio_path = root / "sample.wav"
            materials_dir = root / "materials"
            output_dir = root / "out"
            script_path = root / "extract-figures-tables.py"
            audio_path.write_bytes(b"fake audio")
            materials_dir.mkdir()
            (materials_dir / "iacucci-2024.pdf").write_bytes(b"%PDF-1.7 fake")
            (materials_dir / "slides.md").write_text(
                "Iacucci et al., Nature Reviews Gastroenterology & Hepatology 21, 510 (2024)\n",
                encoding="utf-8",
            )
            script_path.write_text("# fake extractor\n", encoding="utf-8")

            exit_code = main(
                [
                    "run",
                    str(audio_path),
                    "--profile",
                    "seminar",
                    "--provider",
                    "gpt-4o",
                    "--pack",
                    str(materials_dir),
                    "--extract-pdfs",
                    "--pdf-extractor-script",
                    str(script_path),
                    "--output",
                    str(output_dir),
                ],
                transcriber=transcriber,
                command_runner=runner,
            )

            pdf_manifest = json.loads((output_dir / "pdf_extraction_jobs.json").read_text(encoding="utf-8"))
            pack_json = json.loads((output_dir / "knowledge_pack.json").read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(runner_calls), 1)
        self.assertEqual(pdf_manifest["jobs"][0]["status"], "planned")
        self.assertIn("--pdf", runner_calls[0])
        self.assertEqual(len(pack_json["pdf_sources"]), 1)

    def test_run_can_write_enriched_notes_with_pdf_results(self):
        transcriber = FakeTranscriber()
        runner_calls = []

        def runner(command):
            runner_calls.append(command)

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            audio_path = root / "sample.wav"
            materials_dir = root / "materials"
            output_dir = root / "out"
            script_path = root / "extract-figures-tables.py"
            audio_path.write_bytes(b"fake audio")
            materials_dir.mkdir()
            (materials_dir / "slides.md").write_text(
                "\n".join(
                    [
                        "The future of AI in IBD clinical practice",
                        "Iacucci et al., Nature Reviews Gastroenterology & Hepatology 21, 510 (2024)",
                    ]
                ),
                encoding="utf-8",
            )
            (materials_dir / "iacucci-2024.pdf").write_bytes(b"%PDF-1.7 fake")
            script_path.write_text("# fake extractor\n", encoding="utf-8")

            exit_code = main(
                [
                    "run",
                    str(audio_path),
                    "--profile",
                    "seminar",
                    "--provider",
                    "gpt-4o",
                    "--pack",
                    str(materials_dir),
                    "--extract-pdfs",
                    "--pdf-extractor-script",
                    str(script_path),
                    "--enrich-notes",
                    "--output",
                    str(output_dir),
                ],
                transcriber=transcriber,
                command_runner=runner,
            )

            notes = (output_dir / "notes.md").read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(runner_calls), 1)
        self.assertIn("## Speaker Transcript", notes)
        self.assertIn("_source: speaker_transcript_", notes)
        self.assertIn("## Reference PDF", notes)
        self.assertIn("Iacucci et al.", notes)

    def test_run_can_plan_reference_search_from_slide_references(self):
        transcriber = FakeTranscriber()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            audio_path = root / "sample.wav"
            materials_dir = root / "materials"
            output_dir = root / "out"
            audio_path.write_bytes(b"fake audio")
            materials_dir.mkdir()
            (materials_dir / "slides.md").write_text(
                "\n".join(
                    [
                        "The future of AI in IBD clinical practice",
                        "Iacucci et al., Nat Rev Gastroenterol Hepatol. 2024;21:510. doi:10.1038/s41575-024-00913-8",
                    ]
                ),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "run",
                    str(audio_path),
                    "--profile",
                    "seminar",
                    "--provider",
                    "gpt-4o",
                    "--pack",
                    str(materials_dir),
                    "--plan-reference-search",
                    "--enrich-notes",
                    "--output",
                    str(output_dir),
                ],
                transcriber=transcriber,
            )

            reference_jobs = json.loads(
                (output_dir / "reference_lookup_jobs.json").read_text(encoding="utf-8")
            )
            notes = (output_dir / "notes.md").read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual(reference_jobs["references"][0]["status"], "planned")
        self.assertEqual(
            reference_jobs["references"][0]["doi"],
            "10.1038/s41575-024-00913-8",
        )
        self.assertIn("https://doi.org/10.1038/s41575-024-00913-8", notes)

    def test_run_can_write_llm_rich_summary_with_source_labels(self):
        transcriber = FakeTranscriber()
        summarizer = FakeRichSummarizer()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            audio_path = root / "sample.wav"
            output_dir = root / "out"
            audio_path.write_bytes(b"fake audio")

            exit_code = main(
                [
                    "run",
                    str(audio_path),
                    "--profile",
                    "seminar",
                    "--provider",
                    "gpt-4o",
                    "--llm-summarize",
                    "--output",
                    str(output_dir),
                ],
                transcriber=transcriber,
                summarizer=summarizer,
            )

            rich_summary = (output_dir / "rich_summary.md").read_text(encoding="utf-8")
            manifest = json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertIn("# Rich Summary", rich_summary)
        self.assertEqual(len(summarizer.calls), 1)
        self.assertTrue(manifest["llm_summarized"])


if __name__ == "__main__":
    unittest.main()
