"""Command-line interface for the method demonstration."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .baseline import (
    audit_hrv_baseline_observations,
    estimate_personal_baselines,
    estimate_personal_hrv_baselines,
    render_hrv_baseline_report,
)
from .bourdillon import (
    load_bourdillon_rr,
    render_bourdillon_ingestion_report,
    summarize_bourdillon_participants,
    summarize_bourdillon_sessions,
)
from .bootstrap import (
    audit_bootstrap_intervals,
    cluster_bootstrap_recovery,
    render_bootstrap_report,
    summarize_bootstrap_intervals,
    summarize_recovery_uncertainty_points,
)
from .comparison import (
    audit_method_comparison,
    build_method_comparison_paired_table,
    estimate_method_comparison_events,
    estimate_population_hrv_baselines,
    expand_population_baselines_to_common_risk_set,
    render_method_comparison_report,
    summarize_method_comparison,
    summarize_method_discordance,
)
from .deviation import (
    build_hrv_recovery_deviations,
    render_recovery_deviation_report,
    summarize_recovery_deviations,
)
from .hrv import (
    calculate_session_hrv,
    clean_bourdillon_rr,
    render_hrv_report,
    summarize_hrv_qc,
)
from .mauvieux import load_mauvieux_sleep, summarize_mauvieux_sleep
from .plotting import generate_core_figures
from .recovery import add_deviation_scores, estimate_recovery_events
from .recovery_time import (
    estimate_hrv_recovery_events,
    render_recovery_event_report,
    summarize_hrv_recovery_events,
)
from .simulate import simulate_shift_wearable_data
from .sensitivity import (
    audit_threshold_monotonicity,
    build_threshold_stability_table,
    estimate_threshold_sensitivity,
    render_threshold_sensitivity_report,
    summarize_threshold_sensitivity,
)


FEATURE_TYPES = {
    "sleep_onset_hour": "circular",
    "sleep_midpoint_hour": "circular",
    "total_sleep_hours": "linear",
    "sleep_efficiency": "linear",
    "resting_hr": "linear",
    "steps": "linear",
}

MINIMUM_SCALES = {
    "sleep_onset_hour": 0.25,
    "sleep_midpoint_hour": 0.25,
    "total_sleep_hours": 0.25,
    "sleep_efficiency": 1.0,
    "resting_hr": 1.0,
    "steps": 500.0,
}


def run_demo(output_dir: Path, participants: int, seed: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    daily = simulate_shift_wearable_data(n_participants=participants, seed=seed)
    baselines = estimate_personal_baselines(
        daily,
        FEATURE_TYPES,
        min_days=4,
        minimum_scales=MINIMUM_SCALES,
    )
    scored = add_deviation_scores(daily, baselines, FEATURE_TYPES)
    events = estimate_recovery_events(scored, threshold=1.5, consecutive_days=2)

    daily.to_csv(output_dir / "synthetic_daily.csv", index=False)
    baselines.to_csv(output_dir / "personal_baselines.csv", index=False)
    scored.to_csv(output_dir / "daily_deviation_scores.csv", index=False)
    events.to_csv(output_dir / "recovery_events.csv", index=False)

    recovered = int(events["recovered"].sum()) if not events.empty else 0
    print(f"Wrote demonstration outputs to: {output_dir.resolve()}")
    print(f"Recovery demonstrated for {recovered}/{len(events)} night-shift blocks.")


def run_mauvieux(data_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    tidy = load_mauvieux_sleep(data_dir)
    summary = summarize_mauvieux_sleep(tidy)
    tidy.to_csv(output_dir / "mauvieux_sleep_phase_tidy.csv", index=False)
    summary.to_csv(output_dir / "mauvieux_sleep_phase_summary.csv", index=False)
    participants = tidy.groupby("study")["participant_id"].nunique()
    print(f"Wrote Mauvieux phase outputs to: {output_dir.resolve()}")
    for study, count in participants.items():
        print(f"{study}: {count} unique participants")
    print("Important: the release is phase-aggregated, so day-level recovery time is not estimable.")


def run_bourdillon(data_dir: Path, output_dir: Path) -> None:
    """Ingest raw Bourdillon RR intervals and write transparent audit outputs."""

    output_dir.mkdir(parents=True, exist_ok=True)
    tidy = load_bourdillon_rr(data_dir)
    sessions = summarize_bourdillon_sessions(tidy)
    participants = summarize_bourdillon_participants(tidy)
    report = render_bourdillon_ingestion_report(tidy, sessions, participants)

    tidy.to_csv(output_dir / "bourdillon_rr_tidy.csv", index=False, date_format="%Y-%m-%d")
    sessions.to_csv(
        output_dir / "bourdillon_session_audit.csv", index=False, date_format="%Y-%m-%d"
    )
    participants.to_csv(output_dir / "bourdillon_participant_coverage.csv", index=False)
    (output_dir / "bourdillon_ingestion_report.md").write_text(report, encoding="utf-8")

    complete = int(participants["has_all_three_phases"].sum())
    print(f"Wrote Bourdillon ingestion outputs to: {output_dir.resolve()}")
    print(f"Preserved {len(tidy):,} RR intervals from {len(participants)} participants.")
    print(f"All three phases are present for {complete}/{len(participants)} participants.")
    print("Important: QC flags are annotations; no RR intervals were cleaned or interpolated.")


def run_bourdillon_hrv(
    input_file: Path,
    output_dir: Path,
    local_window: int,
    relative_threshold: float,
    robust_z_threshold: float,
    analysis_window_seconds: float,
    maximum_artifact_fraction: float,
) -> None:
    """Clean the standardized RR table and calculate time-domain HRV."""

    if not input_file.exists():
        raise FileNotFoundError(f"Bourdillon tidy RR file not found: {input_file}")
    output_dir.mkdir(parents=True, exist_ok=True)
    tidy = pd.read_csv(input_file, parse_dates=["date", "date_raw"], low_memory=False)
    cleaned = clean_bourdillon_rr(
        tidy,
        local_window=local_window,
        relative_threshold=relative_threshold,
        robust_z_threshold=robust_z_threshold,
        analysis_window_seconds=analysis_window_seconds,
    )
    metrics = calculate_session_hrv(
        cleaned,
        maximum_artifact_fraction=maximum_artifact_fraction,
    )
    qc_summary = summarize_hrv_qc(metrics)
    report = render_hrv_report(cleaned, metrics)

    cleaned.to_csv(
        output_dir / "bourdillon_nn_cleaned.csv", index=False, date_format="%Y-%m-%d"
    )
    metrics.to_csv(
        output_dir / "bourdillon_daily_hrv.csv", index=False, date_format="%Y-%m-%d"
    )
    qc_summary.to_csv(output_dir / "bourdillon_hrv_qc_summary.csv", index=False)
    (output_dir / "bourdillon_hrv_report.md").write_text(report, encoding="utf-8")

    print(f"Wrote Bourdillon HRV outputs to: {output_dir.resolve()}")
    print(f"QC passed for {int(metrics['qc_pass'].sum())}/{len(metrics)} posture series.")
    print("RMSSD and SDNN were calculated from corrected NN intervals only.")


def run_bourdillon_baseline(
    input_file: Path,
    output_dir: Path,
    min_days: int,
    minimum_log_scale: float,
    range_multiplier: float,
) -> None:
    """Estimate participant- and posture-specific HRV baseline ranges."""

    if not input_file.exists():
        raise FileNotFoundError(f"Bourdillon daily HRV file not found: {input_file}")
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics = pd.read_csv(input_file, parse_dates=["date", "date_raw"], low_memory=False)
    observations = audit_hrv_baseline_observations(metrics)
    baselines = estimate_personal_hrv_baselines(
        metrics,
        min_days=min_days,
        minimum_log_scale=minimum_log_scale,
        range_multiplier=range_multiplier,
    )
    report = render_hrv_baseline_report(baselines, observations)

    observations.to_csv(
        output_dir / "bourdillon_baseline_observations.csv",
        index=False,
        date_format="%Y-%m-%d",
    )
    baselines.to_csv(output_dir / "bourdillon_personal_hrv_baselines.csv", index=False)
    (output_dir / "bourdillon_baseline_report.md").write_text(report, encoding="utf-8")

    ready = int(baselines["eligible_for_recovery_analysis"].sum())
    print(f"Wrote Bourdillon baseline outputs to: {output_dir.resolve()}")
    print(f"Recovery analysis is supported for {ready}/{len(baselines)} posture baselines.")
    print("Ranges are individualized operational thresholds, not clinical reference ranges.")


def run_bourdillon_deviation(
    hrv_file: Path,
    baseline_file: Path,
    output_dir: Path,
    max_recovery_day: int,
) -> None:
    """Calculate daily HRV deviations from personal posture-specific baselines."""

    missing = [str(path) for path in (hrv_file, baseline_file) if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing Bourdillon analysis input(s): " + ", ".join(missing))
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics = pd.read_csv(hrv_file, parse_dates=["date", "date_raw"], low_memory=False)
    baselines = pd.read_csv(baseline_file, low_memory=False)
    deviations = build_hrv_recovery_deviations(
        metrics,
        baselines,
        max_recovery_day=max_recovery_day,
    )
    summary = summarize_recovery_deviations(deviations)
    report = render_recovery_deviation_report(deviations, summary)

    deviations.to_csv(
        output_dir / "bourdillon_recovery_daily_deviation.csv",
        index=False,
        date_format="%Y-%m-%d",
    )
    summary.to_csv(output_dir / "bourdillon_recovery_deviation_summary.csv", index=False)
    (output_dir / "bourdillon_recovery_deviation_report.md").write_text(
        report, encoding="utf-8"
    )
    calculated = int(deviations["deviation_status"].eq("calculated").sum())
    print(f"Wrote Bourdillon deviation outputs to: {output_dir.resolve()}")
    print(f"Calculated personal deviations for {calculated}/{len(deviations)} grid rows.")
    print("Missing recovery days remain explicit and are not treated as recovered.")


def run_bourdillon_recovery(
    deviation_file: Path,
    output_dir: Path,
    threshold: float,
    consecutive_days: int,
) -> None:
    """Estimate first HRV recovery and explicit right censoring."""

    if not deviation_file.exists():
        raise FileNotFoundError(f"Bourdillon deviation file not found: {deviation_file}")
    output_dir.mkdir(parents=True, exist_ok=True)
    deviations = pd.read_csv(
        deviation_file,
        parse_dates=["expected_date", "date"],
        low_memory=False,
    )
    events = estimate_hrv_recovery_events(
        deviations,
        threshold=threshold,
        consecutive_days=consecutive_days,
    )
    summary = summarize_hrv_recovery_events(events)
    report = render_recovery_event_report(events)
    primary = events.loc[events["endpoint"].eq("hrv_composite")].copy()

    events.to_csv(
        output_dir / "bourdillon_recovery_events_all_endpoints.csv",
        index=False,
        date_format="%Y-%m-%d",
    )
    primary.to_csv(
        output_dir / "bourdillon_primary_recovery_events.csv",
        index=False,
        date_format="%Y-%m-%d",
    )
    summary.to_csv(output_dir / "bourdillon_recovery_event_summary.csv", index=False)
    (output_dir / "bourdillon_recovery_event_report.md").write_text(
        report, encoding="utf-8"
    )
    risk = primary.loc[primary["survival_eligible"]]
    print(f"Wrote Bourdillon recovery events to: {output_dir.resolve()}")
    print(
        f"Primary recovery observed for {int(risk['event_observed'].sum())}/{len(risk)} "
        "eligible posture series."
    )
    print(f"Right-censored series: {int(risk['right_censored'].sum())}.")


def run_bourdillon_sensitivity(
    deviation_file: Path,
    output_dir: Path,
    thresholds: list[float],
    consecutive_days: int,
) -> None:
    """Repeat recovery estimation across prespecified score thresholds."""

    if not deviation_file.exists():
        raise FileNotFoundError(f"Bourdillon deviation file not found: {deviation_file}")
    output_dir.mkdir(parents=True, exist_ok=True)
    deviations = pd.read_csv(
        deviation_file,
        parse_dates=["expected_date", "date"],
        low_memory=False,
    )
    events = estimate_threshold_sensitivity(
        deviations,
        thresholds=thresholds,
        consecutive_days=consecutive_days,
    )
    summary = summarize_threshold_sensitivity(events)
    stability = build_threshold_stability_table(events)
    monotonicity = audit_threshold_monotonicity(events)
    report = render_threshold_sensitivity_report(events, monotonicity)

    events.to_csv(
        output_dir / "bourdillon_threshold_sensitivity_events.csv",
        index=False,
        date_format="%Y-%m-%d",
    )
    summary.to_csv(output_dir / "bourdillon_threshold_sensitivity_summary.csv", index=False)
    stability.to_csv(output_dir / "bourdillon_threshold_stability_matrix.csv", index=False)
    monotonicity.to_csv(output_dir / "bourdillon_threshold_monotonicity_audit.csv", index=False)
    (output_dir / "bourdillon_threshold_sensitivity_report.md").write_text(
        report, encoding="utf-8"
    )
    violations = int(monotonicity["monotonicity_violation"].sum())
    print(f"Wrote Bourdillon threshold sensitivity outputs to: {output_dir.resolve()}")
    print(f"Completed thresholds: {', '.join(f'{value:g}' for value in sorted(thresholds))}.")
    print(f"Threshold monotonicity violations: {violations}.")


def run_bourdillon_comparison(
    hrv_file: Path,
    personal_baseline_file: Path,
    personal_deviation_file: Path,
    output_dir: Path,
    threshold: float,
) -> None:
    """Compare personal/population baselines and one-/two-day recovery."""

    input_files = (hrv_file, personal_baseline_file, personal_deviation_file)
    missing = [str(path) for path in input_files if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing comparison input(s): " + ", ".join(missing))
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics = pd.read_csv(hrv_file, parse_dates=["date", "date_raw"], low_memory=False)
    personal_baselines = pd.read_csv(personal_baseline_file, low_memory=False)
    personal_deviations = pd.read_csv(
        personal_deviation_file,
        parse_dates=["expected_date", "date"],
        low_memory=False,
    )

    population_baselines = estimate_population_hrv_baselines(personal_baselines)
    expanded_population = expand_population_baselines_to_common_risk_set(
        personal_baselines, population_baselines
    )
    population_deviations = build_hrv_recovery_deviations(
        metrics,
        expanded_population,
        max_recovery_day=7,
    )
    events = estimate_method_comparison_events(
        personal_deviations,
        population_deviations,
        threshold=threshold,
    )
    summary = summarize_method_comparison(events)
    paired = build_method_comparison_paired_table(events)
    discordance = summarize_method_discordance(events)
    audit = audit_method_comparison(events)
    report = render_method_comparison_report(events, audit)

    population_baselines.to_csv(
        output_dir / "bourdillon_population_hrv_baselines.csv", index=False
    )
    population_deviations.to_csv(
        output_dir / "bourdillon_population_recovery_deviation.csv",
        index=False,
        date_format="%Y-%m-%d",
    )
    events.to_csv(
        output_dir / "bourdillon_method_comparison_events.csv",
        index=False,
        date_format="%Y-%m-%d",
    )
    summary.to_csv(output_dir / "bourdillon_method_comparison_summary.csv", index=False)
    paired.to_csv(output_dir / "bourdillon_method_comparison_paired.csv", index=False)
    discordance.to_csv(
        output_dir / "bourdillon_method_comparison_discordance.csv", index=False
    )
    audit.to_csv(output_dir / "bourdillon_method_comparison_audit.csv", index=False)
    (output_dir / "bourdillon_method_comparison_report.md").write_text(
        report, encoding="utf-8"
    )

    violations = int(audit["violation"].sum())
    print(f"Wrote Bourdillon method comparison outputs to: {output_dir.resolve()}")
    print("Compared personal/population baselines and one-/two-day confirmation.")
    print(f"Common-risk-set and confirmation-order audit violations: {violations}.")


def run_bourdillon_bootstrap(
    event_file: Path,
    output_dir: Path,
    replicates: int,
    seed: int,
    horizon_days: float,
) -> None:
    """Bootstrap recovery probability and time at the participant level."""

    if not event_file.exists():
        raise FileNotFoundError(f"Method-comparison event file not found: {event_file}")
    output_dir.mkdir(parents=True, exist_ok=True)
    events = pd.read_csv(event_file, low_memory=False)
    points = summarize_recovery_uncertainty_points(
        events,
        horizon_days=horizon_days,
    )
    bootstrap = cluster_bootstrap_recovery(
        events,
        replicates=replicates,
        seed=seed,
        horizon_days=horizon_days,
    )
    intervals = summarize_bootstrap_intervals(points, bootstrap)
    audit = audit_bootstrap_intervals(intervals)
    report = render_bootstrap_report(intervals, audit, seed=seed)

    points.to_csv(output_dir / "bourdillon_recovery_point_estimates.csv", index=False)
    bootstrap.to_csv(output_dir / "bourdillon_recovery_bootstrap_replicates.csv", index=False)
    intervals.to_csv(output_dir / "bourdillon_recovery_bootstrap_intervals.csv", index=False)
    audit.to_csv(output_dir / "bourdillon_recovery_bootstrap_audit.csv", index=False)
    (output_dir / "bourdillon_recovery_bootstrap_report.md").write_text(
        report, encoding="utf-8"
    )

    participants = events.loc[events["survival_eligible"], "participant_id"].nunique()
    violations = int(audit["violation"].sum())
    print(f"Wrote Bourdillon bootstrap outputs to: {output_dir.resolve()}")
    print(f"Completed {replicates:,} participant-cluster replicates ({participants} clusters).")
    print(f"Bootstrap interval audit violations: {violations}.")


def run_bourdillon_figures(
    hrv_file: Path,
    deviation_file: Path,
    event_file: Path,
    output_dir: Path,
) -> None:
    """Generate the four prespecified recovery figures."""

    input_files = (hrv_file, deviation_file, event_file)
    missing = [str(path) for path in input_files if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing figure input(s): " + ", ".join(missing))
    hrv = pd.read_csv(hrv_file, parse_dates=["date", "date_raw"], low_memory=False)
    deviations = pd.read_csv(
        deviation_file,
        parse_dates=["expected_date", "date"],
        low_memory=False,
    )
    events = pd.read_csv(event_file, low_memory=False)
    generate_core_figures(hrv, deviations, events, output_dir)
    print(f"Wrote four Bourdillon core figures to: {output_dir.resolve()}")
    print("Created both 300-dpi PNG and editable SVG versions.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="shiftrecover")
    subparsers = parser.add_subparsers(dest="command", required=True)
    demo = subparsers.add_parser("demo", help="run the synthetic-data method demo")
    demo.add_argument("--output-dir", type=Path, default=Path("results/demo"))
    demo.add_argument("--participants", type=int, default=24)
    demo.add_argument("--seed", type=int, default=20260914)
    mauvieux = subparsers.add_parser(
        "mauvieux",
        help="tidy the open Mauvieux phase-level sleep workbooks",
    )
    mauvieux.add_argument("--data-dir", type=Path, required=True)
    mauvieux.add_argument("--output-dir", type=Path, default=Path("results/mauvieux"))
    bourdillon = subparsers.add_parser(
        "bourdillon",
        help="ingest and audit the open Bourdillon RR interval files",
    )
    bourdillon.add_argument("--data-dir", type=Path, required=True)
    bourdillon.add_argument(
        "--output-dir", type=Path, default=Path("results/bourdillon")
    )
    bourdillon_hrv = subparsers.add_parser(
        "bourdillon-hrv",
        help="clean the Bourdillon RR table and calculate RMSSD and SDNN",
    )
    bourdillon_hrv.add_argument("--input-file", type=Path, required=True)
    bourdillon_hrv.add_argument(
        "--output-dir", type=Path, default=Path("results/bourdillon_hrv")
    )
    bourdillon_hrv.add_argument("--local-window", type=int, default=11)
    bourdillon_hrv.add_argument("--relative-threshold", type=float, default=0.20)
    bourdillon_hrv.add_argument("--robust-z-threshold", type=float, default=5.0)
    bourdillon_hrv.add_argument("--analysis-window-seconds", type=float, default=180.0)
    bourdillon_hrv.add_argument("--maximum-artifact-fraction", type=float, default=0.05)
    bourdillon_baseline = subparsers.add_parser(
        "bourdillon-baseline",
        help="estimate robust personal HRV baselines from QC-passing baseline days",
    )
    bourdillon_baseline.add_argument("--input-file", type=Path, required=True)
    bourdillon_baseline.add_argument(
        "--output-dir", type=Path, default=Path("results/bourdillon_baseline")
    )
    bourdillon_baseline.add_argument("--min-days", type=int, default=4)
    bourdillon_baseline.add_argument("--minimum-log-scale", type=float, default=0.05)
    bourdillon_baseline.add_argument("--range-multiplier", type=float, default=1.5)
    bourdillon_deviation = subparsers.add_parser(
        "bourdillon-deviation",
        help="calculate recovery-day 1-7 HRV deviations from personal baselines",
    )
    bourdillon_deviation.add_argument("--hrv-file", type=Path, required=True)
    bourdillon_deviation.add_argument("--baseline-file", type=Path, required=True)
    bourdillon_deviation.add_argument(
        "--output-dir", type=Path, default=Path("results/bourdillon_deviation")
    )
    bourdillon_deviation.add_argument("--max-recovery-day", type=int, default=7)
    bourdillon_recovery = subparsers.add_parser(
        "bourdillon-recovery",
        help="estimate first stable HRV recovery and right censoring",
    )
    bourdillon_recovery.add_argument("--deviation-file", type=Path, required=True)
    bourdillon_recovery.add_argument(
        "--output-dir", type=Path, default=Path("results/bourdillon_recovery")
    )
    bourdillon_recovery.add_argument("--threshold", type=float, default=1.5)
    bourdillon_recovery.add_argument("--consecutive-days", type=int, default=2)
    bourdillon_sensitivity = subparsers.add_parser(
        "bourdillon-sensitivity",
        help="repeat recovery estimation over at least three thresholds",
    )
    bourdillon_sensitivity.add_argument("--deviation-file", type=Path, required=True)
    bourdillon_sensitivity.add_argument(
        "--output-dir", type=Path, default=Path("results/bourdillon_sensitivity")
    )
    bourdillon_sensitivity.add_argument(
        "--thresholds", type=float, nargs="+", default=[0.75, 1.0, 1.5, 2.0]
    )
    bourdillon_sensitivity.add_argument("--consecutive-days", type=int, default=2)
    bourdillon_comparison = subparsers.add_parser(
        "bourdillon-comparison",
        help="compare personal/population baselines and one-/two-day recovery",
    )
    bourdillon_comparison.add_argument("--hrv-file", type=Path, required=True)
    bourdillon_comparison.add_argument("--personal-baseline-file", type=Path, required=True)
    bourdillon_comparison.add_argument("--personal-deviation-file", type=Path, required=True)
    bourdillon_comparison.add_argument(
        "--output-dir", type=Path, default=Path("results/bourdillon_comparison")
    )
    bourdillon_comparison.add_argument("--threshold", type=float, default=1.5)
    bourdillon_bootstrap = subparsers.add_parser(
        "bourdillon-bootstrap",
        help="bootstrap recovery probability and time by participant cluster",
    )
    bourdillon_bootstrap.add_argument("--event-file", type=Path, required=True)
    bourdillon_bootstrap.add_argument(
        "--output-dir", type=Path, default=Path("results/bourdillon_bootstrap")
    )
    bourdillon_bootstrap.add_argument("--replicates", type=int, default=2000)
    bourdillon_bootstrap.add_argument("--seed", type=int, default=20260914)
    bourdillon_bootstrap.add_argument("--horizon-days", type=float, default=7.0)
    bourdillon_figures = subparsers.add_parser(
        "bourdillon-figures",
        help="generate the four core recovery figures as PNG and SVG",
    )
    bourdillon_figures.add_argument("--hrv-file", type=Path, required=True)
    bourdillon_figures.add_argument("--deviation-file", type=Path, required=True)
    bourdillon_figures.add_argument("--event-file", type=Path, required=True)
    bourdillon_figures.add_argument(
        "--output-dir", type=Path, default=Path("docs/figures")
    )
    args = parser.parse_args()
    if args.command == "demo":
        run_demo(args.output_dir, args.participants, args.seed)
    elif args.command == "mauvieux":
        run_mauvieux(args.data_dir, args.output_dir)
    elif args.command == "bourdillon":
        run_bourdillon(args.data_dir, args.output_dir)
    elif args.command == "bourdillon-hrv":
        run_bourdillon_hrv(
            args.input_file,
            args.output_dir,
            args.local_window,
            args.relative_threshold,
            args.robust_z_threshold,
            args.analysis_window_seconds,
            args.maximum_artifact_fraction,
        )
    elif args.command == "bourdillon-baseline":
        run_bourdillon_baseline(
            args.input_file,
            args.output_dir,
            args.min_days,
            args.minimum_log_scale,
            args.range_multiplier,
        )
    elif args.command == "bourdillon-deviation":
        run_bourdillon_deviation(
            args.hrv_file,
            args.baseline_file,
            args.output_dir,
            args.max_recovery_day,
        )
    elif args.command == "bourdillon-recovery":
        run_bourdillon_recovery(
            args.deviation_file,
            args.output_dir,
            args.threshold,
            args.consecutive_days,
        )
    elif args.command == "bourdillon-sensitivity":
        run_bourdillon_sensitivity(
            args.deviation_file,
            args.output_dir,
            args.thresholds,
            args.consecutive_days,
        )
    elif args.command == "bourdillon-comparison":
        run_bourdillon_comparison(
            args.hrv_file,
            args.personal_baseline_file,
            args.personal_deviation_file,
            args.output_dir,
            args.threshold,
        )
    elif args.command == "bourdillon-bootstrap":
        run_bourdillon_bootstrap(
            args.event_file,
            args.output_dir,
            args.replicates,
            args.seed,
            args.horizon_days,
        )
    elif args.command == "bourdillon-figures":
        run_bourdillon_figures(
            args.hrv_file,
            args.deviation_file,
            args.event_file,
            args.output_dir,
        )


if __name__ == "__main__":
    main()
