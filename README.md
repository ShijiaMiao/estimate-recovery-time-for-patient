# ShiftRecoverPy

**Personalized estimation of post-shift recovery from longitudinal wearable data**

ShiftRecoverPy is a reproducible Python toolkit for estimating how many days an
individual needs to return to their own baseline after a block of shift work.
The project is motivated by research on temporal eating patterns during shift
work and extends the same sequence-based idea to wearable sleep, heart-rate and
activity data.

The key question is not whether the average night worker differs from the
average day worker. It is:

> After the final shift in a work block, on which day does this person return
> to their usual physiological and behavioural range?

## Current status

Version `0.1.0` is a working method prototype. It currently provides:

- a transparent 28-day synthetic shift-work dataset;
- robust participant-specific baselines;
- correct circular calculations for clock-time variables;
- a multivariable daily deviation score;
- recovery detection requiring two consecutive recovered days;
- censoring when recovery cannot be observed before the next work block;
- unit tests for clock arithmetic and recovery detection.

The first open-data adapter reads the participant-level Mauvieux sleep
tables. Inspection of the released files showed that observations are aggregated
into three study phases rather than participant-days. The adapter therefore
supports transparent phase comparisons but deliberately refuses to describe the
result as a day-level recovery-time estimate.

The Bourdillon adapter now ingests real daily RR-interval recordings from a
baseline–partial-sleep-deprivation–recovery experiment. It handles combined and
posture-separated files, preserves raw values, flags rather than silently removes
questionable intervals, and produces session and participant coverage audits.
The second processing stage creates an interval-level RR-to-NN audit trail and
calculates quality-controlled RMSSD and SDNN separately for each posture.
The third stage estimates robust personal HRV centres and operational normal
ranges from QC-passing baseline dates.
The fourth stage aligns recovery days 1–7 and calculates signed, absolute, and
composite deviations from those personal baselines without filling missing days.
The fifth stage identifies the first of two consecutive recovered days and
retains unrecovered eligible series as right-censored observations.
The sixth stage repeats that algorithm under four recovery thresholds and
automatically audits the expected threshold monotonicity.
The seventh stage compares personal versus population-average baselines and
one-day versus two-day confirmation on one fixed, paired risk set.
The eighth stage uses participant-cluster bootstrap resampling to attach
uncertainty intervals to recovery proportions and time-to-recovery summaries.
The ninth stage generates four reproducible core figures in GitHub-ready PNG
and editable SVG formats.
The tenth stage provides 67 automated tests, an 80% coverage gate and GitHub
Actions checks on Python 3.10 and 3.12; current core-library coverage is 87%.

## Why personal baselines?

There is no single normal bedtime, resting heart rate, or number of steps for
every person. ShiftRecoverPy therefore compares each participant with their own
stable off-duty observations. Baselines are estimated with robust statistics so
that one unusual day does not dominate the result.

Clock times are treated as circular. For example, 23:30 and 00:30 are one hour
apart, not 23 hours apart.

## Quick start

Python 3.10 or newer is recommended.

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m shiftrecover.cli demo --output-dir results/demo
python -m unittest discover -s tests -v
```

After downloading and extracting the Mauvieux files:

```bash
python -m shiftrecover.cli mauvieux \
  --data-dir "data/Exercise, circadian rhythms & night work" \
  --output-dir results/mauvieux
```

After downloading the Bourdillon RR release:

```bash
python -m shiftrecover.cli bourdillon \
  --data-dir "data/raw/bourdillon_2020/RR" \
  --output-dir results/bourdillon

python -m shiftrecover.cli bourdillon-hrv \
  --input-file "results/bourdillon/bourdillon_rr_tidy.csv" \
  --output-dir results/bourdillon_hrv

python -m shiftrecover.cli bourdillon-baseline \
  --input-file "results/bourdillon_hrv/bourdillon_daily_hrv.csv" \
  --output-dir results/bourdillon_baseline

