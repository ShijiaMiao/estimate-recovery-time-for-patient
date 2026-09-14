import unittest

import pandas as pd

from shiftrecover.sensitivity import (
    audit_threshold_monotonicity,
    build_threshold_stability_table,
    estimate_threshold_sensitivity,
)


class RecoveryThresholdSensitivityTests(unittest.TestCase):
    def _deviations(self) -> pd.DataFrame:
        scores = [1.8, 1.8, 1.2, 1.2]
        return pd.DataFrame(
            {
                "participant_id": ["P1"] * 4,
                "posture": ["standing"] * 4,
                "recovery_day": [1, 2, 3, 4],
                "expected_date": pd.date_range("2025-01-01", periods=4),
                "baseline_status": ["ready"] * 4,
                "eligible_for_recovery_analysis": [True] * 4,
                "deviation_status": ["calculated"] * 4,
                "hrv_deviation_score": scores,
                "rmssd_ms__abs_z": scores,
                "sdnn_ms__abs_z": scores,
            }
        )

    def test_three_thresholds_produce_three_event_sets(self):
        events = estimate_threshold_sensitivity(
            self._deviations(), thresholds=[1.0, 1.5, 2.0]
        )
        self.assertEqual(len(events), 9)
        self.assertEqual(set(events["sensitivity_threshold"]), {1.0, 1.5, 2.0})

    def test_lenient_threshold_recovers_no_later(self):
        events = estimate_threshold_sensitivity(
            self._deviations(), thresholds=[1.0, 1.5, 2.0]
        )
        composite = events.loc[events["endpoint"].eq("hrv_composite")]
        days = composite.set_index("sensitivity_threshold")["recovery_day"]
        self.assertTrue(pd.isna(days.loc[1.0]))
        self.assertEqual(int(days.loc[1.5]), 3)
        self.assertEqual(int(days.loc[2.0]), 1)
        self.assertFalse(audit_threshold_monotonicity(events)["monotonicity_violation"].any())

    def test_stability_table_has_one_row_per_series(self):
        events = estimate_threshold_sensitivity(
            self._deviations(), thresholds=[1.0, 1.5, 2.0]
        )
        stability = build_threshold_stability_table(events)
        self.assertEqual(len(stability), 1)
        self.assertIn("threshold_1_5__recovery_day", stability.columns)


if __name__ == "__main__":
    unittest.main()
