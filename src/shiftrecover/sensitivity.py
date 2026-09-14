"""Recovery-threshold sensitivity analysis and monotonicity auditing."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from .recovery_time import estimate_hrv_recovery_events


DEFAULT_THRESHOLDS = (0.75, 1.0, 1.5, 2.0)


def estimate_threshold_sensitivity(
    deviations: pd.DataFrame,
    *,
    thresholds: Iterable[float] = DEFAULT_THRESHOLDS,
    consecutive_days: int = 2,
    primary_threshold: float = 1.5,
) -> pd.DataFrame:
    """Repeat the same recovery analysis over prespecified score thresholds."""

    threshold_values = sorted(set(float(value) for value in thresholds))
    if len(threshold_values) < 3:
        raise ValueError("At least three distinct recovery thresholds are required")
    if any(value <= 0 for value in threshold_values):
        raise ValueError("Recovery thresholds must be positive")
    if consecutive_days < 1:
        raise ValueError("consecutive_days must be positive")

    pieces: list[pd.DataFrame] = []
    for threshold in threshold_values:
        events = estimate_hrv_recovery_events(
            deviations,
            threshold=threshold,
            consecutive_days=consecutive_days,
        )
        events["sensitivity_threshold"] = threshold
        events["is_primary_threshold"] = np.isclose(threshold, primary_threshold)
        pieces.append(events)
    return pd.concat(pieces, ignore_index=True).sort_values(
        ["endpoint", "participant_id", "posture", "sensitivity_threshold"]
    ).reset_index(drop=True)


def summarize_threshold_sensitivity(events: pd.DataFrame) -> pd.DataFrame:
    """Summarize recovery and censoring under every threshold."""

    rows: list[dict[str, object]] = []
    grouping = ["sensitivity_threshold", "endpoint", "posture"]
    for (threshold, endpoint, posture), group in events.groupby(grouping, sort=True):
        risk = group.loc[group["survival_eligible"]]
        recovered = risk.loc[risk["event_observed"]]
        rows.append(
            {
                "threshold": threshold,
                "endpoint": endpoint,
                "posture": posture,
                "eligible": len(risk),
                "recovered": len(recovered),
                "right_censored": int(risk["right_censored"].sum()),
                "recovery_proportion_observed": (
                    len(recovered) / len(risk) if len(risk) else float("nan")
                ),
                "median_recovery_day_among_recovered": recovered["recovery_day"].median(),
                "minimum_recovery_day": recovered["recovery_day"].min(),
                "maximum_recovery_day": recovered["recovery_day"].max(),
            }
        )
    return pd.DataFrame.from_records(rows)


def _threshold_suffix(threshold: float) -> str:
    return str(threshold).replace(".", "_")


def build_threshold_stability_table(
    events: pd.DataFrame,
    *,
    endpoint: str = "hrv_composite",
) -> pd.DataFrame:
    """Create one row per participant-posture with results across thresholds."""

    selected = events.loc[events["endpoint"].eq(endpoint)].copy()
    identifiers = ["participant_id", "posture", "baseline_status"]
    base = selected[identifiers].drop_duplicates().sort_values(identifiers[:2])
    result = base.reset_index(drop=True)
    for threshold in sorted(selected["sensitivity_threshold"].unique()):
        subset = selected.loc[selected["sensitivity_threshold"].eq(threshold)].copy()
        suffix = _threshold_suffix(float(threshold))
        columns = {
            "survival_eligible": f"threshold_{suffix}__survival_eligible",
            "event_observed": f"threshold_{suffix}__event_observed",
            "recovery_day": f"threshold_{suffix}__recovery_day",
            "right_censored": f"threshold_{suffix}__right_censored",
            "censor_day": f"threshold_{suffix}__censor_day",
            "analysis_time_days": f"threshold_{suffix}__analysis_time_days",
        }
        subset = subset[[*identifiers[:2], *columns]].rename(columns=columns)
        result = result.merge(
            subset,
            on=identifiers[:2],
            how="left",
            validate="one_to_one",
        )
    return result


def audit_threshold_monotonicity(events: pd.DataFrame) -> pd.DataFrame:
    """Check that relaxing a threshold never delays a demonstrated recovery."""

    rows: list[dict[str, object]] = []
    keys = ["participant_id", "posture", "endpoint"]
    for key, group in events.groupby(keys, sort=True, dropna=False):
        group = group.sort_values("sensitivity_threshold")
        records = list(group.itertuples(index=False))
        for strict, lenient in zip(records[:-1], records[1:], strict=True):
            strict_event = bool(strict.event_observed)
            lenient_event = bool(lenient.event_observed)
            violation = strict_event and (
                not lenient_event or float(lenient.recovery_day) > float(strict.recovery_day)
            )
            rows.append(
                {
                    "participant_id": key[0],
                    "posture": key[1],
                    "endpoint": key[2],
                    "strict_threshold": strict.sensitivity_threshold,
                    "lenient_threshold": lenient.sensitivity_threshold,
                    "strict_event_observed": strict_event,
                    "lenient_event_observed": lenient_event,
                    "strict_recovery_day": strict.recovery_day,
                    "lenient_recovery_day": lenient.recovery_day,
                    "monotonicity_violation": violation,
                }
            )
    return pd.DataFrame.from_records(rows)


def render_threshold_sensitivity_report(
    events: pd.DataFrame,
    monotonicity: pd.DataFrame,
) -> str:
    """Render a Markdown report focused on the composite endpoint."""

    primary = events.loc[events["endpoint"].eq("hrv_composite")]
    lines = []
    for threshold, group in primary.groupby("sensitivity_threshold", sort=True):
        risk = group.loc[group["survival_eligible"]]
        recovered = int(risk["event_observed"].sum())
        censored = int(risk["right_censored"].sum())
        lines.append(f"| {threshold:g} | {len(risk)} | {recovered} | {censored} |")
    table = "\n".join(lines)
    violations = int(monotonicity["monotonicity_violation"].sum())
    thresholds = ", ".join(
        f"{value:g}" for value in sorted(primary["sensitivity_threshold"].unique())
    )
    consecutive_days = int(primary["required_consecutive_days"].iloc[0])
    return f"""# Bourdillon recovery-threshold sensitivity report

All analyses use personal baselines, the same missing-data rules, and
**{consecutive_days} consecutive recovered days**. Only the recovery threshold
changes: **{thresholds}**.

| Threshold | Eligible | Recovered | Right-censored |
|---:|---:|---:|---:|
{table}

Monotonicity violations detected across all endpoints and postures: **{violations}**.
A more lenient threshold should never produce later recovery than a stricter
threshold for the same series. This audit guards against implementation errors;
it does not establish which threshold is clinically correct.
"""
