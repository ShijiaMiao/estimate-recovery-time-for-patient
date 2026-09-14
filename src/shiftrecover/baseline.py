"""Robust participant-specific baseline estimation."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from .circular import circular_mean_hours, signed_clock_difference


def _robust_scale(values: np.ndarray, minimum: float) -> float:
    values = values[np.isfinite(values)]
    if values.size < 2:
        return float(minimum)
    centre = np.median(values)
    mad_scale = 1.4826 * np.median(np.abs(values - centre))
    if not np.isfinite(mad_scale) or mad_scale < minimum:
        q25, q75 = np.quantile(values, [0.25, 0.75])
        mad_scale = (q75 - q25) / 1.349
    return float(max(mad_scale, minimum))


def estimate_personal_baselines(
    daily: pd.DataFrame,
    feature_types: Mapping[str, str],
    *,
    participant_col: str = "participant_id",
    baseline_col: str = "baseline_eligible",
    min_days: int = 4,
    minimum_scales: Mapping[str, float] | None = None,
) -> pd.DataFrame:
    """Estimate a robust centre and scale for each participant and feature.

    ``feature_types`` maps column names to either ``"linear"`` or
    ``"circular"``. Circular variables must be decimal local-clock hours.
    """

    minimum_scales = dict(minimum_scales or {})
    missing = {participant_col, baseline_col, *feature_types} - set(daily.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    records: list[dict[str, float | str | int | bool]] = []
    for participant, frame in daily.groupby(participant_col, sort=True):
        base = frame.loc[frame[baseline_col].fillna(False).astype(bool)]
        record: dict[str, float | str | int | bool] = {
            participant_col: participant,
            "baseline_days": int(len(base)),
            "baseline_sufficient": bool(len(base) >= min_days),
        }
        for feature, kind in feature_types.items():
            values = pd.to_numeric(base[feature], errors="coerce").to_numpy(float)
            values = values[np.isfinite(values)]
            minimum = float(minimum_scales.get(feature, 0.25))
            if values.size < min_days:
                centre = scale = float("nan")
            elif kind == "circular":
                centre = circular_mean_hours(values)
                deviations = signed_clock_difference(values, centre)
                scale = _robust_scale(deviations, minimum)
            elif kind == "linear":
                centre = float(np.median(values))
                scale = _robust_scale(values, minimum)
            else:
                raise ValueError(f"Unknown feature type for {feature}: {kind}")
            record[f"{feature}__centre"] = centre
            record[f"{feature}__scale"] = scale
            record[f"{feature}__n"] = int(values.size)
        records.append(record)
    return pd.DataFrame.from_records(records)


def audit_hrv_baseline_observations(
    metrics: pd.DataFrame,
    *,
    metric_columns: tuple[str, ...] = ("rmssd_ms", "sdnn_ms"),
) -> pd.DataFrame:
    """Label every baseline posture series as eligible or explain its exclusion."""

    required = {"phase", "qc_pass", *metric_columns}
    missing = sorted(required - set(metrics.columns))
    if missing:
        raise ValueError("Missing HRV baseline columns: " + ", ".join(missing))

    baseline = metrics.loc[metrics["phase"].eq("baseline")].copy()
    finite_positive = np.ones(len(baseline), dtype=bool)
    for metric in metric_columns:
        values = pd.to_numeric(baseline[metric], errors="coerce").to_numpy(float)
        finite_positive &= np.isfinite(values) & (values > 0)
    qc_pass = baseline["qc_pass"].fillna(False).astype(bool).to_numpy()
    baseline["baseline_eligible"] = qc_pass & finite_positive
    baseline["baseline_exclusion_reason"] = np.select(
        [~qc_pass, qc_pass & ~finite_positive],
        ["session_qc_failed", "missing_or_nonpositive_hrv"],
        default="eligible",
    )
    return baseline.reset_index(drop=True)


def estimate_personal_hrv_baselines(
    metrics: pd.DataFrame,
    *,
    metric_columns: tuple[str, ...] = ("rmssd_ms", "sdnn_ms"),
    min_days: int = 4,
    minimum_log_scale: float = 0.05,
    range_multiplier: float = 1.5,
) -> pd.DataFrame:
    """Estimate robust log-scale HRV baselines by participant and posture.

    Centres and scales are estimated from QC-passing baseline dates. Normal
    ranges are operational project ranges, not clinical reference intervals.
    """

    required = {"participant_id", "date", "phase", "posture", "qc_pass", *metric_columns}
    missing = sorted(required - set(metrics.columns))
    if missing:
        raise ValueError("Missing HRV baseline columns: " + ", ".join(missing))
    if min_days < 2:
        raise ValueError("min_days must be at least 2")
    if minimum_log_scale <= 0:
        raise ValueError("minimum_log_scale must be positive")
    if range_multiplier <= 0:
        raise ValueError("range_multiplier must be positive")

    audited = audit_hrv_baseline_observations(metrics, metric_columns=metric_columns)
    records: list[dict[str, object]] = []
    keys = ["participant_id", "posture"]
    for key, all_rows in metrics.groupby(keys, sort=True, dropna=False):
        participant_id, posture = key
        eligible = audited.loc[
            audited["participant_id"].eq(participant_id)
            & audited["posture"].eq(posture)
            & audited["baseline_eligible"]
        ]
        postbaseline = all_rows.loc[
            ~all_rows["phase"].eq("baseline")
            & all_rows["qc_pass"].fillna(False).astype(bool)
        ]
        record: dict[str, object] = {
            "participant_id": participant_id,
            "posture": posture,
            "baseline_candidate_days": int(
                all_rows.loc[all_rows["phase"].eq("baseline"), "date"].nunique()
            ),
            "baseline_qc_eligible_days": int(eligible["date"].nunique()),
            "postbaseline_qc_days": int(postbaseline["date"].nunique()),
            "minimum_required_days": min_days,
            "range_multiplier": range_multiplier,
        }
        metric_sufficient: list[bool] = []
        for metric in metric_columns:
            values = pd.to_numeric(eligible[metric], errors="coerce").to_numpy(float)
            values = values[np.isfinite(values) & (values > 0)]
            sufficient = len(values) >= min_days
            metric_sufficient.append(sufficient)
            if sufficient:
                log_values = np.log(values)
                centre_log = float(np.median(log_values))
                raw_mad_scale = float(
                    1.4826 * np.median(np.abs(log_values - centre_log))
                )
                scale_log = _robust_scale(log_values, minimum_log_scale)
                centre_ms = float(np.exp(centre_log))
                lower_ms = float(np.exp(centre_log - range_multiplier * scale_log))
                upper_ms = float(np.exp(centre_log + range_multiplier * scale_log))
                floor_applied = not np.isfinite(raw_mad_scale) or raw_mad_scale < minimum_log_scale
            else:
                centre_log = scale_log = centre_ms = lower_ms = upper_ms = float("nan")
                floor_applied = False
            record[f"{metric}__n"] = len(values)
            record[f"{metric}__centre_log"] = centre_log
            record[f"{metric}__scale_log"] = scale_log
            record[f"{metric}__centre_ms"] = centre_ms
            record[f"{metric}__normal_lower_ms"] = lower_ms
            record[f"{metric}__normal_upper_ms"] = upper_ms
            record[f"{metric}__scale_floor_applied"] = floor_applied

        baseline_sufficient = all(metric_sufficient)
        has_postbaseline = record["postbaseline_qc_days"] > 0
        record["baseline_sufficient"] = baseline_sufficient
        record["eligible_for_recovery_analysis"] = baseline_sufficient and has_postbaseline
        if not baseline_sufficient:
            record["baseline_status"] = "insufficient_baseline"
        elif not has_postbaseline:
            record["baseline_status"] = "no_postbaseline_data"
        else:
            record["baseline_status"] = "ready"
        records.append(record)
    return pd.DataFrame.from_records(records)


def render_hrv_baseline_report(
    baselines: pd.DataFrame, observations: pd.DataFrame
) -> str:
    """Render a compact run-specific Markdown audit of HRV baselines."""

    sufficient = int(baselines["baseline_sufficient"].sum())
    ready = int(baselines["eligible_for_recovery_analysis"].sum())
    eligible_days = int(observations["baseline_eligible"].sum())
    failed_days = int((~observations["baseline_eligible"]).sum())
    insufficient = baselines.loc[
        baselines["baseline_status"].eq("insufficient_baseline"),
        ["participant_id", "posture", "baseline_qc_eligible_days"],
    ]
    insufficient_text = (
        ", ".join(
            f"{row.participant_id}/{row.posture} ({row.baseline_qc_eligible_days} days)"
            for row in insufficient.itertuples(index=False)
        )
        or "None"
    )
    return f"""# Bourdillon personal HRV baseline report

## Coverage

- Participant-posture combinations: **{len(baselines)}**
- Combinations with at least four eligible baseline days: **{sufficient}**
- Combinations ready for subsequent recovery analysis: **{ready}**
- Eligible baseline participant-date-posture observations: **{eligible_days}**
- Baseline observations excluded by session QC: **{failed_days}**
- Insufficient combinations: **{insufficient_text}**

## Definition

For RMSSD and SDNN separately, the personal centre is the median on the natural
log scale and variability is 1.4826 x MAD with a minimum scale of 0.05 log
units. The primary operational normal range is centre +/- 1.5 robust scales,
back-transformed to milliseconds. These are individualized method thresholds,
not population clinical reference intervals.
"""
