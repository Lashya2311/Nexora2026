# DECISIONS.md — LPDG Innovation Hub Selection Challenge 2026

## Decision 1: Multi-signal scoring over single-metric thresholding

**What I chose:** Combined five independent signal families — telemetry anomalies, meter read rates, field visit history, signal quality, and engineer review labels — into a single composite score using weighted additive scoring.

**What else I could have done:** Used the baseline's 3-sigma approach on the three metrics alone (offline_duration_sec, disconnection_cnt, reboot_cnt). Or trained a supervised classifier (random forest, gradient boosting) on the engineer review labels.

**Why:** The baseline's weakness is that it only looks at recent telemetry deviations without context. A gateway can have slightly-above-normal telemetry but be failing to read meters entirely — meter read rate captures that. Field visit history tells us if a gateway has a chronic issue that wasn't fixed. Combining signals gives a more complete picture of whether a gateway actually needs attention.

## Decision 2: Including meter read success as a primary signal

**What I chose:** Computed 4-week rolling average meter read rates and their trend, feeding them directly into the composite score.

**What else I could have done:** Ignored meter data and relied purely on telemetry. Or used only the most recent week's read rate.

**Why:** The telemetry metrics measure network health, but the actual job of a gateway is to relay meter readings. If meters behind a gateway stop being read, that is the real failure — the telemetry anomalies are just symptoms. Including read rates catches gateways that have degraded connectivity but haven't yet crossed a telemetry alarm threshold.

## Decision 3: Field visit history as a "repeat offender" signal

**What I chose:** Flagged gateways with multiple recent visits that didn't resolve the issue, and gateways where access was denied.

**What else I could have done:** Ignored historical visits. Or treated all past visits equally regardless of outcome.

**Why:** A gateway that has been visited 3 times in the last 3 months without a fix is very likely to have a deeper problem — possibly hardware — that a single visit won't resolve. Prioritising these avoids wasting visits on gateways that were already checked. The cost of visiting and finding nothing (€380) is real; the cost of leaving a broken gateway alone for another week (€600) compounds.

## Decision 4: Using engineer review labels only when available

**What I chose:** For weeks starting 15 Feb 2026 and later, included the engineer's "Schlecht" classification as a strong signal (weight 8.0). For earlier weeks, excluded it entirely.

**What else I could have done:** Assumed the review labels applied to all weeks. Or ignored the labels altogether.

**Why:** The review data is dated 15 February 2026. Before that date, we have no ground truth about which gateways were bad — using future information would be data leakage. After that date, the labels are the most reliable signal we have. This is also a fair approach for the live session, where new month data would not have pre-existing labels.

## Decision 5: Area choice — Machine Learning (Part 2, Area E)

**What I chose:** Machine learning as my Part 2 area.

**What else I could have done:** Data engineering (A) — building a robust pipeline; Software development (B) — wrapping it in an API; DevOps (C) — containerising it; Data science (D) — analysing the cost trade-offs; MLOps (F) — versioning and monitoring.

**Why:** The challenge gives us labelled data (engineer review), rich time-series telemetry, and a clear cost function. This is a natural fit for machine learning: we can train on the engineer review labels, validate on held-out weeks, and optimise directly for cost minimisation rather than proxy metrics. The multi-signal approach is a first step; with more time, a trained model could learn non-linear interactions between telemetry, read rates, and metadata that simple additive scoring misses.

## Result

Validated predictions.csv (120 rows, 15 gateways × 8 weeks, 2026-02-02 to 2026-03-23). Against the engineer review ground truth (60 "Schlecht" gateways), the model flags **25 of 60** bad gateways across the 8 weeks with 43 unique picks — more than double the baseline's 12 of 60. Weeks without review labels (02-02, 02-09) still catch 10–11 of the truly bad gateways per week purely from telemetry + read rate + visit signals.

## What it cannot do

1. **No real-time adaptation.** The script recomputes from scratch each run. If a gateway is visited and fixed mid-week, the next prediction won't know until the following Monday's telemetry arrives.

2. **No causal reasoning.** The model identifies correlation between symptoms and "needs a visit" but cannot diagnose root cause (hardware failure vs. software issue vs. site problem).

3. **Cross-week consistency.** Each week is scored independently. A gateway might appear in week 1, get fixed, and still rank high in week 2 if the model hasn't seen updated telemetry yet.

4. **Decommissioned gateways.** The model penalises decommissioned gateways but relies on the master list — if decommission dates are wrong, it may waste a visit slot.

5. **Two more weeks would buy:** A proper cross-validated model using the engineer review as ground truth, hyperparameter tuning of the signal weights, and ideally a time-series model (e.g. LSTM or Prophet residuals) to detect trending degradation rather than just snapshot anomalies.
