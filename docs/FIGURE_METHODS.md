# Core figure methods

## Figure 1: experiment timeline

The timeline represents the prespecified protocol as seven baseline days,
three partial-sleep-deprivation days and seven recovery days. Circle area and
the printed number show how many participants have at least one QC-passing
posture series on that phase day. The dashed line marks the start of recovery
follow-up.

The display is protocol-relative because participants entered the experiment
on different calendar dates. It does not imply that every participant has a
valid recording on every displayed day.

## Figure 2: individual recovery trajectories

Each line is one eligible participant-posture series scored against its own HRV
baseline. The green dashed line is the composite-deviation threshold of 1.5;
the shaded area is the operational recovered range. A green diamond marks the
first day of a two-consecutive-day recovery pair. A red cross marks the last
observed day for a series that did not demonstrate recovery and was therefore
right-censored.

Lines are separated into standing and supine panels because posture has a
strong influence on HRV. Missing and QC-failed observations create gaps rather
than interpolated recovery values.

## Figure 3: participant recovery heatmap

Rows are eligible participant-posture series and columns are recovery days
1–7. Colour represents the personal composite HRV deviation score, clipped at
5 only for visual scaling; the underlying calculations retain the original
values. Grey cells are missing or QC-failed observations. `R` marks the first
confirmed recovery day under the primary personal-baseline, two-day rule.

Rows are sorted first by event status and then by recovery day. The heatmap is
intended to expose individual heterogeneity and missingness that group averages
can conceal.

## Figure 4: Kaplan–Meier recovery curves

The curves show cumulative probability of confirmed recovery for the four
combinations of personal or population-average baseline and one-day or two-day
confirmation. The denominator is the common 26-series risk set used in the
stage-7 comparison.

Standing and supine observations are displayed together for the descriptive
curve. They are not treated as independent during uncertainty estimation:
stage 8 resamples both observations together at the participant-cluster level.

## Formats and reproducibility

Every figure is produced in two formats:

- 300-dpi PNG for GitHub and presentations; and
- SVG for lossless editing and publication workflows.

All plotting code is in `src/shiftrecover/plotting.py`. The files can be
regenerated with the `bourdillon-figures` command documented in the README.
