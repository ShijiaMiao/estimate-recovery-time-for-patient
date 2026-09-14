import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from shiftrecover.bourdillon import (
    infer_test_protocol,
    load_bourdillon_rr,
    parse_bourdillon_filename,
    read_rr_values,
    split_combined_recording,
    summarize_bourdillon_participants,
    summarize_bourdillon_sessions,
)


class BourdillonFilenameTests(unittest.TestCase):
    def test_parses_standard_combined_filename(self):
        root = Path("RR")
        result = parse_bourdillon_filename(root / "Baseline" / "BHD98_20161020.txt", root)
        self.assertEqual(result.participant_id, "BHD98")
        self.assertEqual(result.phase, "baseline")
        self.assertIsNone(result.posture)

    def test_parses_missing_underscore(self):
        root = Path("RR")
        result = parse_bourdillon_filename(root / "Depriv" / "BRV9320161022.txt", root)
        self.assertEqual(result.participant_id, "BRV93")
        self.assertEqual(result.date, pd.Timestamp("2016-10-22"))

    def test_parses_explicit_posture_in_misspelled_folder(self):
        root = Path("RR")
        path = root / "Baseline" / "spearated" / "BHA95_20161005sup.txt"
        result = parse_bourdillon_filename(path, root)
        self.assertEqual(result.posture, "supine")

    def test_applies_documented_date_correction(self):
        root = Path("RR")
        result = parse_bourdillon_filename(root / "Depriv" / "BPJ93_20131101.txt", root)
        self.assertEqual(result.date_raw, pd.Timestamp("2013-11-01"))
        self.assertEqual(result.date, pd.Timestamp("2016-11-01"))
        self.assertTrue(result.date_was_corrected)

    def test_rejects_unknown_filename(self):
        with self.assertRaisesRegex(ValueError, "Unrecognized"):
            parse_bourdillon_filename(Path("RR/Baseline/not_a_record.txt"), Path("RR"))


class BourdillonValueTests(unittest.TestCase):
    def test_reads_one_value_per_line(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rr.txt"
            path.write_text("800\n801\n799\n", encoding="utf-8")
            np.testing.assert_array_equal(read_rr_values(path), [800, 801, 799])

    def test_rejects_non_numeric_value_with_line_number(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rr.txt"
            path.write_text("800\nbad\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "line 2"):
                read_rr_values(path)

    def test_protocol_classifier(self):
        self.assertEqual(infer_test_protocol(400), ("3-3", 3))
        self.assertEqual(infer_test_protocol(800), ("6-6", 6))

    def test_combined_split_uses_elapsed_time_not_row_half(self):
        values = np.array([60_000.0, 60_000.0, 60_000.0, 30_000.0, 30_000.0])
        supine, standing = split_combined_recording(values, segment_minutes=3)
        np.testing.assert_array_equal(supine, [0, 1, 2])
        np.testing.assert_array_equal(standing, [3, 4])


class BourdillonIntegrationTests(unittest.TestCase):
    def _make_dataset(self, root: Path) -> None:
        for phase in ("Baseline", "Depriv", "Recov"):
            (root / phase).mkdir(parents=True)
        values = "1000\n" * 360
        (root / "Baseline" / "PAA01_20250101.txt").write_text(values, encoding="utf-8")
        (root / "Depriv" / "PAA01_20250102.txt").write_text(values, encoding="utf-8")
        separated = root / "Recov" / "separated"
        separated.mkdir()
        (separated / "PAA01_20250103sup.txt").write_text(
            "1000\n" * 180, encoding="utf-8"
        )
        (separated / "PAA01_20250103std.txt").write_text(
            "1000\n" * 180, encoding="utf-8"
        )

    def test_loads_combined_and_explicit_postures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_dataset(root)
            tidy = load_bourdillon_rr(root)
        self.assertEqual(set(tidy["posture"]), {"supine", "standing"})
        self.assertEqual(
            set(tidy["posture_source"]),
            {"protocol_time_inferred", "filename_explicit"},
        )
        self.assertEqual(len(tidy), 1080)

    def test_assigns_recovery_day(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_dataset(root)
            tidy = load_bourdillon_rr(root)
        recovery = tidy.loc[tidy["phase"].eq("recovery"), "recovery_day"]
        self.assertTrue(recovery.eq(1).all())

    def test_flags_but_retains_out_of_range_rr(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_dataset(root)
            path = root / "Baseline" / "PAA01_20250101.txt"
            path.write_text(("1000\n" * 359) + "250\n", encoding="utf-8")
            tidy = load_bourdillon_rr(root)
        self.assertEqual(int(tidy["qc_out_of_range"].sum()), 1)
        self.assertIn(250, tidy["rr_ms"].tolist())

    def test_builds_session_and_participant_audits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_dataset(root)
            tidy = load_bourdillon_rr(root)
        sessions = summarize_bourdillon_sessions(tidy)
        participants = summarize_bourdillon_participants(tidy)
        self.assertEqual(len(sessions), 6)
        self.assertEqual(int(participants.loc[0, "total_observed_days"]), 3)
        self.assertTrue(bool(participants.loc[0, "has_all_three_phases"]))


if __name__ == "__main__":
    unittest.main()
