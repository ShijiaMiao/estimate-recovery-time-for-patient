import unittest

import numpy as np
import pandas as pd

from shiftrecover.baseline import estimate_personal_baselines, estimate_personal_hrv_baselines
from shiftrecover.circular import circular_mean_hours, signed_clock_difference
from shiftrecover.mauvieux import _extract_sleep_block
from shiftrecover.recovery import add_deviation_scores, estimate_recovery_events


class CircularTimeTests(unittest.TestCase):
    def test_midnight_distance_is_short(self):
        result = signed_clock_difference([0.5], 23.5)
        self.assertAlmostEqual(float(result[0]), 1.0)

    def test_circular_mean_straddles_midnight(self):
        result = circular_mean_hours([23.0, 1.0])
        self.assertTrue(result < 0.01 or result > 23.99)


class RecoveryTests(unittest.TestCase):
    def test_first_of_two_consecutive_recovered_days(self):
        dates = pd.date_range("2025-01-01", periods=9)
        frame = pd.DataFrame(
            {
                "participant_id": ["P1"] * 9,
                "date": dates,
                "shift_type": ["off", "off", "off", "night", "night", "off", "off", "off", "off"],
                "baseline_eligible": [True, True, True, False, False, False, False, False, False],
                "value": [10.0, 10.2, 9.8, 15.0, 15.0, 13.0, 10.4, 10.3, 10.2],
            }
        )
        baselines = estimate_personal_baselines(
            frame,
            {"value": "linear"},
            min_days=3,
            minimum_scales={"value": 0.5},
        )
        scored = add_deviation_scores(frame, baselines, {"value": "linear"}, minimum_features=1)
        events = estimate_recovery_events(scored, threshold=1.0, consecutive_days=2)
        self.assertEqual(int(events.loc[0, "recovery_days"]), 2)
        self.assertTrue(bool(events.loc[0, "recovered"]))

    def test_next_workday_censors_followup(self):
        frame = pd.DataFrame(
            {
                "participant_id": ["P1"] * 5,
                "date": pd.date_range("2025-01-01", periods=5),
                "shift_type": ["night", "night", "off", "day", "off"],
                "recovery_score": [4.0, 4.0, 2.0, 1.0, 0.5],
            }
        )
        events = estimate_recovery_events(frame, threshold=1.0, consecutive_days=1)
        self.assertFalse(bool(events.loc[0, "recovered"]))
        self.assertEqual(int(events.loc[0, "followup_off_days"]), 1)


class HrvBaselineTests(unittest.TestCase):
    def test_uses_only_qc_baseline_and_marks_insufficient_groups(self):
        rows = []
        for participant, days in (("P1", 5), ("P2", 3)):
            for day in range(1, days + 1):
                rows.append(
                    {
                        "participant_id": participant,
                        "date": pd.Timestamp(2025, 1, day),
                        "phase": "baseline",
                        "posture": "standing",
                        "qc_pass": day != 5 or participant == "P2",
                        "rmssd_ms": float(20 + day),
                        "sdnn_ms": float(40 + day),
                    }
                )
            rows.append(
                {
                    "participant_id": participant,
                    "date": pd.Timestamp(2025, 1, 10),
                    "phase": "recovery",
                    "posture": "standing",
                    "qc_pass": True,
                    "rmssd_ms": 25.0,
                    "sdnn_ms": 45.0,
                }
            )
        result = estimate_personal_hrv_baselines(pd.DataFrame(rows), min_days=4)
        p1 = result.loc[result["participant_id"].eq("P1")].iloc[0]
        p2 = result.loc[result["participant_id"].eq("P2")].iloc[0]
        self.assertEqual(int(p1["baseline_qc_eligible_days"]), 4)
        self.assertTrue(bool(p1["eligible_for_recovery_analysis"]))
        self.assertGreater(p1["rmssd_ms__normal_upper_ms"], p1["rmssd_ms__centre_ms"])
        self.assertEqual(p2["baseline_status"], "insufficient_baseline")
        self.assertTrue(np.isnan(p2["sdnn_ms__centre_ms"]))


class MauvieuxAdapterTests(unittest.TestCase):
    def test_extracts_three_phase_rows_without_claiming_dates(self):
        sheet = pd.DataFrame(np.nan, index=range(8), columns=range(18))
        sheet.iat[6, 2] = 1
        sheet.iloc[6, 3:8] = [500, 420, 30, 50, 0.84]
        sheet.iloc[6, 8:13] = [320, 240, 35, 45, 0.75]
        sheet.iloc[6, 13:18] = [360, 285, 25, 50, 0.79]
        result = _extract_sleep_block(
            sheet,
            start_row=6,
            end_row=6,
            study="study",
            group="group",
            condition="condition",
            participant_prefix="P_",
        )
        self.assertEqual(result["phase"].tolist(), ["ZT1", "ZT2", "ZT3"])
        self.assertNotIn("date", result.columns)
        self.assertEqual(result.loc[0, "participant_id"], "P_01")


if __name__ == "__main__":
    unittest.main()
