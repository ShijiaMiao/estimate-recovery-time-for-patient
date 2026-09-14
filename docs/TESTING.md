# Testing and quality assurance

## Current result

- Automated tests: **67 passed, 0 failed**.
- Core-library statement coverage: **87%**.
- Required coverage gate: **80%**.
- Tested Python versions in continuous integration: **3.10 and 3.12**.
- Real-data output integrity checks: passed.

The command-line module is excluded from the percentage because it primarily
parses arguments and delegates to tested library functions. Its help command
and the complete real-data pipeline have been smoke-tested separately. The
scientific calculations, QC decisions, censoring logic, uncertainty estimates
and figure preparation remain inside the measured core library.

## Test matrix

| Test file | Tests | Primary responsibility |
|---|---:|---|
| `test_bourdillon.py` | 13 | File parsing, date correction, posture splitting and ingestion audit |
| `test_hrv.py` | 11 | RR artefact flags, interpolation, RMSSD, SDNN and session QC |
| `test_shiftrecover.py` | 6 | Circular time, baselines, recovery and Mauvieux adapter |
| `test_deviation.py` | 3 | Daily personal deviations, complete grids and insufficient baselines |
| `test_recovery_time.py` | 4 | Consecutive-day recovery, missing days and right censoring |
| `test_sensitivity.py` | 3 | Threshold repetition, stability tables and monotonicity |
| `test_comparison.py` | 8 | Population baseline, common risk set and paired method disagreement |
| `test_bootstrap.py` | 12 | KM statistics, cluster resampling, reproducibility and interval audit |
| `test_plotting.py` | 3 | Heatmap/KM preparation and eight figure artefacts |
| `test_simulate.py` | 4 | Reproducible synthetic data and shift schedule structure |
| **Total** | **67** | |

## Coverage by module

| Core module | Statement coverage |
|---|---:|
| `baseline.py` | 83% |
| `bootstrap.py` | 97% |
| `bourdillon.py` | 85% |
| `circular.py` | 92% |
| `comparison.py` | 96% |
| `deviation.py` | 86% |
| `hrv.py` | 79% |
| `mauvieux.py` | 53% |
| `plotting.py` | 97% |
| `recovery.py` | 94% |
| `recovery_time.py` | 79% |
| `sensitivity.py` | 68% |
| **Core library overall** | **87%** |

Lower module percentages mainly reflect defensive error branches and Markdown
report renderers. The primary Bourdillon calculation path is exercised from
raw RR parsing through figures. Mauvieux coverage is lower because that adapter
is secondary and its public release is phase-aggregated rather than suitable
for day-level recovery estimation.

## High-risk behaviours explicitly tested

- malformed and non-numeric RR files fail visibly;
- known filename/date anomalies receive documented correction;
- artefacts are flagged before interpolation;
- RMSSD and sample SDNN match hand calculations;
- missing days break a consecutive recovery sequence;
- unrecovered observations remain right-censored;
- relaxing a recovery threshold cannot delay recovery;
- two-day confirmation cannot recover earlier than a one-day rule;
- personal and population methods use the same risk set;
- bootstrap resampling is participant-clustered and seed-reproducible;
- invalid probability intervals fail the bootstrap audit;
- all four figures are written in both PNG and SVG formats.

## Local commands

```bash
python -m pip install -e ".[dev]"
python -m coverage run -m unittest discover -s tests -v
python -m coverage report
```

The final command exits unsuccessfully when core-library coverage falls below
80%, so the GitHub workflow acts as a quality gate rather than a decorative
test badge.
