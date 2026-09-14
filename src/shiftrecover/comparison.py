"""Compare personal versus population baselines and recovery confirmation rules."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from .recovery_time import estimate_hrv_recovery_events


HRV_METRICS = ("rmssd_ms", "sdnn_ms")


def _bool_series(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values.dtype):
        return values.fillna(False).astype(bool)
    return values.astype("string").str.lower().eq("true").fillna(False)


def estimate_population_hrv_baselines(
    personal_baselines: pd.DataFrame,
    *,
    metric_columns: tuple[str, ...] = HRV_METRICS,
    minimum_log_scale: float = 0.05,
    range_multiplier: float = 1.5,
) -> pd.DataFrame:
    """Estimate participant-weighted population mean baselines by posture."""

    required = {"participant_id", "posture", "baseline_sufficient"}
    required.update(f"{metric}__centre_log" for metric in metric_columns)
    missing = sorted(required - set(personal_baselines.columns))
    if missing:
        raise ValueError("Missing personal baseline columns: " + ", ".join(missing))
    if minimum_log_scale <= 0 or range_multiplier <= 0:
        raise ValueError("Scale floor and range multiplier must be positive")

    data = personal_baselines.copy()
    data = data.loc[_bool_series(data["baseline_sufficient"])]
    rows: list[dict[str, object]] = []
    for posture, group in data.groupby("posture", sort=True):
        record: dict[str, object] = {
            "posture": posture,
            "baseline_method": "population_average",
            "range_multiplier": range_multiplier,
        }
        contributor_counts: list[int] = []
        for metric in metric_columns:
            values = pd.to_numeric(
                group[f"{metric}__centre_log"], errors="coerce"
            ).to_numpy(float)
            values = values[np.isfinite(values)]
            if len(values) < 2:
                raise ValueError(f"Too few population baseline contributors for {posture}/{metric}")
            centre_log = float(np.mean(values))
            raw_scale_log = float(np.std(values, ddof=1))
            scale_log = max(raw_scale_log, minimum_log_scale)
            record[f"{metric}__n"] = len(values)
            record[f"{metric}__centre_log"] = centre_log
            record[f"{metric}__scale_log"] = scale_log
            record[f"{metric}__centre_ms"] = float(np.exp(centre_log))
            record[f"{metric}__normal_lower_ms"] = float(
                np.exp(centre_log - range_multiplier * scale_log)
            )
            record[f"{metric}__normal_upper_ms"] = float(
                np.exp(centre_log + range_multiplier * scale_log)
            )
            record[f"{metric}__scale_floor_applied"] = raw_scale_log < minimum_log_scale
            contributor_counts.append(len(values))
        record["population_contributors"] = min(contributor_counts)
        rows.append(record)
    return pd.DataFrame.from_records(rows)


def expand_population_baselines_to_common_risk_set(
    personal_baselines: pd.DataFrame,
    population_baselines: pd.DataFrame,
) -> pd.DataFrame:
    """Attach population references while preserving personal-method eligibility."""

    common = personal_baselines[
        ["participant_id", "posture", "eligible_for_recovery_analysis"]
    ].copy()
    common["eligible_for_recovery_analysis"] = _bool_series(
        common["eligible_for_recovery_analysis"]
    )
    expanded = common.merge(
        population_baselines,
        on="posture",
        how="left",
        validate="many_to_one",
    )
    expanded["baseline_status"] = np.where(
        expanded["eligible_for_recovery_analysis"],
        "ready",
        "common_risk_set_excluded",
    )
    return expanded


def estimate_method_comparison_events(
    personal_deviations: pd.DataFrame,
    population_deviations: pd.DataFrame,
    *,
    threshold: float = 1.5,
    consecutive_day_options: Iterable[int] = (1, 2),
) -> pd.DataFrame:
    """Estimate all baseline-method and confirmation-rule combinations."""

    options = sorted(set(int(value) for value in consecutive_day_options))
    if set(options) != {1, 2}:
        raise ValueError("Comparison requires consecutive-day options 1 and 2")
    pieces: list[pd.DataFrame] = []
    for baseline_method, deviations in (
        ("personal", personal_deviations),
        ("population_average", population_deviations),
    ):
        for consecutive_days in options:
            events = estimate_hrv_recovery_events(
                deviations,
                threshold=threshold,
                consecutive_days=consecutive_days,
            )
            events["baseline_method"] = baseline_method
            events["confirmation_rule"] = f"{consecutive_days}_day"
            events["is_primary_strategy"] = (
                baseline_method == "personal" and consecutive_days == 2
            )
            pieces.append(events)
    return pd.concat(pieces, ignore_index=True).sort_values(
        [
            "endpoint",
            "participant_id",
            "posture",
            "baseline_method",
            "required_consecutive_days",
        ]
    ).reset_index(drop=True)


def summarize_method_comparison(events: pd.DataFrame) -> pd.DataFrame:
    """Summarize recovery outcomes for each comparison strategy."""

    rows: list[dict[str, object]] = []
    grouping = ["baseline_method", "required_consecutive_days", "endpoint", "posture"]
    for key, group in events.groupby(grouping, sort=True):
        risk = group.loc[group["survival_eligible"]]
        recovered = risk.loc[risk["event_observed"]]
        rows.append(
            {
                "baseline_method": key[0],
                "required_consecutive_days": key[1],
                "endpoint": key[2],
                "posture": key[3],
                "eligible": len(risk),
                "recovered": len(recovered),
                "right_censored": int(risk["right_censored"].sum()),
                "recovery_proportion_observed": (
                    len(recovered) / len(risk) if len(risk) else float("nan")
                ),
                "median_recovery_day_among_recovered": recovered["recovery_day"].median(),
            }
        )
    return pd.DataFrame.from_records(rows)


def build_method_comparison_paired_table(
    events: pd.DataFrame,
    *,
    endpoint: str = "hrv_composite",
) -> pd.DataFrame:
    """Place four composite-endpoint strategy results side by side."""

    selected = events.loc[events["endpoint"].eq(endpoint)]
    identifiers = ["participant_id", "posture"]
    result = selected[identifiers].drop_duplicates().sort_values(identifiers)
    for (method, days), group in selected.groupby(
        ["baseline_method", "required_consecutive_days"], sort=True
    ):
        suffix = f"{method}__{days}_day"
        columns = {
            "survival_eligible": f"{suffix}__survival_eligible",
            "event_observed": f"{suffix}__event_observed",
            "recovery_day": f"{suffix}__recovery_day",
            "right_censored": f"{suffix}__right_censored",
            "analysis_time_days": f"{suffix}__analysis_time_days",
        }
        subset = group[[*identifiers, *columns]].rename(columns=columns)
        result = result.merge(subset, on=identifiers, how="left", validate="one_to_one")
    return result.reset_index(drop=True)


def summarize_method_discordance(events: pd.DataFrame) -> pd.DataFrame:
    """Count paired disagreements between baseline and confirmation strategies."""

    records: list[dict[str, object]] = []
    for days in (1, 2):
        subset = events.loc[events["required_consecutive_days"].eq(days)]
        for (endpoint, posture), group in subset.groupby(["endpoint", "posture"]):
            wide = group.pivot(index=["participant_id", "posture"], columns="baseline_method")
            eligible = wide["survival_eligible"].all(axis=1)
            wide = wide.loc[eligible]
            personal_event = wide["event_observed"]["personal"].astype(bool)
            population_event = wide["event_observed"]["population_average"].astype(bool)
            personal_day = wide["recovery_day"]["personal"]
            population_day = wide["recovery_day"]["population_average"]
            category = np.select(
                [
                    personal_event & population_event & personal_day.eq(population_day),
                    personal_event & population_event & personal_day.lt(population_day),
                    personal_event & population_event & population_day.lt(personal_day),
                    personal_event & ~population_event,
                    ~personal_event & population_event,
                ],
                [
                    "both_recovered_same_day",
                    "personal_earlier",
                    "population_earlier",
                    "personal_only_recovered",
                    "population_only_recovered",
                ],
                default="both_right_censored",
            )
            counts = pd.Series(category).value_counts()
            for label, count in counts.items():
                records.append(
                    {
                        "comparison": "personal_vs_population",
                        "required_consecutive_days": days,
                        "baseline_method": "both",
                        "endpoint": endpoint,
                        "posture": posture,
                        "category": label,
                        "count": int(count),
                    }
                )

    for method in ("personal", "population_average"):
        subset = events.loc[events["baseline_method"].eq(method)]
        for (endpoint, posture), group in subset.groupby(["endpoint", "posture"]):
            wide = group.pivot(
                index=["participant_id", "posture"], columns="required_consecutive_days"
            )
            eligible = wide["survival_eligible"].all(axis=1)
            wide = wide.loc[eligible]
            one_event = wide["event_observed"][1].astype(bool)
            two_event = wide["event_observed"][2].astype(bool)
            one_day = wide["recovery_day"][1]
            two_day = wide["recovery_day"][2]
            category = np.select(
                [
                    one_event & two_event & one_day.eq(two_day),
                    one_event & two_event & one_day.lt(two_day),
                    one_event & ~two_event,
                    ~one_event & two_event,
                ],
                [
                    "both_recovered_same_day",
                    "two_day_rule_later",
                    "one_day_only_recovered",
                    "two_day_only_recovered",
                ],
                default="both_right_censored",
            )
            counts = pd.Series(category).value_counts()
            for label, count in counts.items():
                records.append(
                    {
                        "comparison": "one_day_vs_two_day",
                        "required_consecutive_days": pd.NA,
                        "baseline_method": method,
                        "endpoint": endpoint,
                        "posture": posture,
                        "category": label,
                        "count": int(count),
                    }
                )
    return pd.DataFrame.from_records(records)


def audit_method_comparison(events: pd.DataFrame) -> pd.DataFrame:
    """Audit common risk sets and one-day/two-day logical ordering."""

    rows: list[dict[str, object]] = []
    identity = ["participant_id", "posture", "endpoint"]
    for method, subset in events.groupby("baseline_method", sort=True):
        for key, group in subset.groupby(identity, sort=True):
            indexed = group.set_index("required_consecutive_days")
            one = indexed.loc[1]
            two = indexed.loc[2]
            violation = bool(two["event_observed"]) and (
                not bool(one["event_observed"])
                or float(one["recovery_day"]) > float(two["recovery_day"])
            )
            rows.append(
                {
                    "audit_type": "confirmation_rule_order",
                    "participant_id": key[0],
                    "posture": key[1],
                    "endpoint": key[2],
                    "baseline_method": method,
                    "required_consecutive_days": pd.NA,
                    "violation": violation,
                }
            )
    for days, subset in events.groupby("required_consecutive_days", sort=True):
        for key, group in subset.groupby(identity, sort=True):
            indexed = group.set_index("baseline_method")
            personal = bool(indexed.loc["personal", "survival_eligible"])
            population = bool(indexed.loc["population_average", "survival_eligible"])
            rows.append(
                {
                    "audit_type": "common_risk_set",
                    "participant_id": key[0],
                    "posture": key[1],
                    "endpoint": key[2],
                    "baseline_method": "both",
                    "required_consecutive_days": days,
                    "violation": personal != population,
                }
            )
    return pd.DataFrame.from_records(rows)


def render_method_comparison_report(
    events: pd.DataFrame,
    audit: pd.DataFrame,
) -> str:
    """Render a primary composite-endpoint four-strategy report."""

    primary = events.loc[events["endpoint"].eq("hrv_composite")]
    lines = []
    for (method, days), group in primary.groupby(
        ["baseline_method", "required_consecutive_days"], sort=True
    ):
        risk = group.loc[group["survival_eligible"]]
        recovered = int(risk["event_observed"].sum())
        censored = int(risk["right_censored"].sum())
        lines.append(f"| {method} | {days} | {len(risk)} | {recovered} | {censored} |")
    table = "\n".join(lines)
    violations = int(audit["violation"].sum())
    return f"""# Bourdillon baseline and confirmation-rule comparison

All strategies use threshold 1.5, recovery days 1-7, and the same common risk
set. Population references give each participant one baseline contribution.

| Baseline | Consecutive days | Eligible | Recovered | Right-censored |
|---|---:|---:|---:|---:|
{table}

Logical audit violations: **{violations}**. The comparison estimates how much
the operational recovery result changes when personalization or the stability
confirmation requirement is removed; it does not validate any rule clinically.
"""
