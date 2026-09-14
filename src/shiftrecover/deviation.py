"""Daily HRV deviations from participant- and posture-specific baselines."""

from __future__ import annotations

import numpy as np
import pandas as pd


DEFAULT_HRV_METRICS = ("rmssd_ms", "sdnn_ms")


def _as_nullable_boolean(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values.dtype):
        return values.astype("boolean")
    normalized = values.astype("string").str.lower()
    return normalized.map({"true": True, "false": False}).astype("boolean")


def build_hrv_recovery_deviations(
    metrics: pd.DataFrame,
    baselines: pd.DataFrame,
    *,
    metric_columns: tuple[str, ...] = DEFAULT_HRV_METRICS,
    max_recovery_day: int = 7,
) -> pd.DataFrame:
    """Build a complete recovery-day grid and calculate personal deviations."""

    metric_required = {
        "participant_id",
        "date",
        "phase",
        "posture",
        "recovery_day",
        "qc_pass",
        *metric_columns,
    }
    baseline_required = {
        "participant_id",
        "posture",
        "baseline_status",
        "eligible_for_recovery_analysis",
        "range_multiplier",
    }
    for metric in metric_columns:
        baseline_required.update(
            {
                f"{metric}__centre_log",
                f"{metric}__scale_log",
                f"{metric}__centre_ms",
                f"{metric}__normal_lower_ms",
                f"{metric}__normal_upper_ms",
            }
        )
    missing_metrics = sorted(metric_required - set(metrics.columns))
    missing_baselines = sorted(baseline_required - set(baselines.columns))
    if missing_metrics:
        raise ValueError("Missing daily HRV columns: " + ", ".join(missing_metrics))
    if missing_baselines:
        raise ValueError("Missing personal baseline columns: " + ", ".join(missing_baselines))
    if max_recovery_day < 1:
        raise ValueError("max_recovery_day must be positive")

    baseline_data = baselines.copy()
    baseline_data["eligible_for_recovery_analysis"] = _as_nullable_boolean(
        baseline_data["eligible_for_recovery_analysis"]
    ).fillna(False)
    recovery_days = pd.DataFrame({"recovery_day": range(1, max_recovery_day + 1)})
    grid = baseline_data.merge(recovery_days, how="cross")

    recovery = metrics.loc[metrics["phase"].eq("recovery")].copy()
    recovery["date"] = pd.to_datetime(recovery["date"]).dt.normalize()
    recovery["recovery_day"] = pd.to_numeric(
        recovery["recovery_day"], errors="coerce"
    ).astype("Int64")
    recovery = recovery.loc[recovery["recovery_day"].between(1, max_recovery_day)]
    duplicate = recovery.duplicated(["participant_id", "posture", "recovery_day"])
    if duplicate.any():
        raise ValueError("Duplicate participant-posture-recovery-day HRV rows")

    anchor_candidates = recovery[["participant_id", "date", "recovery_day"]].dropna()
    anchor_candidates["recovery_anchor"] = anchor_candidates["date"] - pd.to_timedelta(
        anchor_candidates["recovery_day"] - 1, unit="D"
    )
    anchors = anchor_candidates.groupby("participant_id", as_index=False)[
        "recovery_anchor"
    ].min()
    grid = grid.merge(anchors, on="participant_id", how="left", validate="many_to_one")
    grid["expected_date"] = grid["recovery_anchor"] + pd.to_timedelta(
        grid["recovery_day"] - 1, unit="D"
    )
    grid = grid.drop(columns="recovery_anchor")

    metric_metadata = [
        "participant_id",
        "posture",
        "recovery_day",
        "date",
        "qc_pass",
        "qc_status",
        "protocol",
        "posture_source",
        "artifact_fraction",
        *metric_columns,
    ]
    available_metadata = [column for column in metric_metadata if column in recovery]
    result = grid.merge(
        recovery[available_metadata],
        on=["participant_id", "posture", "recovery_day"],
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    result["observation_available"] = result.pop("_merge").eq("both")
    result["session_qc_pass"] = _as_nullable_boolean(result["qc_pass"])
    result = result.drop(columns="qc_pass")

    valid_metric_masks: list[np.ndarray] = []
    abs_z_columns: list[str] = []
    within_columns: list[str] = []
    analysis_eligible = result["eligible_for_recovery_analysis"].fillna(False).to_numpy(bool)
    session_pass = result["session_qc_pass"].fillna(False).to_numpy(bool)
    observed = result["observation_available"].to_numpy(bool)
    for metric in metric_columns:
        value = pd.to_numeric(result[metric], errors="coerce").to_numpy(float)
        centre_log = pd.to_numeric(
            result[f"{metric}__centre_log"], errors="coerce"
        ).to_numpy(float)
        scale_log = pd.to_numeric(
            result[f"{metric}__scale_log"], errors="coerce"
        ).to_numpy(float)
        valid = (
            analysis_eligible
            & session_pass
            & observed
            & np.isfinite(value)
            & (value > 0)
            & np.isfinite(centre_log)
            & np.isfinite(scale_log)
            & (scale_log > 0)
        )
        signed_z = np.full(len(result), np.nan)
        log_ratio = np.full(len(result), np.nan)
        percent_difference = np.full(len(result), np.nan)
        log_ratio[valid] = np.log(value[valid]) - centre_log[valid]
        signed_z[valid] = log_ratio[valid] / scale_log[valid]
        centre_ms = pd.to_numeric(
            result[f"{metric}__centre_ms"], errors="coerce"
        ).to_numpy(float)
        percent_difference[valid] = 100 * (value[valid] / centre_ms[valid] - 1)

        abs_z_column = f"{metric}__abs_z"
        within_column = f"{metric}__within_personal_range"
        result[f"{metric}__log_ratio"] = log_ratio
        result[f"{metric}__percent_difference"] = percent_difference
        result[f"{metric}__signed_z"] = signed_z
        result[abs_z_column] = np.abs(signed_z)
        within = pd.Series(pd.NA, index=result.index, dtype="boolean")
        multiplier = pd.to_numeric(result["range_multiplier"], errors="coerce").to_numpy(float)
        within.loc[valid] = np.abs(signed_z[valid]) <= multiplier[valid]
        result[within_column] = within
        valid_metric_masks.append(valid)
        abs_z_columns.append(abs_z_column)
        within_columns.append(within_column)

    abs_z_matrix = result[abs_z_columns].to_numpy(float)
    available_count = np.isfinite(abs_z_matrix).sum(axis=1)
    result["available_metric_count"] = available_count
    result["hrv_deviation_score"] = np.nan
    complete_metrics = available_count == len(metric_columns)
    result.loc[complete_metrics, "hrv_deviation_score"] = np.sqrt(
        np.mean(np.square(abs_z_matrix[complete_metrics]), axis=1)
    )
    within_all = pd.Series(pd.NA, index=result.index, dtype="boolean")
    if complete_metrics.any():
        within_matrix = np.column_stack(
            [result[column].fillna(False).to_numpy(bool) for column in within_columns]
        )
        within_all.loc[complete_metrics] = within_matrix[complete_metrics].all(axis=1)
    result["all_hrv_metrics_within_personal_range"] = within_all

    status = np.full(len(result), "calculated", dtype=object)
    baseline_status = result["baseline_status"].astype(str).to_numpy()
    status[~analysis_eligible] = baseline_status[~analysis_eligible]
    status[analysis_eligible & ~observed] = "missing_observation"
    status[analysis_eligible & observed & ~session_pass] = "session_qc_failed"
    incomplete = analysis_eligible & observed & session_pass & ~complete_metrics
    status[incomplete] = "missing_or_invalid_metric"
    result["deviation_status"] = status

    ordered = [
        "participant_id",
        "posture",
        "recovery_day",
        "expected_date",
        "date",
        "baseline_status",
        "eligible_for_recovery_analysis",
        "observation_available",
        "session_qc_pass",
        "deviation_status",
    ]
    remainder = [column for column in result if column not in ordered]
    return result[ordered + remainder].sort_values(
        ["participant_id", "posture", "recovery_day"]
    ).reset_index(drop=True)


def summarize_recovery_deviations(deviations: pd.DataFrame) -> pd.DataFrame:
    """Summarize calculated daily deviations without filling missing days."""

    rows: list[dict[str, object]] = []
    for (day, posture), group in deviations.groupby(
        ["recovery_day", "posture"], sort=True
    ):
        calculated = group.loc[group["deviation_status"].eq("calculated")]
        within = calculated["all_hrv_metrics_within_personal_range"].dropna().astype(bool)
        rows.append(
            {
                "recovery_day": day,
                "posture": posture,
                "participant_posture_rows": len(group),
                "analysis_eligible": int(group["eligible_for_recovery_analysis"].sum()),
                "calculated": len(calculated),
                "missing_observation": int(
                    group["deviation_status"].eq("missing_observation").sum()
                ),
                "session_qc_failed": int(
                    group["deviation_status"].eq("session_qc_failed").sum()
                ),
                "baseline_unavailable": int(
                    (~group["eligible_for_recovery_analysis"].fillna(False)).sum()
                ),
                "median_rmssd_signed_z": calculated["rmssd_ms__signed_z"].median(),
                "median_sdnn_signed_z": calculated["sdnn_ms__signed_z"].median(),
                "median_hrv_deviation_score": calculated["hrv_deviation_score"].median(),
                "proportion_all_metrics_within_range": within.mean(),
            }
        )
    return pd.DataFrame.from_records(rows)


def render_recovery_deviation_report(
    deviations: pd.DataFrame, summary: pd.DataFrame
) -> str:
    """Render a compact Markdown audit report for daily deviations."""

    statuses = deviations["deviation_status"].value_counts()
    calculated = int(statuses.get("calculated", 0))
    missing = int(statuses.get("missing_observation", 0))
    qc_failed = int(statuses.get("session_qc_failed", 0))
    baseline_unavailable = int(
        deviations["deviation_status"].isin(
            ["insufficient_baseline", "no_postbaseline_data"]
        ).sum()
    )
    return f"""# Bourdillon recovery-day deviation report

## Coverage

- Complete participant-posture-day grid rows: **{len(deviations)}**
- Rows with calculated RMSSD and SDNN deviations: **{calculated}**
- Rows with no recording on that recovery day: **{missing}**
- Rows excluded because the observed session failed QC: **{qc_failed}**
- Rows unavailable because of baseline or follow-up status: **{baseline_unavailable}**
- Recovery days summarized: **{summary['recovery_day'].min()}-{summary['recovery_day'].max()}**

Signed deviations are calculated on the log scale relative to each person's
posture-specific robust baseline. Positive values indicate HRV above the
personal centre; negative values indicate HRV below it. The combined score is
the root mean square of the absolute RMSSD and SDNN deviations. Missing days are
retained and are never interpreted as recovered.
"""