python -m shiftrecover.cli bourdillon-deviation \
  --hrv-file "results/bourdillon_hrv/bourdillon_daily_hrv.csv" \
  --baseline-file "results/bourdillon_baseline/bourdillon_personal_hrv_baselines.csv" \
  --output-dir results/bourdillon_deviation

python -m shiftrecover.cli bourdillon-recovery \
  --deviation-file "results/bourdillon_deviation/bourdillon_recovery_daily_deviation.csv" \
  --output-dir results/bourdillon_recovery \
  --threshold 1.5 \
  --consecutive-days 2

python -m shiftrecover.cli bourdillon-sensitivity \
  --deviation-file "results/bourdillon_deviation/bourdillon_recovery_daily_deviation.csv" \
  --output-dir results/bourdillon_sensitivity \
  --thresholds 0.75 1.0 1.5 2.0 \
  --consecutive-days 2

python -m shiftrecover.cli bourdillon-comparison \
  --hrv-file "results/bourdillon_hrv/bourdillon_daily_hrv.csv" \
  --personal-baseline-file "results/bourdillon_baseline/bourdillon_personal_hrv_baselines.csv" \
  --personal-deviation-file "results/bourdillon_deviation/bourdillon_recovery_daily_deviation.csv" \
  --output-dir results/bourdillon_comparison \
  --threshold 1.5

python -m shiftrecover.cli bourdillon-bootstrap \
  --event-file "results/bourdillon_comparison/bourdillon_method_comparison_events.csv" \
  --output-dir results/bourdillon_bootstrap \
  --replicates 2000 \
  --seed 20260914 \
  --horizon-days 7

python -m shiftrecover.cli bourdillon-figures \
  --hrv-file "results/bourdillon_hrv/bourdillon_daily_hrv.csv" \
  --deviation-file "results/bourdillon_deviation/bourdillon_recovery_daily_deviation.csv" \
  --event-file "results/bourdillon_comparison/bourdillon_method_comparison_events.csv" \
  --output-dir docs/figures
