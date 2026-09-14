import tempfile
import unittest
from pathlib import Path

import pandas as pd

from shiftrecover.plotting import (
    FIGURE_STEMS,
    generate_core_figures,
    kaplan_meier_curve,
    prepare_recovery_heatmap,
)


class CoreFigureTests(unittest.TestCase):
    def _hrv(self) -> pd.DataFrame:
        rows = []
        for participant in ("P1", "P2"):
            for phase, maximum in (
                ("baseline", 7),
                ("sleep_deprivation", 3),
                ("recovery", 7),
            ):
                for day in range(1, maximum + 1):
                    rows.append(
                        {
                            "participant_id": participant,
                            "phase": phase,
                            "phase_day_calendar": day,
                            "qc_pass": True,
                        }
                    )
        return pd.DataFrame(rows)

    def _deviations(self) -> pd.DataFrame:
        rows = []
        for participant, values in (
            ("P1", [2.0, 1.0, 1.0, 0.8, 0.7, 0.6, 0.5]),
            ("P2", [3.0, 2.5, 2.0, 1.8, 1.7, 1.6, 1.4]),
        ):
            for posture in ("standing", "supine"):
                for day, score in enumerate(values, start=1):
                    rows.append(
                        {
                            "participant_id": participant,
                            "posture": posture,
                            "recovery_day": day,
                            "hrv_deviation_score": score,
                            "eligible_for_recovery_analysis": True,
                        }
                    )
        return pd.DataFrame(rows)

    def _events(self) -> pd.DataFrame:
        rows = []
        for participant in ("P1", "P2"):
            for posture in ("standing", "supine"):
                for method in ("personal", "population_average"):
                    for days in (1, 2):
                        recovered = participant == "P1"
                        rows.append(
                            {
                                "participant_id": participant,
                                "posture": posture,
                                "endpoint": "hrv_composite",
                                "baseline_method": method,
                                "required_consecutive_days": days,
                                "survival_eligible": True,
                                "event_observed": recovered,
                                "recovery_day": 2.0 if recovered else None,
                                "analysis_time_days": 2.0 if recovered else 7.0,
                            }
                        )
        return pd.DataFrame(rows)

    def test_kaplan_meier_curve_is_monotone(self):
        curve = kaplan_meier_curve([1, 2, 3], [True, False, True])
        self.assertTrue(curve["recovery_probability"].is_monotonic_increasing)
        self.assertEqual(curve.iloc[0]["recovery_probability"], 0.0)

    def test_heatmap_has_seven_recovery_days(self):
        matrix, recovery = prepare_recovery_heatmap(
            self._deviations(), self._events()
        )
        self.assertEqual(matrix.shape, (4, 7))
        self.assertEqual(recovery.notna().sum(), 2)

    def test_generate_core_figures_writes_png_and_svg(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            generate_core_figures(
                self._hrv(),
                self._deviations(),
                self._events(),
                output_dir,
            )
            for stem in FIGURE_STEMS:
                self.assertGreater((output_dir / f"{stem}.png").stat().st_size, 1000)
                self.assertGreater((output_dir / f"{stem}.svg").stat().st_size, 1000)
            self.assertTrue((output_dir / "FIGURE_GUIDE.md").exists())


if __name__ == "__main__":
    unittest.main()
