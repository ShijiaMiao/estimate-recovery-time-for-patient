# First HRV recovery event specification

## Primary endpoint

The primary recovery endpoint uses the combined RMSSD/SDNN absolute deviation
score. Recovery is demonstrated when:

```text
HRV deviation score <= 1.5 on two consecutive calendar recovery days
```

Recovery time is assigned to the first day in that qualifying run. The second
day is retained separately as `confirmation_day`; this avoids hiding the future
observation required to establish stable recovery.

The threshold and consecutive-day requirement are operational method choices,
not clinical diagnostic criteria. They are configurable and will be varied in
the sensitivity-analysis stage.

## Missingness and quality control

Only rows with `deviation_status == calculated` can contribute to a qualifying
run. A missing observation, failed-QC session, invalid metric, or unavailable
baseline breaks consecutiveness. The program never joins days across a gap.

For each eligible series it records:

- number and span of evaluable follow-up days;
- first day below threshold, even if stable recovery is not confirmed;
- intermittent and trailing missingness;
- score on the recovery and confirmation days.

## Right censoring

An eligible series that does not demonstrate recovery is right-censored at its
last evaluable recovery day. `analysis_time_days` contains the recovery day when
an event occurs and the censor day otherwise.

A participant-posture combination with an insufficient baseline, no
post-baseline data, or no evaluable follow-up is not placed in the survival risk
set. Such rows are retained with their explicit status and are not mislabeled as
right-censored observations.

Intermittent missingness can conceal an unobserved recovery and introduces more
uncertainty than ordinary terminal right censoring. It is flagged for later
sensitivity analyses rather than ignored.

## Secondary endpoints

The same event logic is applied separately to:

- absolute RMSSD deviation;
- absolute SDNN deviation;
- the primary RMSSD/SDNN composite score.

The primary table contains the composite endpoint. The all-endpoints table
supports transparent comparison without changing the prespecified primary
definition.
