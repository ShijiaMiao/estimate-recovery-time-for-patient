# Recovery-threshold sensitivity specification

## Purpose

The personal HRV deviation threshold is an operational method choice rather
than a validated clinical boundary. The sensitivity analysis therefore repeats
the complete recovery-event algorithm under four prespecified thresholds:

```text
0.75, 1.0, 1.5, and 2.0 robust deviation units
```

Threshold 1.5 remains the primary specification. A smaller threshold is more
strict because the participant must be closer to their personal baseline.

## Conditions held constant

Only the threshold changes. Every run keeps the following fixed:

- participant- and posture-specific personal baselines;
- the RMSSD/SDNN composite definition;
- two consecutive calendar days required for recovery;
- recovery days 1–7;
- missing and failed-QC days breaking consecutiveness;
- right censoring at the last evaluable day;
- the same analysis risk set.

This one-factor-at-a-time design makes differences interpretable as threshold
sensitivity. Personal versus population baseline and one-day versus two-day
recovery definitions belong to the next comparison stage.

## Outputs

- `bourdillon_threshold_sensitivity_events.csv`: all participant, posture,
  endpoint, and threshold combinations.
- `bourdillon_threshold_sensitivity_summary.csv`: recovered and censored counts
  by threshold, endpoint, and posture.
- `bourdillon_threshold_stability_matrix.csv`: one composite-endpoint row per
  participant and posture, with all threshold-specific results side by side.
- `bourdillon_threshold_monotonicity_audit.csv`: automated logical audit.
- `bourdillon_threshold_sensitivity_report.md`: compact primary-endpoint report.

## Monotonicity audit

For the same series, relaxing a threshold cannot turn an observed event into a
non-event or move recovery to a later day. Any such result indicates an
implementation error. Passing this audit confirms internal consistency; it does
not identify a clinically correct threshold.
