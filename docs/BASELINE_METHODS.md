# Personal HRV baseline specification

## Analysis unit

A separate baseline is estimated for every participant and posture. Supine and
standing HRV are not pooled because posture changes autonomic physiology.

Only observations satisfying all of the following are eligible:

- `phase == baseline`;
- the posture series passed the prespecified HRV QC;
- RMSSD and SDNN are finite and positive.

At least four eligible baseline dates are required. A combination with fewer
dates is labelled `insufficient_baseline`; no centre or normal range is forced.

## Robust estimation

RMSSD and SDNN are positive and commonly right-skewed, so each metric is
transformed with the natural logarithm before estimation.

For each metric:

```text
personal centre = median(log(HRV))
personal scale  = 1.4826 x MAD(log(HRV))
normal range    = centre +/- 1.5 x personal scale
```

The centre and range are then exponentiated and reported in milliseconds. A
minimum scale of 0.05 log units prevents an unrealistically zero denominator
when a small baseline sample contains nearly identical values. Whether this
floor was used is retained in the output.

The multiplier 1.5 is the primary project definition, not a clinical cut-off.
Later sensitivity analyses must repeat recovery estimation under alternative
multipliers or standardized-deviation thresholds.

## Outputs and status fields

- `bourdillon_baseline_observations.csv` records every baseline series and its
  eligibility or exclusion reason.
- `bourdillon_personal_hrv_baselines.csv` contains centres, log scales, normal
  limits, counts, and readiness status.
- `bourdillon_baseline_report.md` provides the run-specific coverage audit.

`eligible_for_recovery_analysis` requires both a sufficient personal baseline
and at least one QC-passing post-baseline observation. A participant may
therefore have a valid baseline but still be unavailable for recovery analysis.
