"""Transparent RR artefact handling and time-domain HRV calculation.

This module implements a deliberately simple, inspectable preprocessing rule:
physiologically implausible intervals and intervals differing markedly from a
centred local median are flagged, then replaced by linear interpolation across
beat index. It is not presented as an exact reimplementation of the source
authors' unavailable MATLAB settings.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .bourdillon import RR_MAX_MS, RR_MIN_MS


SESSION_COLUMNS = [
    "participant_id",
    "date",
    "date_raw",
    "date_was_corrected",
    "phase",
    "phase_order",
    "phase_day_observed",
    "phase_day_calendar",
    "recovery_day",
    "protocol",
    "protocol_segment_minutes",
    "posture",
    "posture_source",
    "posture_pair_complete",
]


def rmssd(nn_ms: np.ndarray | pd.Series) -> float:
    """Return root mean square of successive NN-interval differences."""

    values = np.asarray(nn_ms, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) < 2:
        return float("nan")
    return float(np.sqrt(np.mean(np.diff(values) ** 2)))


def sdnn(nn_ms: np.ndarray | pd.Series) -> float:
    """Return sample standard deviation of all NN intervals."""

    values = np.asarray(nn_ms, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) < 2:
        return float("nan")
    return float(np.std(values, ddof=1))


def flag_rr_artifacts(
    rr_ms: np.ndarray | pd.Series,
    *,
    local_window: int = 11,
    relative_threshold: float = 0.20,
    robust_z_threshold: float = 5.0,
    minimum_rr_ms: float = RR_MIN_MS,
    maximum_rr_ms: float = RR_MAX_MS,
) -> pd.DataFrame:
    """Flag range and local-median RR artefacts without changing values."""

    values = np.asarray(rr_ms, dtype=float)
    if values.ndim != 1:
        raise ValueError("RR intervals must be one-dimensional")
    if local_window < 3 or local_window % 2 == 0:
        raise ValueError("local_window must be an odd integer of at least 3")
    if relative_threshold <= 0:
        raise ValueError("relative_threshold must be positive")
    if robust_z_threshold <= 0:
        raise ValueError("robust_z_threshold must be positive")
    if not np.isfinite(values).all():
        raise ValueError("RR intervals must be finite")

    range_flag = (values < minimum_rr_ms) | (values > maximum_rr_ms)
    range_valid = pd.Series(values).mask(range_flag)
    minimum_periods = min(local_window, max(3, local_window // 3))
    local_median = range_valid.rolling(
        local_window, center=True, min_periods=minimum_periods
    ).median()
    local_median = local_median.bfill().ffill().to_numpy(dtype=float)
    residual = values - local_median
    relative_deviation = np.abs(residual) / local_median
    valid_residual = residual[~range_flag & np.isfinite(residual)]
    if len(valid_residual):
        residual_centre = float(np.median(valid_residual))
        robust_scale = float(
            1.4826 * np.median(np.abs(valid_residual - residual_centre))
        )
    else:
        robust_scale = float("nan")
    absolute_threshold = relative_threshold * local_median
    if np.isfinite(robust_scale):
        absolute_threshold = np.maximum(
            absolute_threshold, robust_z_threshold * robust_scale
        )
    local_flag = (np.abs(residual) > absolute_threshold) & ~range_flag
    artifact_flag = range_flag | local_flag
    reason = np.full(len(values), "", dtype=object)
    reason[range_flag & (values < minimum_rr_ms)] = "below_range"
    reason[range_flag & (values > maximum_rr_ms)] = "above_range"
    reason[local_flag] = "local_median_deviation"

    return pd.DataFrame(
        {
            "local_median_rr_ms": local_median,
            "relative_local_deviation": relative_deviation,
            "robust_residual_scale_ms": robust_scale,
            "artifact_flag": artifact_flag,
            "artifact_reason": reason,
        }
    )


def clean_rr_series(
    rr_ms: np.ndarray | pd.Series,
    *,
    local_window: int = 11,
    relative_threshold: float = 0.20,
    robust_z_threshold: float = 5.0,
    minimum_rr_ms: float = RR_MIN_MS,
    maximum_rr_ms: float = RR_MAX_MS,
) -> pd.DataFrame:
    """Flag artefacts and linearly interpolate them across beat index."""

    values = np.asarray(rr_ms, dtype=float)
    flags = flag_rr_artifacts(
        values,
        local_window=local_window,
        relative_threshold=relative_threshold,
        robust_z_threshold=robust_z_threshold,
        minimum_rr_ms=minimum_rr_ms,
        maximum_rr_ms=maximum_rr_ms,
    )
    valid = ~flags["artifact_flag"].to_numpy()
    nn_ms = np.full(len(values), np.nan, dtype=float)
    if valid.sum() >= 2:
        indices = np.arange(len(values))
        nn_ms = np.interp(indices, indices[valid], values[valid])

    result = flags.copy()
    result["nn_ms"] = nn_ms
    result["was_interpolated"] = result["artifact_flag"] & np.isfinite(nn_ms)
    result["correction_ms"] = nn_ms - values
    return result


def clean_bourdillon_rr(
    tidy: pd.DataFrame,
    *,
    local_window: int = 11,
    relative_threshold: float = 0.20,
    robust_z_threshold: float = 5.0,
    analysis_window_seconds: float = 180.0,
) -> pd.DataFrame:
    """Clean every participant-date-posture series and retain row provenance."""

    required = {
        "participant_id",
        "date",
        "phase",
        "posture",
        "posture_rr_index",
        "elapsed_seconds_in_posture",
        "rr_ms",
    }
    missing = sorted(required - set(tidy.columns))
    if missing:
        raise ValueError("Missing Bourdillon columns: " + ", ".join(missing))
    if analysis_window_seconds <= 0:
        raise ValueError("analysis_window_seconds must be positive")

    keys = ["participant_id", "date", "phase", "posture"]
    pieces: list[pd.DataFrame] = []
    for _, group in tidy.groupby(keys, sort=True, dropna=False):
        group = group.sort_values("posture_rr_index").copy().reset_index(drop=True)
        cleaned = clean_rr_series(
            group["rr_ms"],
            local_window=local_window,
            relative_threshold=relative_threshold,
            robust_z_threshold=robust_z_threshold,
        )
        for column in cleaned:
            group[column] = cleaned[column]
        group["in_analysis_window"] = (
            group["elapsed_seconds_in_posture"] <= analysis_window_seconds
        )
        group["analysis_window_seconds"] = analysis_window_seconds
        pieces.append(group)
    return pd.concat(pieces, ignore_index=True)


def calculate_session_hrv(
    cleaned: pd.DataFrame,
    *,
    minimum_intervals: int = 60,
    minimum_duration_seconds: float = 150.0,
    maximum_artifact_fraction: float = 0.05,
) -> pd.DataFrame:
    """Calculate one quality-controlled HRV row per date and posture."""

    if minimum_intervals < 2:
        raise ValueError("minimum_intervals must be at least 2")
    if minimum_duration_seconds <= 0:
        raise ValueError("minimum_duration_seconds must be positive")
    if not 0 <= maximum_artifact_fraction <= 1:
        raise ValueError("maximum_artifact_fraction must be between 0 and 1")

    rows: list[dict[str, object]] = []
    keys = ["participant_id", "date", "phase", "posture"]
    for _, group in cleaned.groupby(keys, sort=True, dropna=False):
        group = group.sort_values("posture_rr_index")
        analysis = group.loc[group["in_analysis_window"]].copy()
        first = group.iloc[0]
        nn_values = analysis["nn_ms"].to_numpy(dtype=float)
        n_intervals = len(analysis)
        n_artifacts = int(analysis["artifact_flag"].sum())
        artifact_fraction = n_artifacts / n_intervals if n_intervals else float("nan")
        analysis_duration = float(analysis["rr_ms"].sum() / 1000.0)

        failures: list[str] = []
        if n_intervals < minimum_intervals:
            failures.append("insufficient_intervals")
        if analysis_duration < minimum_duration_seconds:
            failures.append("insufficient_duration")
        if np.isfinite(artifact_fraction) and artifact_fraction > maximum_artifact_fraction:
            failures.append("excess_artifacts")
        if np.isfinite(nn_values).sum() < 2:
            failures.append("insufficient_nn")
        qc_pass = not failures

        row = {column: first.get(column, pd.NA) for column in SESSION_COLUMNS}
        row.update(
            {
                "source_file": first.get("source_file", pd.NA),
                "analysis_window_seconds": first["analysis_window_seconds"],
                "source_n_rr": len(group),
                "source_duration_seconds": float(group["rr_ms"].sum() / 1000.0),
                "analysis_n_rr": n_intervals,
                "analysis_duration_seconds": analysis_duration,
                "n_artifacts": n_artifacts,
                "artifact_fraction": artifact_fraction,
                "n_interpolated": int(analysis["was_interpolated"].sum()),
                "qc_pass": qc_pass,
                "qc_status": "pass" if qc_pass else ";".join(failures),
                "mean_nn_ms": float(np.nanmean(nn_values)) if qc_pass else float("nan"),
                "mean_hr_bpm": (
                    float(60_000.0 / np.nanmean(nn_values)) if qc_pass else float("nan")
                ),
                "rmssd_ms": rmssd(nn_values) if qc_pass else float("nan"),
                "sdnn_ms": sdnn(nn_values) if qc_pass else float("nan"),
            }
        )
        rows.append(row)
    return pd.DataFrame.from_records(rows).sort_values(
        ["participant_id", "date", "posture"]
    ).reset_index(drop=True)


def summarize_hrv_qc(metrics: pd.DataFrame) -> pd.DataFrame:
    """Summarize session QC and valid HRV values by phase and posture."""

    rows: list[dict[str, object]] = []
    for (phase, posture), group in metrics.groupby(["phase", "posture"], sort=True):
        passed = group.loc[group["qc_pass"]]
        rows.append(
            {
                "phase": phase,
                "posture": posture,
                "sessions": len(group),
                "sessions_qc_pass": int(group["qc_pass"].sum()),
                "sessions_qc_fail": int((~group["qc_pass"]).sum()),
                "median_artifact_fraction": group["artifact_fraction"].median(),
                "median_rmssd_ms_qc_pass": passed["rmssd_ms"].median(),
                "median_sdnn_ms_qc_pass": passed["sdnn_ms"].median(),
            }
        )
    return pd.DataFrame.from_records(rows)


def render_hrv_report(cleaned: pd.DataFrame, metrics: pd.DataFrame) -> str:
    """Render a compact Markdown report for one HRV processing run."""

    passed = int(metrics["qc_pass"].sum())
    artifacts = int(cleaned["artifact_flag"].sum())
    interpolated = int(cleaned["was_interpolated"].sum())
    window = float(cleaned["analysis_window_seconds"].iloc[0])
    return f"""# Bourdillon time-domain HRV processing report

## Processing result

- Participant-date-posture series: **{len(metrics)}**
- Series passing prespecified QC: **{passed}/{len(metrics)}**
- RR intervals flagged across full source segments: **{artifacts}**
- Flagged intervals replaced by linear interpolation: **{interpolated}**
- Standardized analysis window: first **{window:.0f} seconds** of each posture

RMSSD and sample SDNN are calculated separately for supine and standing NN
series. A series fails QC if its analysis window has fewer than 60 intervals,
less than 150 seconds, or more than 5% flagged intervals. Failed series remain
in the output with missing HRV metrics and an explicit `qc_status`.

The detector combines a 300-2000 ms range screen with a conservative local
median rule: a candidate must exceed both 20% of its local median and five
robust residual standard deviations. This transparent rule is a project
preprocessing choice, not an exact recreation of the source authors' unavailable
MATLAB settings.
"""
