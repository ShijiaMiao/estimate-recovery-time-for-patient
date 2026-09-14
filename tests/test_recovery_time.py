import unittest

import numpy as np
import pandas as pd

from shiftrecover.recovery_time import estimate_hrv_recovery_events


class FirstRecoveryTimeTests(unittest.TestCase):
    def _days(
        self,
        scores: list[float],
        statuses: list[str] | None = None,
        *,
        eligible: bool = True,
    ) -> pd.DataFrame:
        statuses = statuses or ["calculated"] * len(scores)
        rows = []
        for day, (score, status) in enumerate(zip(scores, statuses, strict=True), start=1):
            rows.append(
                {
                    "participant_id": "P1",
                    "posture": "standing",
                    "recovery_day": day,
                    "expected_date": pd.Timestamp("2025-01-01") + pd.Timedelta(days=day - 1),
                    "baseline_status": "ready" if eligible else "insufficient_baseline",
                    "eligible_for_recovery_analysis": eligible,
                    "deviation_status": status,
                    "hrv_deviation_score": score,
                    "rmssd_ms__abs_z": score,
                    "sdnn_ms__abs_z": score,
                }
            )
        return pd.DataFrame(rows)

    def test_first_of_two_consecutive_days_is_event_day(self):
        result = estimate_hrv_recovery_events(self._days([2.0, 1.0, 1.2, 0.8]))
        event = result.loc[result["endpoint"].eq("hrv_composite")].iloc[0]
        self.assertEqual(int(event["recovery_day"]), 2)
        self.assertEqual(int(event["confirmation_day"]), 3)
        self.assertTrue(bool(event["event_observed"]))

    def test_missing_day_breaks_consecutive_run(self):
        frame = self._days(
            [1.0, np.nan, 1.0, 1.0],
            ["calculated", "missing_observation", "calculated", "calculated"],
        )
        event = estimate_hrv_recovery_events(frame).query("endpoint == 'hrv_composite'").iloc[0]
        self.assertEqual(int(event["recovery_day"]), 3)
        self.assertTrue(bool(event["has_intermittent_missing"]))

    def test_unrecovered_series_is_censored_at_last_evaluable_day(self):
        frame = self._days(
            [2.0, 2.0, np.nan],
            ["calculated", "calculated", "missing_observation"],
        )
        event = estimate_hrv_recovery_events(frame).query("endpoint == 'hrv_composite'").iloc[0]
        self.assertTrue(bool(event["right_censored"]))
        self.assertEqual(int(event["censor_day"]), 2)
        self.assertEqual(int(event["analysis_time_days"]), 2)

    def test_ineligible_baseline_does_not_enter_risk_set(self):
        event = estimate_hrv_recovery_events(
            self._days([1.0, 1.0], eligible=False)
        ).query("endpoint == 'hrv_composite'").iloc[0]
        self.assertFalse(bool(event["survival_eligible"]))
        self.assertFalse(bool(event["right_censored"]))
        self.assertEqual(event["analysis_status"], "insufficient_baseline")


if __name__ == "__main__":
    unittest.main()
