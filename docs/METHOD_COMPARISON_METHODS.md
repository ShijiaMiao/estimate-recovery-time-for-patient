# Baseline and recovery-rule comparison

## Purpose

This analysis tests whether an estimated recovery time changes when either of
two operational choices is changed:

1. the reference is the participant's own baseline or a population-average
   baseline; and
2. recovery requires one qualifying day or two consecutive qualifying days.

It is a method comparison, not a clinical validation of the threshold.

## Common risk set

All four strategies are evaluated on the same participant-posture series. The
common risk set is fixed by the eligibility criteria for the personal-baseline
analysis: adequate baseline coverage and at least one calculable recovery day.
This prevents a method from appearing better merely because it analysed an
easier or different subset of observations.

## Baseline strategies

### Personal baseline

The personal method uses the robust log-scale centre and scale estimated from
each participant's QC-passing baseline days, as specified in
`BASELINE_METHODS.md`.

### Population-average baseline

For each posture and HRV metric, every baseline-sufficient participant
contributes one personal log-scale centre. The population centre is their
arithmetic mean on the log scale, equivalent to a geometric mean on the raw
millisecond scale. The population scale is the sample standard deviation of
those participant centres, with a minimum log-scale value of 0.05.

Giving each participant one contribution prevents participants with more
baseline days from receiving greater weight. The resulting population
reference is then applied to every series in the common risk set.

## Recovery rules

The comparison holds the composite-deviation threshold at 1.5 and follows
recovery days 1–7. It evaluates the full 2 x 2 design:

| Baseline | Confirmation rule |
|---|---|
| Personal | One qualifying day |
| Personal | Two consecutive qualifying days |
| Population average | One qualifying day |
| Population average | Two consecutive qualifying days |

A qualifying day has an absolute standardized deviation at or below the fixed
threshold. Under the two-day rule, the recorded recovery time is the first day
of the first qualifying pair. Eligible series without a confirmed event remain
right-censored.

The prespecified primary strategy is the personal baseline with two-day
confirmation. The alternatives are sensitivity comparisons.

## Paired comparisons

Results are compared within the same participant and posture. The discordance
table distinguishes:

- both methods recovering on the same day;
- one method recovering earlier;
- recovery under only one method; and
- right-censoring under both methods.

This paired view is necessary because equal group-level recovery proportions
can hide disagreement about which individuals recovered and when.

## Logical audit

The pipeline automatically checks that:

- personal and population methods have identical eligibility within each
  endpoint and confirmation rule; and
- a two-day confirmation rule never produces an earlier recovery day than its
  corresponding one-day rule.

Any failed check is written as an explicit audit violation.

## Outputs

- `bourdillon_population_hrv_baselines.csv`: posture-specific population
  references and contributor counts;
- `bourdillon_population_recovery_deviation.csv`: recovery observations scored
  against the population reference;
- `bourdillon_method_comparison_events.csv`: event-level results for all four
  strategies and all endpoints;
- `bourdillon_method_comparison_summary.csv`: counts, observed proportions and
  median recovery day among recovered series;
- `bourdillon_method_comparison_paired.csv`: four strategy results side by side;
- `bourdillon_method_comparison_discordance.csv`: paired disagreement counts;
- `bourdillon_method_comparison_audit.csv`: row-level logical checks; and
- `bourdillon_method_comparison_report.md`: concise primary-result report.

## Interpretation limits

The population reference is deliberately a transparent comparison method, not
a claim that one HRV range is normal for everyone. The threshold is an
operational research definition. The small experimental sample, short recovery
window, posture-specific measurements, and absence of an external clinical
recovery standard limit biological and clinical interpretation.
