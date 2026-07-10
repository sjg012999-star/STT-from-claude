from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest

from stt_pipeline.conference_context import load_conference_archive
from stt_pipeline.conference_correction import (
    _validate_alignment,
    _validate_processor,
    apply_conference_correction_responses,
    generate_conference_correction_jobs,
)
from stt_pipeline.transcript import TranscriptResult, TranscriptSegment


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _archive_payload() -> dict[str, object]:
    return {
        "generated_at": "2026-06-20T00:00:00Z",
        "agenda_url": "https://example.test/agenda",
        "sessions": [
            {
                "date": "Thursday, July 9, 2026",
                "time": "11:00 AM - 12:00 PM WEST",
                "title": "Tech Session VI: Long-Acting Injectables VII",
                "categories": ["Long-Acting Injectables"],
                "source_url": "https://example.test/session",
                "presentation_id": "s1",
                "detail": {
                    "abstract": "Ultra-long-acting HIV treatment",
                    "presentations": [
                        {
                            "time": "11:16 AM - 11:30 AM WEST",
                            "title": "Ultra-Long-Acting Injectable Doravirine Implant for HIV Treatment",
                            "presenters": ["Speaker: Rahima Benhabbour - UNC"],
                            "presentation_id": "p1",
                        }
                    ],
                },
            }
        ],
    }


class ConferenceCorrectionTest(unittest.TestCase):
    def test_processor_must_use_codex_chatgpt_oauth(self):
        with self.assertRaisesRegex(ValueError, "ChatGPT OAuth"):
            _validate_processor(
                {
                    "surface": "Codex",
                    "authentication": "Platform API",
                    "model": "test-model",
                }
            )

    def test_session_level_alignment_is_valid_for_plenary(self):
        job = {
            "conference_context": {
                "match": {
                    "matched_session": {
                        "presentation_id": "plenary-1",
                        "presentations": [],
                    },
                    "alternative_session_candidates": [],
                },
                "evidence_catalog": [
                    {"evidence_id": "conference.session:plenary-1"}
                ],
            }
        }
        alignment = [
            {
                "presentation_id": "plenary-1",
                "status": "confirmed",
                "confidence": "high",
                "evidence_refs": ["conference.session:plenary-1"],
                "reason": "The plenary is represented directly by the session record.",
            }
        ]

        validated = _validate_alignment(alignment, job)

        self.assertEqual(validated[0]["validation_status"], "valid")
        self.assertEqual(validated[0]["validation_errors"], [])

    def test_jobs_and_apply_preserve_v0_and_validate_evidence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output_root = root / "crs_2026_2026-07-09"
            session_name = "2026-07-09_1124_LAI VII_Doravirine Implant"
            transcript_path = output_root / "sessions" / session_name / "transcript.json"
            transcript = TranscriptResult(
                provider="gpt-4o",
                model="gpt-4o-transcribe",
                profile="seminar",
                text=(
                    "Long Acting Drug Mart uses effective anti-bacterial therapy of ART. "
                    "Daily pills remain common."
                ),
                segments=(
                    TranscriptSegment(
                        segment_id="seg_001",
                        text=(
                            "Long Acting Drug Mart uses effective anti-bacterial therapy of ART. "
                            "Daily pills remain common."
                        ),
                    ),
                ),
            )
            _write_json(transcript_path, asdict(transcript))
            archive_path = root / "conference.json"
            _write_json(archive_path, _archive_payload())
            archive = load_conference_archive(archive_path)
            source_before = transcript_path.read_bytes()

            batch = generate_conference_correction_jobs(
                [output_root],
                archive=archive,
                batch_index_path=root / "jobs.json",
            )
            job_info = batch["jobs"][0]
            job = json.loads(Path(job_info["job_path"]).read_text(encoding="utf-8"))
            response = {
                "job_id": job["job_id"],
                "processor": {
                    "surface": "Codex",
                    "authentication": "ChatGPT OAuth",
                    "model": "test-model",
                },
                "presentation_alignment": [
                    {
                        "presentation_id": "p1",
                        "status": "confirmed",
                        "confidence": "high",
                        "evidence_refs": ["transcript:seg_001", "conference.presentation:p1"],
                        "reason": "The speaker names doravirine and HIV treatment.",
                    }
                ],
                "corrections": [
                    {
                        "segment_id": "seg_001",
                        "original": "anti-bacterial therapy",
                        "corrected": "antiretroviral therapy",
                        "reason": "ART and the HIV talk title directly support the term.",
                        "confidence": "high",
                        "evidence_refs": ["transcript:seg_001", "conference.presentation:p1"],
                    },
                    {
                        "segment_id": "seg_001",
                        "original": "Mart",
                        "corrected": "part",
                        "reason": "Sentence syntax strongly supports 'as part'.",
                        "confidence": "medium",
                        "evidence_refs": ["transcript:seg_001", "conference.session:s1"],
                    },
                    {
                        "segment_id": "seg_001",
                        "original": "Daily pills",
                        "corrected": "Oral tablets",
                        "reason": "Possible paraphrase, not certain ASR correction.",
                        "confidence": "low",
                        "evidence_refs": ["transcript:seg_001"],
                    },
                    {
                        "segment_id": "seg_001",
                        "original": "ART",
                        "corrected": "antiretroviral therapy",
                        "reason": "Uses an unrecognized evidence identifier.",
                        "confidence": "high",
                        "evidence_refs": ["transcript:seg_001", "conference.presentation:missing"],
                    },
                ],
                "notes": ["Test response"],
            }
            _write_json(Path(job_info["response_path"]), response)

            summary = apply_conference_correction_responses(
                [output_root],
                minimum_confidence="medium",
                require_all_responses=True,
            )
            destination = (
                output_root
                / "versions"
                / "V1_conference_aware"
                / "sessions"
                / session_name
            )
            corrected = json.loads((destination / "transcript.json").read_text(encoding="utf-8"))
            corrections = json.loads(
                (destination / "corrections.json").read_text(encoding="utf-8")
            )
            version_manifest = json.loads(
                (destination / "version_manifest.json").read_text(encoding="utf-8")
            )
            source_after = transcript_path.read_bytes()

        self.assertIn("Drug part", corrected["text"])
        self.assertIn("antiretroviral therapy of ART", corrected["text"])
        self.assertIn("Daily pills", corrected["text"])
        self.assertEqual(summary["applied_count"], 2)
        self.assertEqual(summary["withheld_count"], 1)
        self.assertEqual(summary["rejected_count"], 1)
        self.assertEqual(len(corrections["applied"]), 2)
        self.assertEqual(corrections["withheld"][0]["confidence"], "low")
        self.assertIn("unknown evidence_refs", corrections["rejected"][0]["validation_errors"][0])
        self.assertEqual(source_after, source_before)
        self.assertTrue(version_manifest["source_unchanged"])
        self.assertEqual(
            version_manifest["source_sha256_before"],
            version_manifest["source_sha256_after"],
        )


if __name__ == "__main__":
    unittest.main()
