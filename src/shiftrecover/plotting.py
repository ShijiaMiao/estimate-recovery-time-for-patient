"""Publication-style core figures for the Bourdillon recovery analysis."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd


FIGURE_STEMS = (
    "figure_1_experiment_timeline",
    "figure_2_individual_recovery_trajectories",
    "figure_3_participant_recovery_heatmap",
    "figure_4_kaplan_meier_recovery",
)

COLORS = {
    "navy": "#174A7E",
    "blue": "#4C78A8",
    "orange": "#F28E2B",
    "green": "#2E8B57",
    "red": "#C44E52",
    "gray": "#6B7280",
    "light_gray": "#E5E7EB",
}


def _set_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 13,
            "axes.labelsize": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "svg.fonttype": "none",
        }
    )


def _as_bool(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values.dtype):
        return values.fillna(False).astype(bool)
    return values.astype("string").str.lower().eq("true").fillna(False)


def _save_figure(figure: plt.Figure, output_dir: Path, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_dir / f"{stem}.png", dpi=300, bbox_inches="tight")
    figure.savefig(output_dir / f"{stem}.svg", bbox_inches="tight")
    plt.close(figure)


def plot_experiment_timeline(hrv: pd.DataFrame) -> plt.Figure:
    """Plot the standardized protocol and observed participant coverage."""

    required = {"participant_id", "phase", "phase_day_calendar", "qc_pass"}
    missing = sorted(required - set(hrv.columns))
    if missing:
        raise ValueError("Missing HRV timeline columns: " + ", ".join(missing))
    data = hrv.copy()
    data["qc_pass"] = _as_bool(data["qc_pass"])
    phase_spec = [
        ("Baseline", "baseline", 1, 7, COLORS["blue"]),
        ("Partial sleep\ndeprivation", "sleep_deprivation", 8, 10, COLORS["orange"]),
        ("Recovery", "recovery", 11, 17, COLORS["green"]),
    ]
    figure, axis = plt.subplots(figsize=(11.5, 4.4))
    for label, phase, start, end, color in phase_spec:
        axis.add_patch(
            Rectangle(
                (start - 0.45, 0.58),
                end - start + 0.9,
                0.28,
                facecolor=color,
                edgecolor="white",
            )
        )
        axis.text((start + end) / 2, 0.72, label, ha="center", va="center", color="white")
        phase_rows = data.loc[data["phase"].eq(phase)]
        coverage = (
            phase_rows.loc[phase_rows["qc_pass"]]
            .groupby("phase_day_calendar")["participant_id"]
            .nunique()
        )
        duration = end - start + 1
        for phase_day in range(1, duration + 1):
            protocol_day = start + phase_day - 1
            count = int(coverage.get(phase_day, 0))
            axis.scatter(
                protocol_day,
                0.35,
                s=max(18, count * 12),
                color=color,
                edgecolor="white",
                linewidth=0.7,
                zorder=3,
            )
            axis.text(protocol_day, 0.13, str(count), ha="center", va="center", fontsize=8)
    axis.axvline(10.5, color=COLORS["red"], linestyle="--", linewidth=1.3)
    axis.text(10.55, 0.96, "Recovery follow-up starts", color=COLORS["red"], fontsize=9)
    axis.set_xlim(0.3, 17.7)
    axis.set_ylim(0, 1.08)
    axis.set_xticks(range(1, 18))
    axis.set_xticklabels(
        [*[f"B{i}" for i in range(1, 8)], *[f"PSD{i}" for i in range(1, 4)],
         *[f"R{i}" for i in range(1, 8)]]
    )
    axis.set_yticks([])
    axis.set_xlabel("Protocol day")
    axis.set_title("Bourdillon protocol and QC-passing RR measurement coverage", loc="left")
    axis.text(
        0.4,
        0.02,
        "Numbers below circles are participants with a QC-passing posture series; "
        "circle area scales with coverage.",
        fontsize=8.5,
        color=COLORS["gray"],
    )
    for spine in axis.spines.values():
        spine.set_visible(False)
    figure.tight_layout()
    return figure


def _primary_events(events: pd.DataFrame) -> pd.DataFrame:
    required = {
        "participant_id",
        "posture",
        "endpoint",
        "baseline_method",
        "required_consecutive_days",
        "survival_eligible",
        "event_observed",
        "recovery_day",
        "analysis_time_days",
    }
    missing = sorted(required - set(events.columns))
    if missing:
        raise ValueError("Missing recovery event columns: " + ", ".join(missing))
    data = events.copy()
    data["survival_eligible"] = _as_bool(data["survival_eligible"])
    data["event_observed"] = _as_bool(data["event_observed"])
    return data.loc[
        data["endpoint"].eq("hrv_composite")
        & data["baseline_method"].eq("personal")
        & data["required_consecutive_days"].eq(2)
        & data["survival_eligible"]
    ].copy()


def plot_individual_recovery_trajectories(
    deviations: pd.DataFrame,
    events: pd.DataFrame,
    *,
    threshold: float = 1.5,
) -> plt.Figure:
    """Plot participant composite deviations and confirmed recovery events."""

    required = {
        "participant_id",
        "posture",
        "recovery_day",
        "hrv_deviation_score",
        "eligible_for_recovery_analysis",
    }
    missing = sorted(required - set(deviations.columns))
    if missing:
        raise ValueError("Missing trajectory columns: " + ", ".join(missing))
    data = deviations.copy()
    data["eligible_for_recovery_analysis"] = _as_bool(
        data["eligible_for_recovery_analysis"]
    )
    data = data.loc[data["eligible_for_recovery_analysis"]]
    primary = _primary_events(events).set_index(["participant_id", "posture"])
    figure, axes = plt.subplots(1, 2, figsize=(12, 5.4), sharex=True, sharey=True)
    for axis, posture in zip(axes, ("standing", "supine")):
        posture_data = data.loc[data["posture"].eq(posture)]
        for participant, group in posture_data.groupby("participant_id", sort=True):
            event = primary.loc[(participant, posture)]
            recovered = bool(event["event_observed"])
            color = COLORS["blue"] if recovered else COLORS["orange"]
            group = group.sort_values("recovery_day")
            axis.plot(
                group["recovery_day"],
                group["hrv_deviation_score"],
                color=color,
                alpha=0.62,
                linewidth=1.15,
                marker="o",
                markersize=2.8,
            )
            if recovered:
                day = float(event["recovery_day"])
                score = group.loc[group["recovery_day"].eq(day), "hrv_deviation_score"]
                if not score.empty and np.isfinite(score.iloc[0]):
                    axis.scatter(day, score.iloc[0], marker="D", s=32, color=COLORS["green"])
            else:
                evaluable = group.dropna(subset=["hrv_deviation_score"])
                if not evaluable.empty:
                    last = evaluable.iloc[-1]
                    axis.scatter(
                        last["recovery_day"],
                        last["hrv_deviation_score"],
                        marker="X",
                        s=38,
                        color=COLORS["red"],
                    )
        axis.axhspan(0, threshold, color=COLORS["green"], alpha=0.09)
        axis.axhline(threshold, color=COLORS["green"], linestyle="--", linewidth=1.4)
        axis.set_title(posture.capitalize(), loc="left")
        axis.set_xticks(range(1, 8))
        axis.set_xlabel("Recovery day")
        axis.grid(axis="y", color=COLORS["light_gray"], linewidth=0.7)
    axes[0].set_ylabel("Personal composite HRV deviation score")
    figure.suptitle(
        "Individual recovery trajectories after partial sleep deprivation",
        x=0.07,
        ha="left",
        fontsize=14,
    )
    legend = [
        Line2D([0], [0], color=COLORS["blue"], label="Recovered within follow-up"),
        Line2D([0], [0], color=COLORS["orange"], label="Right-censored"),
        Line2D([0], [0], marker="D", color="none", markerfacecolor=COLORS["green"],
               label="First day of confirmed recovery"),
        Line2D([0], [0], marker="X", color="none", markerfacecolor=COLORS["red"],
               label="Last observed day without recovery"),
    ]
    figure.legend(handles=legend, loc="lower center", ncol=2, frameon=False)
    figure.tight_layout(rect=(0, 0.12, 1, 0.95))
    return figure


def prepare_recovery_heatmap(
    deviations: pd.DataFrame,
    events: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    """Create a sorted participant-posture matrix and recovery-day annotation."""

    primary = _primary_events(events)
    eligible = primary[["participant_id", "posture"]]
    data = deviations.merge(eligible, on=["participant_id", "posture"], how="inner")
    matrix = data.pivot(
        index=["participant_id", "posture"],
        columns="recovery_day",
        values="hrv_deviation_score",
    ).reindex(columns=range(1, 8))
    recovery = primary.set_index(["participant_id", "posture"])["recovery_day"]
    order = pd.DataFrame(index=matrix.index)
    order["recovered"] = recovery.notna()
    order["recovery_day"] = recovery.fillna(99)
    order["participant_label"] = order.index.get_level_values("participant_id")
    order["posture_label"] = order.index.get_level_values("posture")
    ordered_index = order.sort_values(
        ["recovered", "recovery_day", "participant_label", "posture_label"],
        ascending=[False, True, True, True],
    ).index
    return matrix.loc[ordered_index], recovery.reindex(ordered_index)


def plot_participant_recovery_heatmap(
    deviations: pd.DataFrame,
    events: pd.DataFrame,
) -> plt.Figure:
    """Plot participant-posture by recovery-day composite deviation heatmap."""

    matrix, recovery = prepare_recovery_heatmap(deviations, events)
    cmap = plt.get_cmap("RdYlBu_r").with_extremes(bad="#D1D5DB")
    figure, axis = plt.subplots(figsize=(9.2, 10.2))
    image = axis.imshow(
        matrix.to_numpy(float),
        aspect="auto",
        cmap=cmap,
        norm=Normalize(vmin=0, vmax=5),
        interpolation="none",
    )
    for row, day in enumerate(recovery):
        if np.isfinite(day):
            axis.text(int(day) - 1, row, "R", ha="center", va="center", fontweight="bold")
    axis.set_xticks(range(7), labels=[f"Day {day}" for day in range(1, 8)])
    labels = [f"{participant} · {posture}" for participant, posture in matrix.index]
    axis.set_yticks(range(len(labels)), labels=labels)
    axis.tick_params(axis="y", labelsize=8)
    axis.set_xlabel("Recovery follow-up")
    axis.set_title("Participant-level HRV recovery heatmap", loc="left", pad=12)
    axis.set_xticks(np.arange(-0.5, 7, 1), minor=True)
    axis.set_yticks(np.arange(-0.5, len(labels), 1), minor=True)
    axis.grid(which="minor", color="white", linewidth=0.7)
    axis.tick_params(which="minor", bottom=False, left=False)
    colorbar = figure.colorbar(image, ax=axis, fraction=0.035, pad=0.03)
    colorbar.set_label("Composite deviation score (values ≥5 share one colour)")
    axis.text(
        0,
        -0.055,
        "R = first day of two-day confirmed recovery; grey = missing or QC-failed.",
        transform=axis.transAxes,
        fontsize=8.5,
        color=COLORS["gray"],
        va="top",
    )
    figure.tight_layout(rect=(0, 0.025, 1, 1))
    return figure


def kaplan_meier_curve(
    analysis_time_days: pd.Series | np.ndarray,
    event_observed: pd.Series | np.ndarray,
    *,
    horizon_days: int = 7,
) -> pd.DataFrame:
    """Return a step-function table for cumulative probability of recovery."""

    time = np.asarray(analysis_time_days, dtype=float)
    event = np.asarray(event_observed, dtype=bool)
    valid = np.isfinite(time) & (time > 0)
    time = time[valid]
    event = event[valid]
    if len(time) == 0:
        raise ValueError("Kaplan-Meier curve requires at least one valid observation")
    survival = 1.0
    records = [{"day": 0.0, "recovery_probability": 0.0, "at_risk": len(time)}]
    for day in sorted(np.unique(time[time <= horizon_days])):
        at_risk = int(np.sum(time >= day))
        events = int(np.sum((time == day) & event))
        survival *= 1.0 - events / at_risk
        records.append(
            {
                "day": float(day),
                "recovery_probability": 1.0 - survival,
                "at_risk": at_risk,
            }
        )
    if records[-1]["day"] < horizon_days:
        records.append(
            {
                "day": float(horizon_days),
                "recovery_probability": 1.0 - survival,
                "at_risk": int(np.sum(time >= horizon_days)),
            }
        )
    return pd.DataFrame.from_records(records)


def plot_kaplan_meier_recovery(events: pd.DataFrame) -> plt.Figure:
    """Compare cumulative recovery curves for all four operational strategies."""

    data = events.copy()
    data["survival_eligible"] = _as_bool(data["survival_eligible"])
    data["event_observed"] = _as_bool(data["event_observed"])
    data = data.loc[data["endpoint"].eq("hrv_composite") & data["survival_eligible"]]
    figure, axis = plt.subplots(figsize=(9.5, 5.8))
    method_colors = {"personal": COLORS["navy"], "population_average": COLORS["orange"]}
    line_styles = {1: "--", 2: "-"}
    for (method, days), group in data.groupby(
        ["baseline_method", "required_consecutive_days"], sort=True
    ):
        curve = kaplan_meier_curve(group["analysis_time_days"], group["event_observed"])
        recovered = int(group["event_observed"].sum())
        label_method = "Personal" if method == "personal" else "Population average"
        axis.step(
            curve["day"],
            curve["recovery_probability"],
            where="post",
            color=method_colors[method],
            linestyle=line_styles[int(days)],
            linewidth=2.2,
            label=f"{label_method}, {int(days)}-day rule ({recovered}/{len(group)})",
        )
    axis.set_xlim(0, 7)
    axis.set_ylim(0, 1.03)
    axis.set_xticks(range(0, 8))
    axis.set_yticks(np.linspace(0, 1, 6), labels=[f"{value:.0%}" for value in np.linspace(0, 1, 6)])
    axis.set_xlabel("Days since recovery follow-up began")
    axis.set_ylabel("Cumulative probability of confirmed recovery")
    axis.set_title("Kaplan–Meier recovery curves under four operational definitions", loc="left")
    axis.grid(color=COLORS["light_gray"], linewidth=0.7)
    axis.legend(loc="lower right", frameon=False)
    axis.text(
        0,
        -0.17,
        "Standing and supine series are shown together; bootstrap uncertainty is "
        "reported separately using participant-level clusters.",
        transform=axis.transAxes,
        fontsize=8.5,
        color=COLORS["gray"],
    )
    figure.tight_layout()
    return figure


def render_figure_report(output_dir: Path) -> str:
    """Describe the analytical role of every generated figure."""

    return f"""# Core figure guide

