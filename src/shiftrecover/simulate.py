"""Transparent synthetic data for method development and tests."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _wrap(hours):
    return np.asarray(hours) % 24.0


def simulate_shift_wearable_data(
    n_participants: int = 24,
    n_days: int = 28,
    seed: int = 20260914,
) -> pd.DataFrame:
    """Generate participant-day data with two night-work blocks.

    This is a software benchmark, not a simulated estimate of population truth.
    Each participant has an explicit latent recovery time constant.
    """

    if n_days < 28:
        raise ValueError("The demonstration schedule requires at least 28 days")
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2025-01-06")
    schedule = np.full(n_days, "off", dtype=object)
    schedule[6:8] = "day"
    schedule[10:13] = "night"
    schedule[20:23] = "night"

    records = []
    for i in range(n_participants):
        participant = f"P{i + 1:03d}"
        base_onset = _wrap(rng.normal(23.2, 0.65)).item()
        base_duration = rng.normal(7.35, 0.45)
        base_efficiency = rng.normal(88.0, 2.5)
        base_hr = rng.normal(62.0, 5.5)
        base_steps = rng.normal(8200.0, 1200.0)
        tau = rng.uniform(0.9, 2.8)
        last_night_index = None

        for day in range(n_days):
            shift = schedule[day]
            if shift == "night":
                last_night_index = day
                onset_shift = 8.7
                duration_shift = -1.8
                efficiency_shift = -7.0
                hr_shift = 6.0
                steps_shift = -1800.0
            elif last_night_index is not None:
                days_after = day - last_night_index
                decay = np.exp(-(days_after - 1) / tau)
                onset_shift = 5.2 * decay
                duration_shift = -1.35 * decay
                efficiency_shift = -5.0 * decay
                hr_shift = 4.5 * decay
                steps_shift = -1400.0 * decay
            else:
                onset_shift = duration_shift = efficiency_shift = hr_shift = steps_shift = 0.0

            if shift == "day":
                onset_shift -= 0.45
                duration_shift -= 0.35

            onset = _wrap(base_onset + onset_shift + rng.normal(0, 0.30)).item()
            duration = base_duration + duration_shift + rng.normal(0, 0.28)
            midpoint = _wrap(onset + duration / 2.0).item()
            wake = _wrap(onset + duration).item()
            record = {
                "participant_id": participant,
                "date": start + pd.Timedelta(days=day),
                "shift_type": shift,
                "baseline_eligible": bool(day < 6 and shift == "off"),
                "sleep_onset_hour": round(onset, 3),
                "wake_hour": round(wake, 3),
                "sleep_midpoint_hour": round(midpoint, 3),
                "total_sleep_hours": round(duration, 3),
                "sleep_efficiency": round(base_efficiency + efficiency_shift + rng.normal(0, 1.4), 3),
                "resting_hr": round(base_hr + hr_shift + rng.normal(0, 1.1), 3),
                "steps": round(max(500, base_steps + steps_shift + rng.normal(0, 650)), 0),
                "latent_recovery_tau": round(tau, 3),
            }
            records.append(record)
    return pd.DataFrame.from_records(records)

