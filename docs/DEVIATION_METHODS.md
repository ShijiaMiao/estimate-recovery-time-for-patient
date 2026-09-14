# Recovery-day HRV deviation specification

## Complete day grid

The pipeline creates recovery days 1–7 for every participant and posture found
in the personal baseline table. It does not restrict the output to dates with a
recording. Consequently, missing observations, failed sessions, insufficient
baselines, and absence of post-baseline data remain visible.

Recovery day 1 is the first date of the dataset's recovery phase. Later calendar
days are aligned to that anchor; an unobserved date is retained as an explicit
`missing_observation` row.

## Metric-level deviations

For RMSSD and SDNN separately:

```text
log ratio       = log(observed HRV) - personal log-baseline centre
signed z        = log ratio / personal robust log-scale
absolute z      = abs(signed z)
percent change  = 100 x (observed HRV / personal centre - 1)
```

A positive signed value means HRV is above that person's baseline centre; a
negative value means it is below. `within_personal_range` is true when the
absolute standardized deviation is no larger than the baseline range multiplier
(1.5 in the primary specification).

## Composite deviation

When both metric deviations are available:

```text
HRV deviation score = sqrt(mean(RMSSD absolute z^2, SDNN absolute z^2))
```

The uncapped metric-level values remain in the output. Missing RMSSD or SDNN does
not produce a composite score. The composite is a methodological summary, not a
validated clinical measurement.

## Status hierarchy

Each row receives one mutually exclusive status:

- `calculated`;
- `missing_observation`;
- `session_qc_failed`;
- `missing_or_invalid_metric`;
- `insufficient_baseline`;
- `no_postbaseline_data`.

No missing day is filled or counted as recovery. This is necessary for the next
stage, where recovery events and right censoring are defined.
