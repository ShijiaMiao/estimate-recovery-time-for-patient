"""Reader for the openly available Mauvieux (2025) sleep tables.

The released workbooks contain participant-level values aggregated into three
study phases. They do not contain participant-day timestamps. Consequently,
this adapter supports phase comparison but not day-level recovery estimation.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


PHASES = {
    "ZT1": {
        "order": 1,
        "label": "weekend_recovery",
        "window": "Friday noon to Sunday night",
    },
    "ZT2": {
        "order": 2,
        "label": "first_72h_night_work",
        "window": "Sunday night to Wednesday noon",
    },
    "ZT3": {
        "order": 3,
        "label": "late_week_night_work",
        "window": "Wednesday noon to Friday morning",
    },
}

METRICS = ["time_in_bed_min", "total_sleep_time_min", "sleep_onset_latency_min", "waso_min", "sleep_efficiency"]
PHASE_START_COLUMNS = {"ZT1": 3, "ZT2": 8, "ZT3": 13}


def _extract_sleep_block(
    sheet: pd.DataFrame,
    *,
    start_row: int,
    end_row: int,
    study: str,
    group: str,
    condition: str,
    participant_prefix: str,
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for row_number in range(start_row, end_row + 1):
        subject = pd.to_numeric(sheet.iat[row_number, 2], errors="coerce")
        if pd.isna(subject):
            continue
        subject_int = int(subject)
        for phase, start_column in PHASE_START_COLUMNS.items():
            values = [
                pd.to_numeric(sheet.iat[row_number, start_column + offset], errors="coerce")
                for offset in range(5)
            ]
            record = {
                "study": study,
                "participant_id": f"{participant_prefix}{subject_int:02d}",
                "source_subject_id": subject_int,
                "group": group,
                "condition": condition,
                "phase": phase,
                "phase_order": PHASES[phase]["order"],
                "phase_label": PHASES[phase]["label"],
                "phase_window": PHASES[phase]["window"],
            }
            record.update(dict(zip(METRICS, values, strict=True)))
            records.append(record)
    return pd.DataFrame.from_records(records)


def load_mauvieux_sleep(data_directory: str | Path) -> pd.DataFrame:
    """Load and tidy both participant-level sleep-quality workbooks."""

    data_directory = Path(data_directory)
    study1_path = data_directory / "Table 3 Sleep Quality.xlsx"
    study2_path = data_directory / "Table 5 Sleep Quality Study 2.xlsx"
    missing = [str(path) for path in (study1_path, study2_path) if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing Mauvieux workbook(s): " + ", ".join(missing))

    study1 = pd.read_excel(study1_path, sheet_name="Table 3", header=None)
    study2 = pd.read_excel(study2_path, sheet_name="Table 5", header=None)

    tidy = pd.concat(
        [
            _extract_sleep_block(
                study1,
                start_row=6,
                end_row=17,
                study="study_1_cross_sectional",
                group="physically_active",
                condition="observed",
                participant_prefix="S1_PA_",
            ),
            _extract_sleep_block(
                study1,
                start_row=21,
                end_row=32,
                study="study_1_cross_sectional",
                group="sedentary",
                condition="observed",
                participant_prefix="S1_S_",
            ),
            _extract_sleep_block(
                study2,
                start_row=6,
                end_row=21,
                study="study_2_training",
                group="sedentary",
                condition="pre_training",
                participant_prefix="S2_",
            ),
            _extract_sleep_block(
                study2,
                start_row=25,
                end_row=40,
                study="study_2_training",
                group="sedentary",
                condition="post_training",
                participant_prefix="S2_",
            ),
        ],
        ignore_index=True,
    )
    tidy["sleep_efficiency_pct"] = tidy["sleep_efficiency"] * 100.0
    tidy = tidy.drop(columns="sleep_efficiency")
    return tidy.sort_values(["study", "participant_id", "condition", "phase_order"]).reset_index(drop=True)


def summarize_mauvieux_sleep(tidy: pd.DataFrame) -> pd.DataFrame:
    """Return transparent descriptive summaries by study group and phase."""

    grouping = ["study", "group", "condition", "phase", "phase_order", "phase_label"]
    metrics = [*METRICS[:-1], "sleep_efficiency_pct"]
    summary = tidy.groupby(grouping, dropna=False)[metrics].agg(["count", "mean", "std"])
    summary.columns = [f"{metric}__{stat}" for metric, stat in summary.columns]
    return summary.reset_index().sort_values(["study", "group", "condition", "phase_order"])

