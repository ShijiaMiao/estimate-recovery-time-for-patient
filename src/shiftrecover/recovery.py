"""Daily deviation scoring and recovery-event estimation."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from .circular import signed_clock_difference


def add_deviation_scores(
    daily: pd.DataFrame,
    baselines: pd.DataFrame,
    feature_types: Mapping[str, str],
    *,
    participant_col: str = "participant_id",
    minimum_features: int = 3,
    cap_z: float = 8.0,
) -> pd.DataFrame:
    """Add feature-level absolute deviations and an RMS composite score."""

    merged = daily.merge(baselines, on=participant_col, how="left", validate="many_to_one")
    z_columns: list[str] = []
    for feature, kind in feature_types.items():
        centre = merged[f"{feature}__centre"].to_numpy(float)
        scale = merged[f"{feature}__scale"].to_numpy(float)
        values = pd.to_numeric(merged[feature], errors="coerce").to_numpy(float)
        if kind == "circular":
            raw_difference = (values - centre + 12.0) % 24.0 - 12.0
        elif kind == "linear":
            raw_difference = values - centre
        else:
            raise ValueError(f"Unknown feature type for {feature}: {kind}")
        z = np.abs(raw_difference / scale)
        z[~np.isfinite(z)] = np.nan
        name = f"{feature}__abs_z"
        merged[name] = np.minimum(z, cap_z)
        z_columns.append(name)

    matrix = merged[z_columns].to_numpy(float)
    counts = np.isfinite(matrix).sum(axis=1)
    with np.errstate(invalid="ignore"):
        score = np.sqrt(np.nanmean(np.square(matrix), axis=1))
    score[counts < minimum_features] = np.nan
    merged["available_feature_count"] = counts
    merged["recovery_score"] = score
    return merged


def _night_blocks(frame: pd.DataFrame, date_col: str, shift_col: str, target_shift: str):
    target = frame.loc[frame[shift_col].eq(target_shift), [date_col]].copy()
    if target.empty:
        return []
    target = target.sort_values(date_col)
    dates = target[date_col].tolist()
    blocks: list[tuple[pd.Timestamp, pd.Timestamp, int]] = []
    start = previous = dates[0]
    length = 1
    for current in dates[1:]:
        if (current - previous).days == 1:
            length += 1
        else:
            blocks.append((start, previous, length))
            start, length = current, 1
        previous = current
    blocks.append((start, previous, length))
    return blocks


def estimate_recovery_events(
    scored_daily: pd.DataFrame,
    *,
    participant_col: str = "participant_id",
    date_col: str = "date",
    shift_col: str = "shift_type",
    target_shift: str = "night",
    recovery_shift: str = "off",
    threshold: float = 1.0,
    consecutive_days: int = 2,
) -> pd.DataFrame:
    """Estimate recovery after each target-shift block.

    Follow-up uses consecutive off-duty calendar days and stops when another
    work day begins. Recovery is the first day of the required run below the
    threshold. Events without a demonstrated run are right-censored.
    """

    data = scored_daily.copy()
    data[date_col] = pd.to_datetime(data[date_col]).dt.normalize()
    output: list[dict[str, object]] = []

    for participant, frame in data.groupby(participant_col, sort=True):
        frame = frame.sort_values(date_col).reset_index(drop=True)
        for number, (start, end, block_length) in enumerate(
            _night_blocks(frame, date_col, shift_col, target_shift), start=1
        ):
            after = frame.loc[frame[date_col] > end].copy()
            candidates = []
            expected = end + pd.Timedelta(days=1)
            for row in after.itertuples(index=False):
                row_date = getattr(row, date_col)
                row_shift = getattr(row, shift_col)
                if row_date != expected or row_shift != recovery_shift:
                    break
                candidates.append(row)
                expected += pd.Timedelta(days=1)

            recovered_day: int | None = None
            run = 0
            run_start = 0
            for day_number, row in enumerate(candidates, start=1):
                score = getattr(row, "recovery_score")
                if pd.notna(score) and float(score) <= threshold:
                    if run == 0:
                        run_start = day_number
                    run += 1
                    if run >= consecutive_days:
                        recovered_day = run_start
                        break
                else:
                    run = 0

            followup_days = len(candidates)
            output.append(
                {
                    participant_col: participant,
                    "block_number": number,
                    "shift_type": target_shift,
                    "block_start": start,
                    "block_end": end,
                    "block_length": block_length,
                    "followup_off_days": followup_days,
                    "recovery_days": recovered_day,
                    "recovered": recovered_day is not None,
                    "right_censored": recovered_day is None,
                    "threshold": threshold,
                    "required_consecutive_days": consecutive_days,
                }
            )
    return pd.DataFrame.from_records(output)

