"""Participant-cluster bootstrap uncertainty for recovery outcomes."""

from __future__ import annotations

import numpy as np
import pandas as pd


STRATUM_COLUMNS = [
    "baseline_method",
    "required_consecutive_days",
    "endpoint",
    "posture",
]

STATISTIC_COLUMNS = [
    "crude_recovery_proportion",
    "km_recovery_probability_by_horizon",
    "km_median_recovery_day",
    "restricted_mean_time_days",
]


def _as_bool(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values.dtype):
        return values.fillna(False).astype(bool)
    return values.astype("string").str.lower().eq("true").fillna(False)


def _validate_events(events: pd.DataFrame) -> pd.DataFrame:
    required = {
        "participant_id",
        "posture",
        "endpoint",
        "baseline_method",
        "required_consecutive_days",
        "survival_eligible",
        "event_observed",
        "analysis_time_days",
    }
    missing = sorted(required - set(events.columns))
    if missing:
        raise ValueError("Missing recovery-event columns: " + ", ".join(missing))
    data = events.copy()
    data["survival_eligible"] = _as_bool(data["survival_eligible"])
    data["event_observed"] = _as_bool(data["event_observed"])
    data["analysis_time_days"] = pd.to_numeric(
        data["analysis_time_days"], errors="coerce"
    )
    return data


def kaplan_meier_statistics(
    analysis_time_days: pd.Series | np.ndarray,
    event_observed: pd.Series | np.ndarray,
    *,
    horizon_days: float = 7.0,
) -> dict[str, float]:
    """Calculate recovery probability, median time and restricted mean time."""

    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive")
    time = np.asarray(analysis_time_days, dtype=float)
    event = np.asarray(event_observed, dtype=bool)
    valid = np.isfinite(time) & (time > 0)
    time = time[valid]
    event = event[valid]
    if len(time) == 0:
        return {
            "km_recovery_probability_by_horizon": float("nan"),
            "km_median_recovery_day": float("nan"),
            "restricted_mean_time_days": float("nan"),
        }

    survival = 1.0
    median = float("nan")
    restricted_mean = 0.0
    previous_time = 0.0
    for current_time in sorted(np.unique(time[time <= horizon_days])):
        restricted_mean += survival * (float(current_time) - previous_time)
        at_risk = int(np.sum(time >= current_time))
        deaths = int(np.sum((time == current_time) & event))
        if at_risk:
            survival *= 1.0 - deaths / at_risk
        if np.isnan(median) and survival <= 0.5:
            median = float(current_time)
        previous_time = float(current_time)
    restricted_mean += survival * (horizon_days - previous_time)
    return {
        "km_recovery_probability_by_horizon": 1.0 - survival,
        "km_median_recovery_day": median,
        "restricted_mean_time_days": restricted_mean,
    }


def _add_overall_posture(data: pd.DataFrame) -> pd.DataFrame:
    overall = data.copy()
    overall["posture"] = "all"
    return pd.concat([data, overall], ignore_index=True)


def summarize_recovery_uncertainty_points(
    events: pd.DataFrame,
    *,
    horizon_days: float = 7.0,
) -> pd.DataFrame:
    """Calculate point estimates for each strategy, endpoint and posture."""

    data = _add_overall_posture(_validate_events(events))
    records: list[dict[str, object]] = []
    for key, group in data.groupby(STRATUM_COLUMNS, sort=True):
        risk = group.loc[group["survival_eligible"]].copy()
        km = kaplan_meier_statistics(
            risk["analysis_time_days"],
            risk["event_observed"],
            horizon_days=horizon_days,
        )
        records.append(
            {
                **dict(zip(STRATUM_COLUMNS, key)),
                "eligible_series": len(risk),
                "eligible_participants": risk["participant_id"].nunique(),
                "events": int(risk["event_observed"].sum()),
                "right_censored": int((~risk["event_observed"]).sum()),
                "crude_recovery_proportion": (
                    float(risk["event_observed"].mean()) if len(risk) else float("nan")
                ),
                **km,
                "horizon_days": horizon_days,
            }
        )
    return pd.DataFrame.from_records(records)


def cluster_bootstrap_recovery(
    events: pd.DataFrame,
    *,
    replicates: int = 2000,
    seed: int = 20260914,
    horizon_days: float = 7.0,
) -> pd.DataFrame:
    """Resample participants with replacement and retain all their posture rows."""

    if replicates < 2:
        raise ValueError("replicates must be at least 2")
    data = _validate_events(events)
    participants = np.sort(
        data.loc[data["survival_eligible"], "participant_id"].dropna().unique()
    )
    if len(participants) < 2:
        raise ValueError("At least two eligible participants are required")
    participant_rows = {
        participant: data.loc[data["participant_id"].eq(participant)]
        for participant in participants
    }
    rng = np.random.default_rng(seed)
    pieces: list[pd.DataFrame] = []
    for replicate in range(1, replicates + 1):
        sampled = rng.choice(participants, size=len(participants), replace=True)
        sample = pd.concat(
            [participant_rows[participant] for participant in sampled],
            ignore_index=True,
        )
        estimates = summarize_recovery_uncertainty_points(
            sample,
            horizon_days=horizon_days,
        )
        estimates.insert(0, "replicate", replicate)
        estimates["sampled_clusters"] = len(sampled)
        estimates["unique_sampled_participants"] = len(np.unique(sampled))
        pieces.append(estimates)
    return pd.concat(pieces, ignore_index=True)


