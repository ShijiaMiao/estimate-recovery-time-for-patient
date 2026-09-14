import unittest

import numpy as np
import pandas as pd

from shiftrecover.comparison import (
    audit_method_comparison,
    build_method_comparison_paired_table,
    estimate_method_comparison_events,
    estimate_population_hrv_baselines,
    expand_population_baselines_to_common_risk_set,
    render_method_comparison_report,
    summarize_method_comparison,
    summarize_method_discordance,
)


class RecoveryMethodComparisonTests(unittest.TestCase):
    def _personal_baselines(self) -> pd.DataFrame:
        rows = []
        for participant, rmssd, sdnn in (("P1", 20.0, 40.0), ("P2", 80.0, 120.0)):
            rows.append(
                {
                    "participant_id": participant,
                    "posture": "standing",
                    "baseline_sufficient": True,
                    "eligible_for_recovery_analysis": True,
                    "rmssd_ms__centre_log": np.log(rmssd),
                    "sdnn_ms__centre_log": np.log(sdnn),
                }
            )
        return pd.DataFrame(rows)

    def _deviations(self, scores: list[float]) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "participant_id": ["P1"] * len(scores),
                "posture": ["standing"] * len(scores),
                "recovery_day": range(1, len(scores) + 1),
                "expected_date": pd.date_range("2025-01-01", periods=len(scores)),
                "baseline_status": ["ready"] * len(scores),
                "eligible_for_recovery_analysis": [True] * len(scores),
                "deviation_status": ["calculated"] * len(scores),
                "hrv_deviation_score": scores,
                "rmssd_ms__abs_z": scores,
                "sdnn_ms__abs_z": scores,
            }
        )

    def test_population_baseline_weights_each_participant_once(self):
        result = estimate_population_hrv_baselines(self._personal_baselines())
        expected_rmssd = np.sqrt(20.0 * 80.0)
        self.assertAlmostEqual(result.loc[0, "rmssd_ms__centre_ms"], expected_rmssd)
        self.assertEqual(int(result.loc[0, "population_contributors"]), 2)

    def test_comparison_contains_four_strategies(self):
        personal = self._deviations([1.0, 2.0, 1.0])
        population = self._deviations([1.0, 1.0, 1.0])
        events = estimate_method_comparison_events(personal, population)
        strategies = events[["baseline_method", "required_consecutive_days"]].drop_duplicates()
        self.assertEqual(len(strategies), 4)

    def test_two_day_rule_cannot_recover_before_one_day_rule(self):
        personal = self._deviations([2.0, 1.0, 1.0])
        population = self._deviations([1.0, 1.0, 1.0])
        events = estimate_method_comparison_events(personal, population)
        audit = audit_method_comparison(events)
        self.assertFalse(audit["violation"].any())

    def test_paired_table_keeps_one_row_per_participant_posture(self):
        personal = self._deviations([2.0, 1.0, 1.0])
        population = self._deviations([1.0, 1.0, 1.0])
        events = estimate_method_comparison_events(personal, population)
        paired = build_method_comparison_paired_table(events)
        self.assertEqual(len(paired), 1)
        self.assertIn("personal__2_day__recovery_day", paired.columns)

    def test_population_expansion_preserves_personal_eligibility(self):
        personal = self._personal_baselines()
        personal.loc[1, "eligible_for_recovery_analysis"] = False
        population = estimate_population_hrv_baselines(personal)
        expanded = expand_population_baselines_to_common_risk_set(personal, population)
        self.assertEqual(len(expanded), 2)
        self.assertEqual(expanded["eligible_for_recovery_analysis"].tolist(), [True, False])
        self.assertEqual(expanded.loc[1, "baseline_status"], "common_risk_set_excluded")

    def test_summary_and_discordance_are_created(self):
        personal = self._deviations([2.0, 1.0, 1.0])
        population = self._deviations([1.0, 1.0, 1.0])
        events = estimate_method_comparison_events(personal, population)
        summary = summarize_method_comparison(events)
        discordance = summarize_method_discordance(events)
        self.assertEqual(len(summary), 12)
        self.assertIn("personal_vs_population", set(discordance["comparison"]))
        self.assertIn("one_day_vs_two_day", set(discordance["comparison"]))

    def test_audit_detects_common_risk_set_mismatch(self):
        events = estimate_method_comparison_events(
            self._deviations([1.0, 1.0]),
            self._deviations([1.0, 1.0]),
        )
        target = (
            events["baseline_method"].eq("population_average")
            & events["required_consecutive_days"].eq(1)
            & events["endpoint"].eq("hrv_composite")
        )
        events.loc[target, "survival_eligible"] = False
        audit = audit_method_comparison(events)
        self.assertTrue(audit["violation"].any())

    def test_report_states_audit_result(self):
        events = estimate_method_comparison_events(
            self._deviations([1.0, 1.0]),
            self._deviations([1.0, 1.0]),
        )
        audit = audit_method_comparison(events)
        report = render_method_comparison_report(events, audit)
        self.assertIn("Logical audit violations: **0**", report)


if __name__ == "__main__":
    unittest.main()
