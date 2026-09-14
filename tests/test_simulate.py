import unittest

import pandas as pd

from shiftrecover.simulate import simulate_shift_wearable_data


class SyntheticWearableDataTests(unittest.TestCase):
    def test_simulation_is_reproducible(self):
        first = simulate_shift_wearable_data(n_participants=3, seed=42)
        second = simulate_shift_wearable_data(n_participants=3, seed=42)
        pd.testing.assert_frame_equal(first, second)

    def test_simulation_has_expected_participant_day_structure(self):
        data = simulate_shift_wearable_data(n_participants=4, n_days=28, seed=1)
        self.assertEqual(len(data), 112)
        self.assertEqual(data["participant_id"].nunique(), 4)
        self.assertTrue(data.groupby("participant_id")["date"].nunique().eq(28).all())
        self.assertEqual(int(data["baseline_eligible"].sum()), 24)

    def test_schedule_contains_two_night_blocks(self):
        data = simulate_shift_wearable_data(n_participants=1, seed=4)
        night_days = data.loc[data["shift_type"].eq("night"), "date"].dt.day.tolist()
        self.assertEqual(night_days, [16, 17, 18, 26, 27, 28])

    def test_rejects_schedule_shorter_than_28_days(self):
        with self.assertRaises(ValueError):
            simulate_shift_wearable_data(n_days=27)