def summarize_bootstrap_intervals(
    points: pd.DataFrame,
    bootstrap: pd.DataFrame,
    *,
    confidence_level: float = 0.95,
) -> pd.DataFrame:
    """Create long-form percentile intervals for all recovery statistics."""

    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must lie between 0 and 1")
    alpha = (1.0 - confidence_level) / 2.0
    records: list[dict[str, object]] = []
    point_index = points.set_index(STRATUM_COLUMNS)
    for key, group in bootstrap.groupby(STRATUM_COLUMNS, sort=True):
        point = point_index.loc[key]
        total_replicates = group["replicate"].nunique()
        for statistic in STATISTIC_COLUMNS:
            values = pd.to_numeric(group[statistic], errors="coerce").dropna()
            records.append(
                {
                    **dict(zip(STRATUM_COLUMNS, key)),
                    "statistic": statistic,
                    "point_estimate": float(point[statistic]),
                    "bootstrap_standard_error": float(values.std(ddof=1)),
                    "ci_lower": float(values.quantile(alpha)),
                    "ci_upper": float(values.quantile(1.0 - alpha)),
                    "confidence_level": confidence_level,
                    "valid_replicates": len(values),
                    "requested_replicates": total_replicates,
                    "valid_replicate_fraction": len(values) / total_replicates,
                }
            )
    return pd.DataFrame.from_records(records)


def audit_bootstrap_intervals(intervals: pd.DataFrame) -> pd.DataFrame:
    """Flag malformed intervals and low finite-replicate coverage."""

    audit = intervals[STRATUM_COLUMNS + ["statistic"]].copy()
    audit["bounds_order_violation"] = intervals["ci_lower"] > intervals["ci_upper"]
    probability = intervals["statistic"].isin(
        ["crude_recovery_proportion", "km_recovery_probability_by_horizon"]
    )
    audit["probability_bounds_violation"] = probability & (
        intervals["ci_lower"].lt(0) | intervals["ci_upper"].gt(1)
    )
    audit["low_valid_replicate_fraction"] = intervals[
        "valid_replicate_fraction"
    ].lt(0.90)
    audit["violation"] = audit[
        [
            "bounds_order_violation",
            "probability_bounds_violation",
        ]
    ].any(axis=1)
    audit["warning"] = audit["low_valid_replicate_fraction"]
    return audit


def render_bootstrap_report(
    intervals: pd.DataFrame,
    audit: pd.DataFrame,
    *,
    seed: int,
) -> str:
    """Render four-strategy composite results with bootstrap intervals."""

    selected = intervals.loc[
        intervals["endpoint"].eq("hrv_composite")
        & intervals["posture"].eq("all")
        & intervals["statistic"].isin(
            ["km_recovery_probability_by_horizon", "km_median_recovery_day"]
        )
    ]
    wide = selected.pivot(
        index=["baseline_method", "required_consecutive_days"],
        columns="statistic",
        values=[
            "point_estimate",
            "ci_lower",
            "ci_upper",
            "valid_replicates",
            "requested_replicates",
        ],
    )
    lines = []
    for (method, days), row in wide.sort_index().iterrows():
        probability = row[("point_estimate", "km_recovery_probability_by_horizon")]
        probability_lower = row[("ci_lower", "km_recovery_probability_by_horizon")]
        probability_upper = row[("ci_upper", "km_recovery_probability_by_horizon")]
        median = row[("point_estimate", "km_median_recovery_day")]
        median_lower = row[("ci_lower", "km_median_recovery_day")]
        median_upper = row[("ci_upper", "km_median_recovery_day")]
        median_valid = int(row[("valid_replicates", "km_median_recovery_day")])
        requested = int(row[("requested_replicates", "km_median_recovery_day")])
        median_text = (
            f"{median:.1f} ({median_lower:.1f}–{median_upper:.1f}); "
            f"{median_valid}/{requested} finite"
            if np.isfinite(median)
            else "not reached"
        )
        lines.append(
            f"| {method} | {days} | {probability:.3f} "
            f"({probability_lower:.3f}–{probability_upper:.3f}) | {median_text} |"
        )
    violations = int(audit["violation"].sum())
    warnings = int(audit["warning"].sum())
    replicates = int(intervals["requested_replicates"].max())
    return f"""# Bourdillon recovery uncertainty

Participant-cluster percentile bootstrap with {replicates:,} replicates,
random seed {seed}, and a 7-day horizon. Standing and supine observations from
the same participant are resampled together.

| Baseline | Consecutive days | KM recovery by day 7, 95% CI | KM median day, 95% CI |
|---|---:|---:|---:|
{chr(10).join(lines)}

Bootstrap audit violations: **{violations}**; finite-replicate warnings:
**{warnings}**. A warning means that the KM median was not reached in more than
10% of resamples; its percentile interval is therefore conditional on finite
medians. Intervals quantify sampling
uncertainty in this dataset; they do not establish a clinically valid recovery
threshold or generalize beyond the study population.
"""
