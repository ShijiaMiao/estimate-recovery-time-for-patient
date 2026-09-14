# estimate-recovery-time-for-patient

**Personal estimation of recovery after shift work using longitudinal wearable data**

`estimate-recovery-time-for-patient` is a reproducible Python toolkit. It estimates how many days a person needs to return to their own baseline after shift work.

This project comes from my research on eating patterns in police officers who work shifts. In this research, I found that there is still a lack of methods to calculate recovery time after different shift patterns.

This project uses the same idea of analysing data over time. It applies this idea to wearable data, including sleep, heart rate, and activity data.

The main question is:

> After the last shift in a work period, how many days does a person need to return to their normal physical and behavioural state?

## Include：



Two public datasets are used. The Mauvieux dataset provides sleep results from three study stages. These data can be used to compare changes between the stages. The Bourdillon dataset comes from an experiment with a baseline period, a partial sleep deprivation period, and a recovery period. It provides daily RR interval records. The RR intervals are checked for data quality and then converted into NN intervals. RMSSD and SDNN are then calculated for different body positions. A personal HRV baseline and normal range are created from each participant’s baseline condition. The recovery data are arranged from day 1 to day 7. The difference between each recovery day and the personal baseline is then calculated. Missing data are excluded from this calculation.

Recovery is defined as two consecutive days within the normal range. The first of these two days is recorded as the recovery day. If recovery is not observed before the end of follow-up, the record is treated as right-censored. Four recovery thresholds are used to check whether the results are stable. Personal baselines are compared with the population average baseline. A one-day recovery rule is also compared with a two-day recovery rule. Bootstrap resampling is performed at the participant level. It provides uncertainty intervals for the recovery proportion and recovery time. The final results include a study timeline, individual recovery trajectories, a recovery-day heatmap, and Kaplan–Meier recovery curves.

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
