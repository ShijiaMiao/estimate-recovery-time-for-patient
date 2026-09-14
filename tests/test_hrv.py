import unittest

import numpy as np
import pandas as pd

from shiftrecover.hrv import (
    calculate_session_hrv,
    clean_bourdillon_rr,
    clean_rr_series,
    flag_rr_artifacts,
    rmssd,
    sdnn,
)


class HrvFormulaTests(unittest.TestCase):
    def test_rmssd_matches_hand_calculation(self):
        values = np.array([800.0, 820.0, 790.0])
        expected = np.sqrt((20**2 + (-30) ** 2) / 2)
        self.assertAlmostEqual(rmssd(values), expected)

    def test_sdnn_uses_sample_standard_deviation(self):
        values = np.array([800.0, 810.0, 820.0])
        self.assertAlmostEqual(sdnn(values), 10.0)


class HrvCleaningTests(unittest.TestCase):
    def test_flags_physiological_range_violation(self):
        result = flag_rr_artifacts([800] * 5 + [250] + [800] * 5)
        self.assertTrue(bool(result.loc[5, "artifact_flag"]))
        self.assertEqual(result.loc[5, "artifact_reason"], "below_range")

    def test_flags_local_median_spike(self):
        result = flag_rr_artifacts([800] * 5 + [1200] + [800] * 5)
        self.assertTrue(bool(result.loc[5, "artifact_flag"]))
        self.assertEqual(result.loc[5, "artifact_reason"], "local_median_deviation")

    def test_interpolates_internal_artifact(self):
        result = clean_rr_series([800] * 5 + [1200] + [800] * 5)
        self.assertEqual(float(result.loc[5, "nn_ms"]), 800.0)
        self.assertTrue(bool(result.loc[5, "was_interpolated"]))

    def test_preserves_unflagged_intervals(self):
        values = np.array([800.0, 805.0, 798.0, 810.0, 795.0])
        result = clean_rr_series(values, local_window=3)
        np.testing.assert_array_equal(result["nn_ms"], values)

    def test_preserves_smooth_high_variability(self):
        values = 800 + 180 * np.sin(np.linspace(0, 6 * np.pi, 101))
        result = flag_rr_artifacts(values)
        self.assertFalse(result["artifact_flag"].any())


class HrvSessionTests(unittest.TestCase):
    def _tidy(self, *, n: int = 360, artifact_indices: tuple[int, ...] = ()) -> pd.DataFrame:
        records = []
        for posture in ("supine", "standing"):
            values = np.full(n, 1000.0)
            values[list(artifact_indices)] = 250.0
            for index, value in enumerate(values, start=1):
                records.append(
                    {
                        "participant_id": "P01",
                        "date": pd.Timestamp("2025-01-01"),
                        "date_raw": pd.Timestamp("2025-01-01"),
                        "date_was_corrected": False,
                        "phase": "baseline",
                        "phase_order": 1,
                        "phase_day_observed": 1,
                        "phase_day_calendar": 1,
                        "recovery_day": pd.NA,
                        "protocol": "6-6",
                        "protocol_segment_minutes": 6,
                        "posture": posture,
                        "posture_source": "filename_explicit",
                        "posture_pair_complete": True,
                        "posture_rr_index": index,
                        "elapsed_seconds_in_posture": index,
                        "rr_ms": value,
                        "source_file": f"{posture}.txt",
                    }
                )
        return pd.DataFrame.from_records(records)

    def test_standardizes_to_first_three_minutes(self):
        cleaned = clean_bourdillon_rr(self._tidy(), analysis_window_seconds=180)
        metrics = calculate_session_hrv(cleaned)
        self.assertTrue(metrics["analysis_n_rr"].eq(180).all())

    def test_calculates_postures_separately(self):
        cleaned = clean_bourdillon_rr(self._tidy())
        metrics = calculate_session_hrv(cleaned)
        self.assertEqual(metrics["posture"].tolist(), ["standing", "supine"])
        self.assertEqual(len(metrics), 2)

    def test_constant_nn_series_has_zero_hrv(self):
        cleaned = clean_bourdillon_rr(self._tidy())
        metrics = calculate_session_hrv(cleaned)
        self.assertTrue(metrics["qc_pass"].all())
        self.assertTrue(metrics["rmssd_ms"].eq(0).all())
        self.assertTrue(metrics["sdnn_ms"].eq(0).all())

    def test_excess_artifacts_fail_qc_but_row_is_retained(self):
        artifacts = tuple(range(0, 20, 2))
        cleaned = clean_bourdillon_rr(self._tidy(n=180, artifact_indices=artifacts))
        metrics = calculate_session_hrv(cleaned, maximum_artifact_fraction=0.05)
        self.assertEqual(len(metrics), 2)
        self.assertFalse(metrics["qc_pass"].any())
        self.assertTrue(metrics["rmssd_ms"].isna().all())
        self.assertTrue(metrics["qc_status"].str.contains("excess_artifacts").all())


if __name__ == "__main__":
    unittest.main()