```

The Bourdillon command creates a posture-aware interval table, a session-level
QC audit, participant phase coverage, and a Markdown ingestion report. The
second command flags suspected artefacts, creates interpolated NN intervals,
and calculates RMSSD and SDNN using a standardized three-minute posture window.
See [`docs/HRV_METHODS.md`](docs/HRV_METHODS.md) for the complete specification.
Personal baseline eligibility and robust range construction are documented in
[`docs/BASELINE_METHODS.md`](docs/BASELINE_METHODS.md).
Recovery-day alignment and deviation formulas are documented in
[`docs/DEVIATION_METHODS.md`](docs/DEVIATION_METHODS.md).
First recovery and right-censoring rules are documented in
[`docs/RECOVERY_EVENT_METHODS.md`](docs/RECOVERY_EVENT_METHODS.md).
Threshold sensitivity and its logical audit are documented in
[`docs/THRESHOLD_SENSITIVITY_METHODS.md`](docs/THRESHOLD_SENSITIVITY_METHODS.md).
The paired baseline and confirmation-rule comparison is documented in
[`docs/METHOD_COMPARISON_METHODS.md`](docs/METHOD_COMPARISON_METHODS.md).
Participant-cluster resampling and uncertainty statistics are documented in
[`docs/BOOTSTRAP_METHODS.md`](docs/BOOTSTRAP_METHODS.md).
Figure construction and interpretation are documented in
[`docs/FIGURE_METHODS.md`](docs/FIGURE_METHODS.md).
The test matrix, coverage scope and quality checks are documented in
[`docs/TESTING.md`](docs/TESTING.md).

## Core figures

### Experimental timeline

![Bourdillon experimental timeline](docs/figures/figure_1_experiment_timeline.png)

### Individual recovery trajectories

![Individual recovery trajectories](docs/figures/figure_2_individual_recovery_trajectories.png)

### Participant recovery heatmap

![Participant recovery heatmap](docs/figures/figure_3_participant_recovery_heatmap.png)

### Kaplan–Meier recovery comparison

![Kaplan–Meier recovery curves](docs/figures/figure_4_kaplan_meier_recovery.png)

The demo creates:

- `synthetic_daily.csv`: participant-day wearable features and shifts;
- `personal_baselines.csv`: each participant's feature centres and scales;
- `daily_deviation_scores.csv`: standardized deviations from baseline;
- `recovery_events.csv`: estimated recovery time after every night-shift block.

## Recovery definition in version 0.1

For each participant and each variable:

1. Estimate the centre and variability from eligible stable off-duty days.
2. Express each later observation as an absolute robust standardized deviation.
3. Combine available variables using the root-mean-square deviation.
4. Start follow-up on the first calendar day after the final night shift.
5. Define recovery as the first of two consecutive off-duty days with a score
   at or below the chosen threshold.
6. Mark the event as censored if another work block begins or follow-up ends
   before recovery is demonstrated.

The default demonstration variables are sleep onset, sleep midpoint, total
sleep time, sleep efficiency, resting heart rate, and daily steps. Thresholds
and included variables must be evaluated in sensitivity analyses rather than
treated as universal clinical cut-offs.

## Data

Raw participant data are never committed to this repository. See
[`docs/DATA_DOWNLOAD_CN.md`](docs/DATA_DOWNLOAD_CN.md) for exact access steps.
The standardized Bourdillon output fields and ingestion assumptions are listed
in [`docs/BOURDILLON_DATA_DICTIONARY.md`](docs/BOURDILLON_DATA_DICTIONARY.md).

- **Mauvieux 2025**: directly downloadable, CC BY 4.0. The release contains
  participant-level sleep and derived circadian parameters for three aggregated
  phases, plus group fitted curves. It can demonstrate open-data ingestion and
  phase comparison, but cannot identify the exact recovery day.
- **TILES-2018**: public research access after account registration and a signed
  Data Usage Agreement; 212 hospital workers followed for approximately ten
  weeks with Fitbit sleep, heart rate and steps, plus work-day metadata.
- **Bourdillon 2021**: openly released morning orthostatic-test RR intervals from
  a one-week baseline, three-night partial sleep-deprivation, and one-week
  recovery protocol. It validates the physiological recovery workflow but is
  not itself a shift-worker cohort.

## Repository layout

```text
ShiftRecoverPy/
├── docs/
│   ├── BASELINE_METHODS.md
│   ├── BOOTSTRAP_METHODS.md
│   ├── BOURDILLON_DATA_DICTIONARY.md
│   ├── DATA_DOWNLOAD_CN.md
│   ├── DEVIATION_METHODS.md
│   ├── FIGURE_METHODS.md
│   ├── HRV_METHODS.md
│   ├── METHOD_COMPARISON_METHODS.md
│   ├── PROJECT_PLAN_CN.md
│   ├── RECOVERY_EVENT_METHODS.md
│   ├── TESTING.md
│   └── THRESHOLD_SENSITIVITY_METHODS.md
├── src/shiftrecover/
│   ├── baseline.py
│   ├── bourdillon.py
│   ├── bootstrap.py
│   ├── circular.py
│   ├── cli.py
│   ├── comparison.py
│   ├── deviation.py
│   ├── hrv.py
│   ├── plotting.py
│   ├── recovery.py
│   ├── recovery_time.py
│   ├── sensitivity.py
│   └── simulate.py
├── tests/
├── data/raw/          # ignored by Git
├── results/           # ignored by Git
└── pyproject.toml
```

## Research interpretation

The output is a method-derived recovery estimate, not a medical diagnosis. A
short observational window produces right-censored recovery times. Associations
with health outcomes are observational and should not be interpreted causally.

## Data governance

This repository does not contain Airwave Health Monitoring Study participant
data. Those data were accessed under research governance and cannot be
redistributed. The present software is developed with synthetic benchmarks and
independent public or research-access datasets.

## Licence

Code is released under the MIT License. Source datasets retain their own terms.
