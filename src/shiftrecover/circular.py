"""Utilities for clock-time variables represented as decimal hours."""

from __future__ import annotations

import numpy as np


def signed_clock_difference(hours, reference):
    """Return the shortest signed difference in hours, in [-12, 12)."""

    values = np.asarray(hours, dtype=float)
    return (values - float(reference) + 12.0) % 24.0 - 12.0


def circular_mean_hours(hours) -> float:
    """Return the circular mean of non-missing decimal clock hours."""

    values = np.asarray(hours, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return float("nan")
    angles = values / 24.0 * 2.0 * np.pi
    mean_angle = np.arctan2(np.sin(angles).mean(), np.cos(angles).mean())
    return float((mean_angle % (2.0 * np.pi)) * 24.0 / (2.0 * np.pi))

