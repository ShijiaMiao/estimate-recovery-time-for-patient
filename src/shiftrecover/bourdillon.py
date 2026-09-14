"""Ingest the open Bourdillon orthostatic-test RR interval dataset.

The source release contains one RR interval per line. Most recordings contain
the supine and standing portions in one file; a minority are already separated
with ``sup`` and ``std`` filename suffixes. This module preserves every source
interval, assigns posture transparently, and flags implausible intervals without
cleaning or interpolating them. Signal cleaning belongs to the HRV stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re

import numpy as np
import pandas as pd


PHASES = {
    "Baseline": ("baseline", 1),
    "Depriv": ("sleep_deprivation", 2),
    "Recov": ("recovery", 3),
}
POSTURES = {"sup": "supine", "std": "standing"}
RR_MIN_MS = 300.0
RR_MAX_MS = 2000.0

_FILENAME_PATTERN = re.compile(
    r"^(?P<participant>[A-Z]{3}\d{2})_?(?P<date>\d{8})(?P<posture>sup|std)?\.txt$",
    re.IGNORECASE,
)

# The three source filenames form an otherwise continuous 2016 sequence:
# baseline ends 2016-10-31 and recovery starts 2016-11-04. Preserve the source
# date in ``date_raw`` while exposing the corrected analysis date in ``date``.
DATE_CORRECTIONS = {
    ("BPJ93", "sleep_deprivation", "2013-11-01"): "2016-11-01",
    ("BPJ93", "sleep_deprivation", "2013-11-02"): "2016-11-02",
    ("BPJ93", "sleep_deprivation", "2013-11-03"): "2016-11-03",
}


@dataclass(frozen=True)
class SourceFile:
    """Metadata parsed from one source filename."""

    path: Path
    source_file: str
    participant_id: str
    date_raw: pd.Timestamp
    date: pd.Timestamp
    date_was_corrected: bool
    phase: str
    phase_order: int
    posture: str | None


def parse_bourdillon_filename(path: str | Path, data_directory: str | Path) -> SourceFile:
    """Parse participant, date, phase, and optional posture from a source path."""

    path = Path(path)
    data_directory = Path(data_directory)
    try:
        relative = path.relative_to(data_directory)
    except ValueError as exc:
        raise ValueError(f"File is outside the Bourdillon data directory: {path}") from exc
    if not relative.parts or relative.parts[0] not in PHASES:
        raise ValueError(f"Unknown Bourdillon phase folder: {relative}")

    match = _FILENAME_PATTERN.fullmatch(path.name)
    if match is None:
        raise ValueError(f"Unrecognized Bourdillon RR filename: {path.name}")

    participant = match.group("participant").upper()
    phase, phase_order = PHASES[relative.parts[0]]
    raw_date = pd.Timestamp(datetime.strptime(match.group("date"), "%Y%m%d").date())
    correction_key = (participant, phase, raw_date.strftime("%Y-%m-%d"))
    corrected = DATE_CORRECTIONS.get(correction_key)
    date = pd.Timestamp(corrected) if corrected else raw_date
    posture_code = match.group("posture")

    return SourceFile(
        path=path,
        source_file=relative.as_posix(),
        participant_id=participant,
        date_raw=raw_date,
        date=date,
        date_was_corrected=corrected is not None,
        phase=phase,
        phase_order=phase_order,
        posture=POSTURES[posture_code.lower()] if posture_code else None,
    )


def read_rr_values(path: str | Path) -> np.ndarray:
    """Read a headerless, one-value-per-line RR file in milliseconds."""

    path = Path(path)
    values: list[float] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8-sig", errors="strict").splitlines(), start=1
    ):
        value = line.strip()
        if not value:
            continue
        try:
            values.append(float(value.replace(",", ".")))
        except ValueError as exc:
            raise ValueError(f"Non-numeric RR value in {path} at line {line_number}") from exc
    if not values:
        raise ValueError(f"Empty RR file: {path}")
    result = np.asarray(values, dtype=float)
    if not np.isfinite(result).all():
        raise ValueError(f"Non-finite RR value in {path}")
    return result


def infer_test_protocol(total_duration_seconds: float) -> tuple[str, int]:
    """Classify a recording as the published 3-3 or 6-6 minute protocol."""

    if total_duration_seconds <= 0:
        raise ValueError("Recording duration must be positive")
    if total_duration_seconds < 9 * 60:
        return "3-3", 3
    return "6-6", 6


def split_combined_recording(
    rr_ms: np.ndarray, segment_minutes: int
) -> tuple[np.ndarray, np.ndarray]:
    """Split a combined recording at the protocol-defined posture-change time.

    Intervals ending at or before the 3- or 6-minute boundary are assigned to
    supine. Remaining intervals are assigned to standing. The assignment is an
    explicit protocol-time inference because the source file has no marker.
    """

    if rr_ms.ndim != 1 or len(rr_ms) < 2:
        raise ValueError("A combined recording needs at least two RR intervals")
    boundary_ms = segment_minutes * 60 * 1000
    split_index = int(np.searchsorted(np.cumsum(rr_ms), boundary_ms, side="right"))
    if split_index == 0 or split_index == len(rr_ms):
        raise ValueError("Protocol boundary falls outside the combined recording")
    return np.arange(split_index), np.arange(split_index, len(rr_ms))


def _discover_source_files(data_directory: Path) -> list[SourceFile]:
    if not data_directory.exists():
        raise FileNotFoundError(f"Bourdillon RR directory not found: {data_directory}")
    missing_phases = [folder for folder in PHASES if not (data_directory / folder).is_dir()]
    if missing_phases:
        raise FileNotFoundError("Missing Bourdillon phase folder(s): " + ", ".join(missing_phases))

    files = [
        parse_bourdillon_filename(path, data_directory)
        for folder in PHASES
        for path in sorted((data_directory / folder).rglob("*.txt"))
    ]
    if not files:
        raise FileNotFoundError(f"No Bourdillon RR text files found in: {data_directory}")
    return files


def _rr_records(
    source: SourceFile,
    rr_ms: np.ndarray,
    indices: np.ndarray,
    *,
    posture: str,
    posture_source: str,
    protocol: str,
    segment_minutes: int,
    posture_pair_complete: bool,
) -> list[dict[str, object]]:
    selected = rr_ms[indices]
    elapsed = np.cumsum(selected) / 1000.0
    records: list[dict[str, object]] = []
    for posture_index, (source_index, value, elapsed_seconds) in enumerate(
        zip(indices, selected, elapsed, strict=True), start=1
    ):
        below = bool(value < RR_MIN_MS)
        above = bool(value > RR_MAX_MS)
        if below:
            reason = "below_300_ms"
        elif above:
            reason = "above_2000_ms"
        else:
            reason = ""
        records.append(
            {
                "participant_id": source.participant_id,
                "date": source.date,
                "date_raw": source.date_raw,
                "date_was_corrected": source.date_was_corrected,
                "phase": source.phase,
                "phase_order": source.phase_order,
                "protocol": protocol,
                "protocol_segment_minutes": segment_minutes,
                "posture": posture,
                "posture_source": posture_source,
                "posture_pair_complete": posture_pair_complete,
                "source_rr_index": int(source_index) + 1,
                "posture_rr_index": posture_index,
                "elapsed_seconds_in_posture": elapsed_seconds,
                "rr_ms": value,
                "qc_out_of_range": below or above,
                "qc_reason": reason,
                "source_file": source.source_file,
            }
        )
    return records


def load_bourdillon_rr(data_directory: str | Path) -> pd.DataFrame:
    """Load all RR intervals into a standardized, posture-aware long table."""

    data_directory = Path(data_directory)
    sources = _discover_source_files(data_directory)
    grouped: dict[tuple[str, pd.Timestamp, str], list[SourceFile]] = {}
    for source in sources:
        key = (source.participant_id, source.date, source.phase)
        grouped.setdefault(key, []).append(source)

    records: list[dict[str, object]] = []
    for key, group in sorted(grouped.items(), key=lambda item: item[0]):
        combined = [source for source in group if source.posture is None]
        separated = [source for source in group if source.posture is not None]
        if combined and separated:
            raise ValueError(f"Both combined and separated files found for session: {key}")
        if len(combined) > 1:
            raise ValueError(f"Multiple combined files found for session: {key}")

        if combined:
            source = combined[0]
            values = read_rr_values(source.path)
            protocol, segment_minutes = infer_test_protocol(float(values.sum() / 1000.0))
            supine_indices, standing_indices = split_combined_recording(values, segment_minutes)
            records.extend(
                _rr_records(
                    source,
                    values,
                    supine_indices,
                    posture="supine",
                    posture_source="protocol_time_inferred",
                    protocol=protocol,
                    segment_minutes=segment_minutes,
                    posture_pair_complete=True,
                )
            )
            records.extend(
                _rr_records(
                    source,
                    values,
                    standing_indices,
                    posture="standing",
                    posture_source="protocol_time_inferred",
                    protocol=protocol,
                    segment_minutes=segment_minutes,
                    posture_pair_complete=True,
                )
            )
            continue

        by_posture: dict[str, SourceFile] = {}
        for source in separated:
            if source.posture in by_posture:
                raise ValueError(f"Duplicate {source.posture} file found for session: {key}")
            by_posture[source.posture] = source
        values_by_posture = {
            posture: read_rr_values(source.path) for posture, source in by_posture.items()
        }
        pair_complete = set(values_by_posture) == {"supine", "standing"}
        total_seconds = sum(float(values.sum() / 1000.0) for values in values_by_posture.values())
        if not pair_complete:
            total_seconds *= 2
        protocol, segment_minutes = infer_test_protocol(total_seconds)
        for posture in ("supine", "standing"):
            if posture not in values_by_posture:
                continue
            source = by_posture[posture]
            values = values_by_posture[posture]
            records.extend(
                _rr_records(
                    source,
                    values,
                    np.arange(len(values)),
                    posture=posture,
                    posture_source="filename_explicit",
                    protocol=protocol,
                    segment_minutes=segment_minutes,
                    posture_pair_complete=pair_complete,
                )
            )

    tidy = pd.DataFrame.from_records(records)
    day_table = tidy[["participant_id", "phase", "date"]].drop_duplicates()
    day_table = day_table.sort_values(["participant_id", "phase", "date"])
    day_table["phase_day_observed"] = day_table.groupby(
        ["participant_id", "phase"]
    ).cumcount() + 1
    first_dates = day_table.groupby(["participant_id", "phase"])["date"].transform("min")
    day_table["phase_day_calendar"] = (day_table["date"] - first_dates).dt.days + 1
    tidy = tidy.merge(day_table, on=["participant_id", "phase", "date"], how="left")
    tidy["recovery_day"] = pd.Series(pd.NA, index=tidy.index, dtype="Int64")
    recovery = tidy["phase"].eq("recovery")
    tidy.loc[recovery, "recovery_day"] = tidy.loc[recovery, "phase_day_calendar"].astype(
        "Int64"
    )
    tidy["phase_day_observed"] = tidy["phase_day_observed"].astype("Int64")
    tidy["phase_day_calendar"] = tidy["phase_day_calendar"].astype("Int64")
    return tidy.sort_values(
        ["participant_id", "date", "posture", "posture_rr_index"]
    ).reset_index(drop=True)


def summarize_bourdillon_sessions(tidy: pd.DataFrame) -> pd.DataFrame:
    """Create one audit row per participant-date-posture recording."""

    group_columns = [
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
        "source_file",
    ]
    audit = tidy.groupby(group_columns, dropna=False).agg(
        n_rr=("rr_ms", "size"),
        duration_seconds=("rr_ms", lambda values: values.sum() / 1000.0),
        rr_min_ms=("rr_ms", "min"),
        rr_median_ms=("rr_ms", "median"),
        rr_max_ms=("rr_ms", "max"),
        n_qc_out_of_range=("qc_out_of_range", "sum"),
    )
    audit = audit.reset_index()
    audit["qc_out_of_range_pct"] = 100 * audit["n_qc_out_of_range"] / audit["n_rr"]
    return audit.sort_values(["participant_id", "date", "posture"]).reset_index(drop=True)


def summarize_bourdillon_participants(tidy: pd.DataFrame) -> pd.DataFrame:
    """Summarize observed days in each phase for every participant."""

    days = tidy[["participant_id", "phase", "date"]].drop_duplicates()
    coverage = days.pivot_table(
        index="participant_id", columns="phase", values="date", aggfunc="nunique", fill_value=0
    ).reset_index()
    coverage.columns.name = None
    for phase in ("baseline", "sleep_deprivation", "recovery"):
        if phase not in coverage:
            coverage[phase] = 0
        coverage = coverage.rename(columns={phase: f"{phase}_days"})
    day_columns = ["baseline_days", "sleep_deprivation_days", "recovery_days"]
    coverage["has_all_three_phases"] = coverage[day_columns].gt(0).all(axis=1)
    coverage["total_observed_days"] = coverage[day_columns].sum(axis=1)
    return coverage[
        ["participant_id", *day_columns, "total_observed_days", "has_all_three_phases"]
    ].sort_values("participant_id").reset_index(drop=True)


def render_bourdillon_ingestion_report(
    tidy: pd.DataFrame, sessions: pd.DataFrame, participants: pd.DataFrame
) -> str:
    """Render a concise Markdown audit report from generated tables."""

    unique_days = tidy[["participant_id", "date"]].drop_duplicates().shape[0]
    corrected = tidy.loc[tidy["date_was_corrected"], "source_file"].nunique()
    flagged = int(tidy["qc_out_of_range"].sum())
    explicit_days = sessions.loc[
        sessions["posture_source"].eq("filename_explicit"),
        ["participant_id", "date"],
    ].drop_duplicates().shape[0]
    inferred_days = sessions.loc[
        sessions["posture_source"].eq("protocol_time_inferred"),
        ["participant_id", "date"],
    ].drop_duplicates().shape[0]
    complete = int(participants["has_all_three_phases"].sum())
    return f"""# Bourdillon RR ingestion audit

Generated by `python -m shiftrecover.cli bourdillon`.

## Coverage

- Participants found: **{participants.shape[0]}**
- Participants with all three phases: **{complete}**
- Participant-days found: **{unique_days}**
- RR intervals preserved: **{len(tidy)}**
- Explicitly separated participant-days: **{explicit_days}**
- Protocol-time separated participant-days: **{inferred_days}**

## Data-quality flags

- Source filenames with documented date corrections: **{corrected}**
- RR intervals outside {RR_MIN_MS:.0f}–{RR_MAX_MS:.0f} ms: **{flagged}**
- Incomplete explicit supine/standing pairs: **{int((~sessions['posture_pair_complete']).sum())}**

Out-of-range intervals are flagged but retained. No ectopic-beat removal,
interpolation, or HRV computation is performed during ingestion.

Combined recordings have no posture marker. They are split at the published
3- or 6-minute protocol boundary and labelled `protocol_time_inferred`; this
assumption must remain visible in downstream sensitivity analyses.
"""
