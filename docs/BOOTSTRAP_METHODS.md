# Bootstrap uncertainty methods

## Why uncertainty is needed

A recovery proportion or median recovery day calculated from one small sample
is a point estimate, not an exact population value. This stage uses bootstrap
resampling to show how much the estimate could vary if a similar set of
participants had been observed.

## Resampling unit

The participant is the sampling cluster. A sampled participant contributes all
available standing and supine records, all endpoints, and all four method
strategies. Participants are sampled with replacement until the original
number of participants is reached.

This preserves dependence between measurements from the same person and keeps
the four strategies paired within every bootstrap replicate. Resampling
participant-posture rows independently would incorrectly treat correlated
measurements as unrelated observations.

## Prespecified implementation

- Number of replicates: 2,000.
- Random seed: 20260914.
- Follow-up horizon: 7 days.
- Confidence level: 95%.
- Interval method: percentile bootstrap using the 2.5th and 97.5th percentiles.
- Stratification: baseline method, confirmation rule, endpoint, and posture;
  an additional `all` posture result combines both postures while retaining
  participant-level cluster sampling.

## Reported statistics

For every stratum, the pipeline reports:

1. crude observed recovery proportion;
2. Kaplan–Meier cumulative recovery probability by the 7-day horizon;
3. Kaplan–Meier median recovery day; and
4. restricted mean time to recovery through day 7.

The restricted mean is the area under the Kaplan–Meier non-recovery curve from
day 0 to day 7. Unlike the median, it remains estimable when fewer than half of
a bootstrap sample demonstrate recovery.

## Right censoring

Kaplan–Meier calculations use `analysis_time_days` and `event_observed` from the
stage-7 event table. A recovery contributes an event at its first confirmed
recovery day. An unrecovered series contributes a censoring time at its last
evaluable follow-up day.

If a bootstrap replicate never reaches 50% cumulative recovery, its KM median
is undefined and is not replaced with day 7. The output records the number and
fraction of finite median replicates. A finite fraction below 90% is an explicit
warning; it is not treated as a calculation failure.

## Audit rules

The audit checks that:

- lower confidence limits do not exceed upper limits;
- probability intervals remain between 0 and 1; and
- at least 90% of replicates yield each statistic, reported as a warning when
  the KM median is frequently not reached.

## Outputs

- `bourdillon_recovery_point_estimates.csv`: original-sample estimates;
- `bourdillon_recovery_bootstrap_replicates.csv`: every replicate estimate;
- `bourdillon_recovery_bootstrap_intervals.csv`: long-form point estimates,
  standard errors, percentile intervals and valid-replicate counts;
- `bourdillon_recovery_bootstrap_audit.csv`: errors and finite-median warnings;
  and
- `bourdillon_recovery_bootstrap_report.md`: primary four-strategy results.

## Interpretation limits

These intervals describe sampling uncertainty under participant resampling.
They do not account for uncertainty introduced earlier when estimating each
personal baseline from a limited number of days, and they do not validate the
1.5 recovery threshold clinically. With only a small number of participant
clusters, intervals should be interpreted as descriptive rather than definitive.
