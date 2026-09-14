# Time-domain HRV processing specification

## Scope

This stage converts posture-specific Bourdillon RR intervals to corrected NN
intervals and calculates RMSSD and SDNN. It is an auditable preprocessing
implementation, not a medical diagnostic pipeline and not an exact recreation
of the authors' unavailable MATLAB settings.

The source study states that ectopic or missing beats were identified,
interpolated, and analysed separately for supine and standing recordings:

<https://doi.org/10.3389/fnins.2021.642548>

RMSSD and SDNN follow the standard time-domain definitions described by the
1996 ESC/NASPE Task Force:

<https://pubmed.ncbi.nlm.nih.gov/8598068/>

## Prespecified pipeline

For each participant, date, and posture:

1. Preserve the original `rr_ms` value.
2. Flag values outside 300–2000 ms.
3. Calculate a centred 11-beat rolling median.
4. Calculate the robust scale of residuals from that local median using MAD.
5. Flag a local candidate only when its absolute deviation exceeds both 20% of
   the local median and five robust residual standard deviations.
6. Replace flagged intervals by linear interpolation across beat index, storing
   the result as `nn_ms` and retaining the reason and correction magnitude.
7. Use the first 180 seconds of each posture so 3–3 and 6–6 tests have the same
   analysis duration.
8. Calculate RMSSD as the square root of the mean squared successive NN
   differences and SDNN as the sample standard deviation of NN intervals.

Artefacts can materially distort HRV estimates, motivating explicit detection
and sensitivity analysis. A more sophisticated published example is Lipponen
and Tarvainen's time-varying-threshold classification algorithm:

<https://pubmed.ncbi.nlm.nih.gov/31314618/>

The present project does not claim to implement that proprietary-software
workflow. Its simpler rule is intentionally visible, configurable, and covered
by automated tests.

## Session-level quality control

A participant-date-posture series fails the primary QC when any of the following
is true:

- fewer than 60 intervals are available in the analysis window;
- the analysis window contains less than 150 seconds;
- more than 5% of intervals are flagged;
- fewer than two finite NN intervals remain.

Failed series are never silently removed. They remain in
`bourdillon_daily_hrv.csv` with `qc_pass = False`, a populated `qc_status`, and
missing HRV estimates.

## Outputs

- `bourdillon_nn_cleaned.csv`: interval-level RR, flag, interpolation, and NN
  audit trail.
- `bourdillon_daily_hrv.csv`: one row per participant-date-posture with RMSSD,
  SDNN, mean NN, mean heart rate, and QC fields.
- `bourdillon_hrv_qc_summary.csv`: phase-by-posture processing summary.
- `bourdillon_hrv_report.md`: compact run-specific audit report.

The 20% local threshold, robust scale multiplier, 5% session threshold, and
analysis-window duration should later be varied in sensitivity analyses.
