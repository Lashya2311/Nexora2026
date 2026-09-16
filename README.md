# LPDG Innovation Hub Selection Challenge 2026

Which 15 gateways should the LPDG field team visit next week?

Multi-signal anomaly scoring that ranks all ~320 gateways each week and outputs the 15 most likely to need a visit.

## Result

2x the baseline's recall against the engineer-review ground truth:

| Model | Bad gateways caught (of 60) |
|---|---|
| Baseline 3-sigma | 12 |
| This solution | **25** |

- 8 scored weeks: 2026-02-02 → 2026-03-23, 15 visits/week (hard limit)
- Output: `predictions.csv` — 120 rows, validated by `scripts/validate_submission.py`

## Results — visual

**Broken gateways someone should have visited, caught per week** (ground truth from the Feb engineer review of 60 gateways):

![Broken gateways caught per week](plots/evaluation.png)

**Total unique broken gateways flagged across all 8 weeks** — this solution flags 25 of the 60 truly broken gateways vs 12 for the baseline:

![Total recall](plots/total_recall.png)

## How it works

Each scored week, every gateway gets a composite anomaly score from five signals:

1. **Telemetry anomalies (50%)** — cumulative offline duration, disconnection count, and reboot count in the trailing 28 days. Bad gateways average ~12x more offline time, ~9x more disconnections, and ~5x more reboots than normal ones. Sums are normalised by the fleet median; abnormal-hour flags add a secondary bonus.
2. **Meter read rate (20%)** — a 4-week rolling read-success rate and its trend. Degrading read rates catch gateways whose connectivity has decayed below telemetry alarm thresholds.
3. **Field visit history (10%)** — repeat visits that didn't resolve the issue and no-access visits mark chronic offenders.
4. **Signal quality (5%)** — proportion of bad RSSI/RSRP/ECIO readings.
5. **Engineer review labels (15%, only for weeks ≥ 2026-02-15)** — the "Schlecht" classification from the February engineer review is applied only to weeks on or after the review date to avoid data leakage.

Decommissioned gateways are heavily penalised (never worth a visit slot).

## Getting started

```bash
# 1. Put the data in ./data (telemetry/, meter_read_success.csv, field_visits.csv,
#    engineer_review_2026-02.xlsx, gateway_master.csv)

# 2. Run, validate and evaluate
python scripts/run.py            # generates predictions.csv + validates it
python scripts/evaluate.py       # recall vs engineer-review ground truth
python scripts/make_plots.py     # regenerates the plots in ./plots
```

Requires Python 3.10+ with `pandas`, `numpy`, `pyarrow`, `openpyxl`, `matplotlib`.

## Project layout

```
lpdg-challenge/
├── predictions.csv          # final output (120 rows)
├── DECISIONS.md             # 5 key decisions + what it cannot do
├── AI-USAGE.md              # AI usage statement
├── SCREEN_RECORDING_GUIDE.md  # 7-minute recording walkthrough
├── plots/
│   ├── evaluation.png       # broken gateways caught per week
│   └── total_recall.png     # total unique broken gateways flagged
├── scripts/
│   ├── predict.py           # main prediction pipeline
│   ├── run.py               # one-command generate + validate
│   ├── evaluate.py          # recall vs engineer-review labels
│   ├── make_plots.py        # regenerates the plots
│   ├── baseline_3sigma.py   # provided baseline (reference)
│   └── validate_submission.py  # provided validator
└── data/                    # challenge data — NOT committed (confidential)
```

## Cost context

- €380 per visit (wasted if nothing is wrong)
- €600 per week per broken gateway left unvisited (recurring every week it stays broken)
- 15 visits/week is a hard limit

The model prioritises the highest-probability broken gateways first so expensive visits are spent where the recurring €600/week cost is mounting.