import unittest

import numpy as np
import pandas as pd

from shiftrecover.bootstrap import (
    audit_bootstrap_intervals,
    cluster_bootstrap_recovery,
    kaplan_meier_statistics,
    render_bootstrap_report,
    summarize_bootstrap_intervals,
    summarize_recovery_uncertainty_points,
)


class BootstrapRecoveryTests(unittest.TestCase):
    def _events(self) -> pd.DataFrame:
        rows = []
        outcomes = {
            "P1": (1.0, True),
            "P2": (2.0, True),
            "P3": (3.0, False),
            "P4": (3.0, True),
        }
        for participant, (time, event) in outcomes.items():
            for method in ("personal", "population_average"):
                for days in (1, 2):
                    rows.append(
                        {
                            "participant_id": participant,
                            "posture": "standing",
                            "endpoint": "hrv_composite",
                            "baseline_method": method,
                            "required_consecutive_days": days,
                            "survival_eligible": True,
                            "event_observed": event,
                            "analysis_time_days": time,
                        }
                    )
        return pd.DataFrame(rows)

    def test_kaplan_meier_known_recovery_probability(self):
        result = kaplan_meier_statistics([1, 2, 2, 3], [True, True, False, True])
        self.assertAlmostEqual(result["km_recovery_probability_by_horizon"], 1.0)
        self.assertEqual(result["km_median_recovery_day"], 2.0)

    def test_restricted_mean_uses_survival_before_each_time(self):
        result = kaplan_meier_statistics([1, 3], [True, False], horizon_days=3)
        self.assertAlmostEqual(result["restricted_mean_time_days"], 2.0)

    def test_cluster_bootstrap_is_reproducible(self):
        first = cluster_bootstrap_recovery(self._events(), replicates=10, seed=42)
        second = cluster_bootstrap_recovery(self._events(), replicates=10, seed=42)
        pd.testing.assert_frame_equal(first, second)

    def test_bootstrap_retains_all_four_strategies(self):
        result = cluster_bootstrap_recovery(self._events(), replicates=5, seed=3)
        strategies = result[
            ["baseline_method", "required_consecutive_days"]
        ].drop_duplicates()
        self.assertEqual(len(strategies), 4)

    def test_probability_intervals_remain_in_unit_range(self):
        events = self._events()
        points = summarize_recovery_uncertainty_points(events)
        bootstrap = cluster_bootstrap_recovery(events, replicates=20, seed=7)
        intervals = summarize_bootstrap_intervals(points, bootstrap)
        audit = audit_bootstrap_intervals(intervals)
        probability_rows = audit["statistic"].str.contains("probability|proportion")
        self.assertFalse(audit.loc[probability_rows, "violation"].any())

    def test_rejects_too_few_replicates(self):
        with self.assertRaises(ValueError):
            cluster_bootstrap_recovery(self._events(), replicates=1)

    def test_empty_kaplan_meier_input_is_explicit(self):
        result = kaplan_meier_statistics([], [])
        self.assertTrue(np.isnan(result["km_median_recovery_day"]))

    def test_rejects_nonpositive_horizon(self):
        with self.assertRaises(ValueError):
            kaplan_meier_statistics([1], [True], horizon_days=0)

    def test_rejects_invalid_confidence_level(self):
        events = self._events()
        points = summarize_recovery_uncertainty_points(events)
        bootstrap = cluster_bootstrap_recovery(events, replicates=3, seed=1)
        with self.assertRaises(ValueError):
            summarize_bootstrap_intervals(points, bootstrap, confidence_level=1.0)

    def test_low_finite_median_fraction_is_warning_not_failure(self):
        events = self._events()
        points = summarize_recovery_uncertainty_points(events)
        bootstrap = cluster_bootstrap_recovery(events, replicates=10, seed=9)
        intervals = summarize_bootstrap_intervals(points, bootstrap)
        median = intervals["statistic"].eq("km_median_recovery_day")
        intervals.loc[median, "valid_replicate_fraction"] = 0.5
        audit = audit_bootstrap_intervals(intervals)
        self.assertTrue(audit.loc[median, "warning"].all())
        self.assertFalse(audit.loc[median, "violation"].any())

    def test_audit_detects_invalid_probability_bound(self):
        events = self._events()
        points = summarize_recovery_uncertainty_points(events)
        bootstrap = cluster_bootstrap_recovery(events, replicates=5, seed=2)
        intervals = summarize_bootstrap_intervals(points, bootstrap)
        target = intervals["statistic"].eq("crude_recovery_proportion")
        intervals.loc[target, "ci_upper"] = 1.1
        audit = audit_bootstrap_intervals(intervals)
        self.assertTrue(audit.loc[target, "violation"].all())

    def test_bootstrap_report_describes_cluster_resampling(self):
        events = self._events()
        points = summarize_recovery_uncertainty_points(events)
        bootstrap = cluster_bootstrap_recovery(events, replicates=10, seed=5)
        intervals = summarize_bootstrap_intervals(points, bootstrap)
        audit = audit_bootstrap_intervals(intervals)
        report = render_bootstrap_report(intervals, audit, seed=5)
        self.assertIn("Participant-cluster percentile bootstrap", report)
        self.assertIn("random seed 5", report)


if __name__ == "__main__":
    unittest.main()
