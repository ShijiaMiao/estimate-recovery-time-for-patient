# Bourdillon ingestion data dictionary

## `bourdillon_rr_tidy.csv`

Each row is one source RR interval. Ingestion preserves the raw value and adds
metadata; it does not remove ectopic beats or interpolate NN intervals.

| Column | Meaning |
|---|---|
| `participant_id` | Pseudonymous source participant identifier |
| `date` | Analysis date, including documented corrections |
| `date_raw` | Date parsed literally from the source filename |
| `date_was_corrected` | Whether `date` differs from `date_raw` |
| `phase` | `baseline`, `sleep_deprivation`, or `recovery` |
| `phase_order` | Chronological phase order, 1–3 |
| `protocol` | Published `3-3` or `6-6` minute orthostatic protocol |
| `protocol_segment_minutes` | Planned minutes in each posture |
| `posture` | `supine` or `standing` |
| `posture_source` | Explicit filename label or protocol-time inference |
| `posture_pair_complete` | Whether both postures are present for that session |
| `source_rr_index` | One-based interval position in the source file |
| `posture_rr_index` | One-based interval position within the assigned posture |
| `elapsed_seconds_in_posture` | Cumulative RR time within the posture |
| `rr_ms` | Original RR interval in milliseconds |
| `qc_out_of_range` | Whether RR is outside the ingestion screen of 300–2000 ms |
| `qc_reason` | Empty, `below_300_ms`, or `above_2000_ms` |
| `source_file` | Source path relative to the downloaded `RR` directory |
| `phase_day_observed` | Rank among observed dates in that phase |
| `phase_day_calendar` | Calendar days since that participant's first phase date |
| `recovery_day` | Calendar day of recovery phase; missing outside recovery |

## Audit outputs

- `bourdillon_session_audit.csv`: one row per participant, date, and posture,
  including duration, RR distribution, and QC counts.
- `bourdillon_participant_coverage.csv`: number of observed days in each phase
  and an indicator for presence of all three phases.
- `bourdillon_ingestion_report.md`: compact run-specific coverage and QC report.

## Explicit assumptions

The source paper specifies a supine segment immediately followed by a standing
segment, lasting either 3 minutes each or 6 minutes each. Combined source files
contain no posture marker. The adapter classifies the protocol from total
duration and places the boundary at cumulative minute 3 or 6. These rows carry
`posture_source = protocol_time_inferred` so downstream sensitivity analysis can
distinguish them from explicitly separated source files.

Three `BPJ93` deprivation filenames contain year 2013 between October and
November 2016 phases. The adapter applies the transparent corrections
2013-11-01/02/03 to 2016-11-01/02/03 while retaining the filename dates in
`date_raw`.