1. **Experiment timeline** — maps baseline, partial sleep deprivation and
   recovery days, with actual QC-passing RR coverage.
2. **Individual trajectories** — shows whether each participant-posture series
   crosses and sustains the personal recovery threshold; diamonds mark the
   first confirmed day and crosses mark unrecovered follow-up endings.
3. **Participant heatmap** — exposes heterogeneity, intermittent deviations and
   missing/QC-failed days instead of hiding them in an average.
4. **Kaplan–Meier curves** — compares cumulative confirmed recovery under the
   four baseline and confirmation-rule combinations.

Every figure is available as a 300-dpi PNG for README display and an SVG for
editing or publication. Output directory: `{output_dir}`.
"""


def generate_core_figures(
    hrv: pd.DataFrame,
    deviations: pd.DataFrame,
    events: pd.DataFrame,
    output_dir: Path,
) -> None:
    """Generate and save the four prespecified figures in PNG and SVG formats."""

    _set_style()
    figures = (
        plot_experiment_timeline(hrv),
        plot_individual_recovery_trajectories(deviations, events),
        plot_participant_recovery_heatmap(deviations, events),
        plot_kaplan_meier_recovery(events),
    )
    for stem, figure in zip(FIGURE_STEMS, figures):
        _save_figure(figure, output_dir, stem)
    (output_dir / "FIGURE_GUIDE.md").write_text(
        render_figure_report(output_dir), encoding="utf-8"
    )
