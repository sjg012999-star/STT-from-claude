import json
from pathlib import Path
import tempfile
import unittest

from stt_pipeline.conference_context import (
    build_conference_context,
    find_manifest_entry,
    load_conference_archive,
    load_recording_manifest,
)


def _write_archive(path: Path) -> None:
    payload = {
        "generated_at": "2026-06-20T00:00:00Z",
        "agenda_url": "https://example.test/agenda",
        "sessions": [
            {
                "date": "Thursday, July 9, 2026",
                "time": "10:30 AM - 12:30 PM WEST",
                "title": "Tech Session VI: Nanomedicine & Nanoscale Delivery VII",
                "categories": ["Nanomedicine and Nanoscale Delivery"],
                "source_url": "https://example.test/session-vii",
                "presentation_id": "s-vii",
                "detail": {
                    "abstract": "Long-acting injectables, depots, and implantables",
                    "presentations": [
                        {
                            "time": "11:26 AM - 11:36 AM WEST",
                            "title": "Unraveling injectable liposomal depots",
                            "presenters": ["Speaker: Paola Luciani - University of Bern"],
                            "presentation_id": "p-liposome",
                        },
                        {
                            "time": "11:36 AM - 11:46 AM WEST",
                            "title": "Discovery of a new polymorph of TBAJ tartrate induced by wet milling",
                            "presenters": ["Speaker: Ben Boyd - Monash University"],
                            "presentation_id": "p-tbaj",
                        },
                    ],
                },
            },
            {
                "date": "Thursday, July 9, 2026",
                "time": "10:30 AM - 12:30 PM WEST",
                "title": "Tech Session VI: Nanomedicine & Nanoscale Delivery VIII",
                "categories": ["Nanomedicine and Nanoscale Delivery"],
                "source_url": "https://example.test/session-viii",
                "presentation_id": "s-viii",
                "detail": {
                    "abstract": "Inflammation and infection",
                    "presentations": [
                        {
                            "time": "11:36 AM - 11:46 AM WEST",
                            "title": "Tuning PEG chain length in LNPs",
                            "presenters": ["Speaker: Nadine Saber - Utrecht"],
                            "presentation_id": "p-peg",
                        }
                    ],
                },
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


class ConferenceContextTest(unittest.TestCase):
    def test_schedule_track_and_transcript_override_stale_filename_label(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            archive_path = root / "conference.json"
            manifest_path = root / "manifest.tsv"
            _write_archive(archive_path)
            manifest_path.write_text(
                "source_name\ttarget_name\tlisbon_start_WEST\tduration\tconfidence\tnote\tstatus\n"
                "raw.WAV\t2026-07-09_1137_Nano VII_Injectable Liposomal Depots.WAV\t"
                "2026-07-09 11:37:00\t00:09:00\tmedium\tplanned order\trenamed\n",
                encoding="utf-8",
            )
            archive = load_conference_archive(archive_path)
            manifest = load_recording_manifest(manifest_path)

            context = build_conference_context(
                "2026-07-09_1137_Nano VII_Injectable Liposomal Depots",
                (
                    "Ben Boyd presents a TBAJ tartrate polymorph discovered during wet milling. "
                    "The formulation is intended for long-acting injection."
                ),
                archive=archive,
                manifest_entries=manifest,
            )

        self.assertEqual(
            context["match"]["matched_session"]["presentation_id"],
            "s-vii",
        )
        self.assertEqual(context["match"]["session_confidence"], "high")
        self.assertEqual(
            context["match"]["presentation_candidates"][0]["presentation_id"],
            "p-tbaj",
        )
        self.assertIn(
            "schedule_is_planned_context",
            {item["code"] for item in context["match"]["warnings"]},
        )
        self.assertEqual(
            context["match"]["alternative_session_candidates"][0]["session"][
                "presentation_id"
            ],
            "s-viii",
        )

    def test_manifest_entry_matches_source_or_target_filename(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.tsv"
            manifest_path.write_text(
                "source_name\ttarget_name\tlisbon_start_WEST\tduration\tconfidence\tnote\tstatus\n"
                "old_name.WAV\t2026-07-09_1137_New Name.WAV\tstart\tduration\tmedium\tnote\tdone\n",
                encoding="utf-8",
            )
            entries = load_recording_manifest(manifest_path)

        self.assertEqual(find_manifest_entry("old_name", entries), entries[0])
        self.assertEqual(
            find_manifest_entry("2026-07-09_1137_New Name", entries),
            entries[0],
        )

    def test_explicit_missing_manifest_fails(self):
        with self.assertRaises(FileNotFoundError):
            load_recording_manifest("missing-recording-manifest.tsv")


if __name__ == "__main__":
    unittest.main()
