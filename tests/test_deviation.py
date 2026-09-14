import unittest

import numpy as np
import pandas as pd

from shiftrecover.deviation import build_hrv_recovery_deviations


class HrvRecoveryDeviationTests(unittest.TestCase):
    def _baseline(self, participant: str, status: str = "ready") -> dict[str, object]:
        eligible = status == "ready"
        row: dict[str, object] = {
            "participant_id": participant,
            "posture": "standing",
            "baseline_status": status,
            "eligible_for_recovery_analysis": eligible,
            "range_multiplier": 1.5,
        }
        for metric, centre in (("rmssd_ms", 20.0), ("sdnn_ms", 40.0)):
            row[f"{metric}__centre_log"] = np.log(centre) if eligible else np.nan
            row[f"{metric}__scale_log"] = 0.1 if eligible else np.nan
            row[f"{metric}__centre_ms"] = centre if eligible else np.nan
            row[f"{metric}__normal_lower_ms"] = centre * np.exp(-0.15)
            row[f"{metric}__normal_upper_ms"] = centre * np.exp(0.15)
        return row

    def _metrics(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "participant_id": "P1",
                    "date": pd.Timestamp("2025-01-10"),
                    "phase": "recovery",
                    "posture": "standing",
                    "recovery_day": 1,
                    "qc_pass": True,
                    "qc_status": "pass",
                    "protocol": "3-3",
                    "posture_source": "filename_explicit",
                    "artifact_fraction": 0.0,
                    "rmssd_ms": 20 * np.exp(0.1),
                    "sdnn_ms": 40.0,
                },
                {
                    "participant_id": "P1",
                    "date": pd.Timestamp("2025-01-12"),
                    "phase": "recovery",
                    "posture": "standing",
                    "recovery_day": 3,
                    "qc_pass": False,
                    "qc_status": "excess_artifacts",
                    "protocol": "3-3",
                    "posture_source": "filename_explicit",
                    "artifact_fraction": 0.1,
                    "rmssd_ms": np.nan,
                    "sdnn_ms": np.nan,
                },
            ]
        )

    def test_calculates_signed_personal_z_and_composite(self):
        result = build_hrv_recovery_deviations(
            self._metrics(), pd.DataFrame([self._baseline("P1")]), max_recovery_day=3
        )
        day1 = result.loc[result["recovery_day"].eq(1)].iloc[0]
        self.assertAlmostEqual(day1["rmssd_ms__signed_z"], 1.0)
        self.assertAlmostEqual(day1["sdnn_ms__signed_z"], 0.0)
        self.assertAlmostEqual(day1["hrv_deviation_score"], np.sqrt(0.5))

    def test_complete_grid_retains_missing_and_qc_failed_days(self):
        result = build_hrv_recovery_deviations(
            self._metrics(), pd.DataFrame([self._baseline("P1")]), max_recovery_day=3
        )
        self.assertEqual(result["deviation_status"].tolist(), [
            "calculated",
            "missing_observation",
            "session_qc_failed",
        ])
        self.assertEqual(result.loc[1, "expected_date"], pd.Timestamp("2025-01-11"))

    def test_insufficient_baseline_is_explicit(self):
        baselines = pd.DataFrame(
            [self._baseline("P1"), self._baseline("P2", "insufficient_baseline")]
        )
        result = build_hrv_recovery_deviations(
            self._metrics(), baselines, max_recovery_day=2
        )
        p2 = result.loc[result["participant_id"].eq("P2")]
        self.assertTrue(p2["deviation_status"].eq("insufficient_baseline").all())
        self.assertTrue(p2["hrv_deviation_score"].isna().all())


if __name__ == "__main__":
    unittest.main()
