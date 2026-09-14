"""First recovery-time estimation with explicit right censoring."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd


DEFAULT_ENDPOINTS = {
    "hrv_composite": "hrv_deviation_score",
    "rmssd": "rmssd_ms__abs_z",
    "sdnn": "sdnn_ms__abs_z",
}


def _to_bool(value: object) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


def estimate_hrv_recovery_events(
    deviations: pd.DataFrame,
    *,
    endpoint_columns: Mapping[str, str] = DEFAULT_ENDPOINTS,
    threshold: float = 1.5,
    consecutive_days: int = 2,
) -> pd.DataFrame:
    """Estimate first stable recovery for each participant, posture, and endpoint.

    The event day is the first day in the qualifying run. A later day is kept as
    the confirmation day. Missing or failed-QC days break a qualifying run.
    """

    required = {
        "participant_id",
        "posture",
        "recovery_day",
        "expected_date",
        "baseline_status",
        "eligible_for_recovery_analysis",
        "deviation_status",
        *endpoint_columns.values(),
    }
    missing = sorted(required - set(deviations.columns))
    if missing:
        raise ValueError("Missing recovery deviation columns: " + ", ".join(missing))
    if threshold <= 0:
        raise ValueError("threshold must be positive")
    if consecutive_days < 1:
        raise ValueError("consecutive_days must be positive")

    rows: list[dict[str, object]] = []
    for (participant, posture), group in deviations.groupby(
        ["participant_id", "posture"], sort=True, dropna=False
    ):
        group = group.sort_values("recovery_day").reset_index(drop=True)
        first = group.iloc[0]
        eligible = _to_bool(first["eligible_for_recovery_analysis"])
        max_followup_day = int(group["recovery_day"].max())
        calculated = group["deviation_status"].eq("calculated")
        calculated_days = group.loc[calculated, "recovery_day"].astype(int)
        last_evaluable_day = int(calculated_days.max()) if len(calculated_days) else None
        first_evaluable_day = int(calculated_days.min()) if len(calculated_days) else None
        if len(calculated_days):
            span = set(range(first_evaluable_day, last_evaluable_day + 1))
            intermittent_missing = bool(span - set(calculated_days.tolist()))
            trailing_missing_days = max_followup_day - last_evaluable_day
        else:
            intermittent_missing = False
            trailing_missing_days = max_followup_day

        for endpoint, score_column in endpoint_columns.items():
            scores = pd.to_numeric(group[score_column], errors="coerce").to_numpy(float)
            evaluable = calculated.to_numpy() & np.isfinite(scores)
            first_below_day: int | None = None
            recovery_day: int | None = None
            confirmation_day: int | None = None
            score_at_recovery: float | None = None
            score_at_confirmation: float | None = None
            run_start: int | None = None
            run_start_score: float | None = None
            run_length = 0

            if eligible:
                for index, row in group.iterrows():
                    day = int(row["recovery_day"])
                    below = bool(evaluable[index] and scores[index] <= threshold)
                    if below and first_below_day is None:
                        first_below_day = day
                    if below:
                        if run_length == 0:
                            run_start = day
                            run_start_score = float(scores[index])
                        run_length += 1
                        if run_length >= consecutive_days:
                            recovery_day = run_start
                            confirmation_day = day
                            score_at_recovery = run_start_score
                            score_at_confirmation = float(scores[index])
                            break
                    else:
                        run_start = None
                        run_start_score = None
                        run_length = 0

            event_observed = recovery_day is not None
            endpoint_evaluable_days = int(evaluable.sum()) if eligible else 0
            survival_eligible = eligible and endpoint_evaluable_days > 0
            if not eligible:
                analysis_status = str(first["baseline_status"])
            elif not survival_eligible:
                analysis_status = "no_evaluable_followup"
            elif event_observed:
                analysis_status = "recovered"
            else:
                analysis_status = "right_censored"
            right_censored = survival_eligible and not event_observed
            censor_day = last_evaluable_day if right_censored else None
            analysis_time = recovery_day if event_observed else censor_day

            recovery_date = pd.NaT
            confirmation_date = pd.NaT
            if event_observed:
                recovery_date = group.loc[
                    group["recovery_day"].eq(recovery_day), "expected_date"
                ].iloc[0]
                confirmation_date = group.loc[
                    group["recovery_day"].eq(confirmation_day), "expected_date"
                ].iloc[0]

            rows.append(
                {
                    "participant_id": participant,
                    "posture": posture,
                    "endpoint": endpoint,
                    "score_column": score_column,
                    "baseline_status": first["baseline_status"],
                    "survival_eligible": survival_eligible,
                    "analysis_status": analysis_status,
                    "event_observed": event_observed,
                    "recovered": event_observed,
                    "right_censored": right_censored,
                    "recovery_day": recovery_day,
                    "confirmation_day": confirmation_day,
                    "recovery_date": recovery_date,
                    "confirmation_date": confirmation_date,
                    "censor_day": censor_day,
                    "analysis_time_days": analysis_time,
                    "first_below_threshold_day": first_below_day,
                    "score_at_recovery": score_at_recovery,
                    "score_at_confirmation": score_at_confirmation,
                    "threshold": threshold,
                    "required_consecutive_days": consecutive_days,
                    "planned_followup_days": max_followup_day,
                    "evaluable_followup_days": endpoint_evaluable_days,
                    "first_evaluable_day": first_evaluable_day,
                    "last_evaluable_day": last_evaluable_day,
                    "missing_observation_days": int(
                        group["deviation_status"].eq("missing_observation").sum()
                    ),
                    "session_qc_failed_days": int(
                        group["deviation_status"].eq("session_qc_failed").sum()
                    ),
                    "has_intermittent_missing": intermittent_missing,
                    "trailing_missing_days": trailing_missing_days,
                }
            )
    return pd.DataFrame.from_records(rows).sort_values(
        ["endpoint", "participant_id", "posture"]
    ).reset_index(drop=True)


def summarize_hrv_recovery_events(events: pd.DataFrame) -> pd.DataFrame:
    """Summarize observed and censored recovery events by endpoint and posture."""

    rows: list[dict[str, object]] = []
    for (endpoint, posture), group in events.groupby(["endpoint", "posture"], sort=True):
        risk = group.loc[group["survival_eligible"]]
        recovered = risk.loc[risk["event_observed"]]
        rows.append(
            {
                "endpoint": endpoint,
                "posture": posture,
                "participant_posture_rows": len(group),
                "survival_eligible": len(risk),
                "recovered": len(recovered),
                "right_censored": int(risk["right_censored"].sum()),
                "recovery_proportion_observed": (
                    len(recovered) / len(risk) if len(risk) else float("nan")
                ),
                "median_recovery_day_among_recovered": recovered["recovery_day"].median(),
                "maximum_analysis_time": risk["analysis_time_days"].max(),
                "with_intermittent_missing": int(risk["has_intermittent_missing"].sum()),
            }
        )
    return pd.DataFrame.from_records(rows)


def render_recovery_event_report(events: pd.DataFrame) -> str:
    """Render a compact Markdown audit for the primary composite endpoint."""

    primary = events.loc[events["endpoint"].eq("hrv_composite")]
    risk = primary.loc[primary["survival_eligible"]]
    recovered = int(risk["event_observed"].sum())
    censored = int(risk["right_censored"].sum())
    unavailable = len(primary) - len(risk)
    threshold = float(primary["threshold"].iloc[0])
    required_days = int(primary["required_consecutive_days"].iloc[0])
    return f"""# Bourdillon first HRV recovery event report

## Primary definition

- Endpoint: **composite RMSSD/SDNN absolute deviation score**
- Recovered: score <= **{threshold:g}** for **{required_days} consecutive days**
- Event day: first day in the qualifying run
- Maximum planned follow-up: recovery day **{int(primary['planned_followup_days'].max())}**

## Primary endpoint coverage

- Participant-posture combinations: **{len(primary)}**
- Eligible with evaluable follow-up: **{len(risk)}**
- Recovery events observed: **{recovered}**
- Right-censored without demonstrated recovery: **{censored}**
- Not entered into the risk set: **{unavailable}**

Missing and failed-QC days break consecutive recovery. An unrecovered eligible
series is censored at its last evaluable recovery day. The event table also
contains separate RMSSD and SDNN endpoints and records intermittent or trailing
missingness for later sensitivity and survival analyses.
"""
