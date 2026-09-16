#!/usr/bin/env python3
"""
Enhanced prediction script for LPDG Innovation Hub Selection Challenge 2026.

Multi-signal anomaly scoring that considers:
  1. Telemetry anomalies (offline duration, disconnections, reboots)
  2. Declining meter read rates
  3. Field visit history (repeat visits, unfixed issues)
  4. Signal quality degradation
  5. Gateway metadata risk factors
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib

import numpy as np
import pandas as pd

SCORED_WEEKS = [dt.date(2026, 2, 2) + dt.timedelta(days=7 * i) for i in range(8)]
VISITS_PER_WEEK = 15
BASELINE_DAYS = 28
RECENT_DAYS = 7

TELEMETRY_METRICS = [
    "offline_duration_sec", "disconnection_cnt", "reboot_cnt",
    "reboot_duration_sec", "rx_crc_bad", "tx_busy",
]
SIGNAL_METRICS = [
    "rssi_bad", "rscp_rsrp_bad", "ecio_rsrq_bad",
]
SYSTEM_METRICS = [
    "avg_load1", "load1_bigger2", "avg_memfree",
]


def load_telemetry(data_dir: pathlib.Path) -> pd.DataFrame:
    frame = pd.read_parquet(
        data_dir / "telemetry",
        columns=["gateway_id", "ts_utc", *TELEMETRY_METRICS, *SIGNAL_METRICS, *SYSTEM_METRICS],
    )
    frame["ts"] = pd.to_datetime(frame["ts_utc"], utc=True)
    return frame.drop(columns=["ts_utc"])


def load_meter_read(data_dir: pathlib.Path) -> pd.DataFrame:
    ms = pd.read_csv(data_dir / "meter_read_success.csv")
    ms["week_start"] = pd.to_datetime(ms["week_start"]).dt.date
    ms["read_rate"] = ms["meters_read"] / ms["meters_expected"].clip(lower=1)
    ms["read_rate_drop"] = ms.groupby("gateway_id")["read_rate"].diff()
    return ms


def load_field_visits(data_dir: pathlib.Path) -> pd.DataFrame:
    fv = pd.read_csv(data_dir / "field_visits.csv")
    fv["requested_dt"] = pd.to_datetime(fv["requested_on"])
    fv["visited_dt"] = pd.to_datetime(fv["visited_on"])
    fv["gw_norm"] = fv["gateway_id"].str.replace(":", "").str.upper()
    fv["had_fix"] = fv["outcome"] == "Fehler behoben"
    fv["no_access"] = fv["outcome"] == "Kein Zugang"
    return fv


def load_engineer_review(data_dir: pathlib.Path) -> pd.DataFrame:
    rev = pd.read_excel(data_dir / "engineer_review_2026-02.xlsx")
    rev["gw_norm"] = rev["gateway_id"].str.replace(":", "").str.upper()
    rev["is_bad"] = rev["Kategorie"] == "Schlecht"
    return rev


def load_gateway_master(data_dir: pathlib.Path) -> pd.DataFrame:
    gm = pd.read_csv(data_dir / "gateway_master.csv", encoding="latin-1")
    gm["gw_norm"] = gm["gateway_id"].str.replace(":", "").str.upper()
    gm["is_decommissioned"] = gm["decommissioned_on"].notna()
    gm["installed_dt"] = pd.to_datetime(gm["installed_on"], errors="coerce")
    return gm


def score_telemetry(frame: pd.DataFrame, monday: dt.date, end_dt: pd.Timestamp) -> pd.DataFrame:
    """Score each gateway based on telemetry anomalies in the trailing window."""
    window = frame[(frame["ts"] >= end_dt - dt.timedelta(days=BASELINE_DAYS)) & (frame["ts"] < end_dt)]
    if window.empty:
        return pd.DataFrame()

    recent = window[window["ts"] >= end_dt - dt.timedelta(days=RECENT_DAYS)]
    mid = window[(window["ts"] >= end_dt - dt.timedelta(days=BASELINE_DAYS)) & (window["ts"] < end_dt - dt.timedelta(days=RECENT_DAYS))]

    # Per-gateway stats on mid period
    mid_stats = mid.groupby("gateway_id")[TELEMETRY_METRICS].agg(["mean", "std"])

    # Count flagged hours in recent period (beyond 2 sigma)
    flags = recent.groupby("gateway_id").size().rename("total_hours")

    # How many hours each metric is abnormally high
    flagged_counts = {}
    for metric in TELEMETRY_METRICS:
        mean = recent["gateway_id"].map(mid_stats[(metric, "mean")])
        std = recent["gateway_id"].map(mid_stats[(metric, "std")]).replace(0, np.nan)
        exceeded = (recent[metric] - mean) > 2.5 * std
        exceeded = exceeded.fillna(False)
        flagged_counts[f"flag_{metric}"] = exceeded.groupby(recent["gateway_id"]).sum()

    # Sum of metric values in recent period
    recent_sums = recent.groupby("gateway_id")[TELEMETRY_METRICS].sum()
    recent_means = recent.groupby("gateway_id")[TELEMETRY_METRICS].mean()

    # Signal quality degrades
    signal_sum = recent.groupby("gateway_id")[SIGNAL_METRICS].sum()
    total_signal = signal_sum.sum(axis=1).clip(lower=1)
    bad_signal_ratio = signal_sum.get("rssi_bad", 0) / total_signal

    result = flags.to_frame()
    for k, v in flagged_counts.items():
        result[k] = v
    for m in TELEMETRY_METRICS:
        result[f"sum_{m}"] = recent_sums[m]
        result[f"mean_{m}"] = recent_means[m]
    result["bad_signal_ratio"] = bad_signal_ratio

    return result


def score_meter_reads(ms: pd.DataFrame, monday: dt.date) -> pd.DataFrame:
    """Score each gateway based on declining meter read rates."""
    # Get the 4 weeks leading up to the Monday
    relevant = ms[(ms["week_start"] >= monday - dt.timedelta(days=28)) & (ms["week_start"] < monday)]
    if relevant.empty:
        return pd.DataFrame()

    grouped = relevant.groupby("gateway_id").agg(
        avg_read_rate=("read_rate", "mean"),
        min_read_rate=("read_rate", "min"),
        read_rate_trend=("read_rate_drop", "mean"),
        n_weeks=("read_rate", "count"),
        total_meters_expected=("meters_expected", "sum"),
        total_meters_read=("meters_read", "sum"),
    )
    grouped["overall_read_rate"] = grouped["total_meters_read"] / grouped["total_meters_expected"].clip(lower=1)

    return grouped


def score_field_visits(fv: pd.DataFrame, monday: dt.date) -> pd.DataFrame:
    """Score each gateway based on field visit history."""
    # Visits in the 3 months before this Monday
    cutoff = pd.Timestamp(monday)
    recent_visits = fv[fv["requested_dt"] < cutoff]
    recent_3m = recent_visits[recent_visits["requested_dt"] >= cutoff - dt.timedelta(days=90)]
    recent_1m = recent_visits[recent_visits["requested_dt"] >= cutoff - dt.timedelta(days=30)]

    grouped_3m = recent_3m.groupby("gw_norm").agg(
        visit_count_3m=("visit_id", "count"),
        fix_count_3m=("had_fix", "sum"),
        no_access_3m=("no_access", "sum"),
        last_visit=("requested_dt", "max"),
    )
    grouped_1m = recent_1m.groupby("gw_norm").agg(
        visit_count_1m=("visit_id", "count"),
    )

    result = grouped_3m.join(grouped_1m, how="left")
    result["visit_count_1m"] = result["visit_count_1m"].fillna(0)
    result["days_since_visit"] = (cutoff - result["last_visit"]).dt.days

    return result


def build_scored_features(
    telem_score: pd.DataFrame,
    meter_score: pd.DataFrame,
    visit_score: pd.DataFrame,
    review_df: pd.DataFrame,
    gm_df: pd.DataFrame,
    monday: dt.date,
) -> pd.DataFrame:
    """Combine all signals into a per-gateway feature set."""
    # Start with telemetry scores
    features = telem_score.copy()

    # Join meter read data
    if not meter_score.empty:
        features = features.join(meter_score, how="left")

    # Join field visit data
    if not visit_score.empty:
        features = features.join(visit_score, how="left")

    # Join engineer review (if available for this week)
    if monday >= dt.date(2026, 2, 15):
        review_available = review_df[["gw_norm", "is_bad", "Bemerkung"]].copy()
        review_available = review_available.set_index("gw_norm")
        features = features.join(review_available, how="left")
    else:
        features["is_bad"] = np.nan
        features["Bemerkung"] = ""

    # Join gateway master info
    gw_info = gm_df[["gw_norm", "is_decommissioned", "n_meters_installed", "hw_model", "site_type", "installed_dt"]].copy()
    gw_info = gw_info.set_index("gw_norm")
    features = features.join(gw_info, how="left")

    # Fill NaN
    features = features.fillna(0)

    return features


def compute_composite_score(features: pd.DataFrame, monday: dt.date) -> pd.Series:
    """Compute a composite anomaly score for each gateway.

    Key insight from data analysis: bad gateways have 12x more offline time,
    9x more disconnections, and 5x more reboots than normal gateways.
    Cumulative sums are the strongest discriminator.
    """
    score = pd.Series(0.0, index=features.index)

    # 1. Cumulative telemetry (50% weight) - the strongest signal
    # Bad gateways: offline ~5M, disc ~1445, reboots ~47
    # Normal:       offline ~0.4M, disc ~161,  reboots ~9
    for metric, weight in [("offline_duration_sec", 2.0), ("disconnection_cnt", 3.0), ("reboot_cnt", 1.5)]:
        col = f"sum_{metric}"
        if col in features.columns:
            median = features[col].median()
            if median > 0:
                normalized = features[col] / median
                score += normalized.clip(upper=15.0) * weight

    # 2. Flag hours bonus - gateways with many anomalous hours are riskier (15%)
    for metric in TELEMETRY_METRICS:
        col = f"flag_{metric}"
        if col in features.columns:
            score += features[col] * 0.5

    # 3. Meter read rate (15%) - low reads = can't trust the gateway
    if "avg_read_rate" in features.columns:
        read_deficit = (1.0 - features["avg_read_rate"].clip(upper=1.0, lower=0.0))
        score += read_deficit * 4.0

    # 4. Read rate declining trend (5%)
    if "read_rate_trend" in features.columns:
        decline = features["read_rate_trend"].clip(lower=-0.5, upper=0)
        score += (-decline) * 2.0

    # 5. Field visit signals - unfixed visits are expensive to waste (10%)
    if "visit_count_3m" in features.columns:
        unfixed = features["visit_count_3m"] - features["fix_count_3m"]
        score += unfixed.clip(lower=0) * 2.0

    if "no_access_3m" in features.columns:
        score += features["no_access_3m"] * 1.5

    # 6. Engineer review label boost (strong positive signal, 5%)
    if "is_bad" in features.columns:
        score += features["is_bad"].astype(float) * 8.0

    # 7. Signal quality degradation (5%)
    if "bad_signal_ratio" in features.columns:
        score += features["bad_signal_ratio"].clip(upper=1.0) * 2.0

    # 8. Decommissioned penalty
    if "is_decommissioned" in features.columns:
        score -= features["is_decommissioned"].astype(float) * 50.0

    return score


def generate_reasons(features: pd.DataFrame, ranked: pd.DataFrame) -> list[str]:
    """Generate human-readable reasons for each gateway selection."""
    reasons = []
    for gw in ranked.index:
        if gw not in features.index:
            reasons.append("Flagged by multi-signal anomaly scoring.")
            continue

        row = features.loc[gw]
        parts = []

        # Check specific issues
        flag_total = sum(row.get(f"flag_{m}", 0) for m in TELEMETRY_METRICS)
        if flag_total > 5:
            top_metric = max(TELEMETRY_METRICS, key=lambda m: row.get(f"flag_{m}", 0))
            readable = {
                "offline_duration_sec": "prolonged offline periods",
                "disconnection_cnt": "frequent disconnections",
                "reboot_cnt": "excessive reboots",
                "reboot_duration_sec": "long reboot durations",
                "rx_crc_bad": "high CRC error rate",
                "tx_busy": "transmit failures",
            }
            parts.append(f"{flag_total} hours with {readable.get(top_metric, 'anomalies')}")

        if "avg_read_rate" in row and row["avg_read_rate"] < 0.7:
            parts.append(f"meter read rate only {row['avg_read_rate']:.0%}")

        if "read_rate_trend" in row and row["read_rate_trend"] < -0.1:
            parts.append("declining read rate")

        if "visit_count_3m" in row and row["visit_count_3m"] > 2:
            unfixed = row["visit_count_3m"] - row["fix_count_3m"]
            if unfixed > 0:
                parts.append(f"{int(unfixed)} unfixed visit(s) in last 3 months")
            else:
                parts.append("multiple recent visits with recurring issues")

        if "no_access_3m" in row and row["no_access_3m"] > 0:
            parts.append(f"{int(row['no_access_3m'])} visit(s) with no access")

        if row.get("is_bad", False):
            parts.append("flagged as problematic in engineer review")

        if "bad_signal_ratio" in row and row["bad_signal_ratio"] > 0.3:
            parts.append("degraded signal quality")

        if not parts:
            parts.append("above-average anomaly score across multiple telemetry indicators")

        reasons.append("; ".join(parts[:2])[:299])

    return reasons


def build_predictions(frame: pd.DataFrame, ms: pd.DataFrame, fv: pd.DataFrame,
                      review_df: pd.DataFrame, gm_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for monday in SCORED_WEEKS:
        end_dt = pd.Timestamp(monday, tz="UTC")

        telem_score = score_telemetry(frame, monday, end_dt)
        meter_score = score_meter_reads(ms, monday)
        visit_score = score_field_visits(fv, monday)

        features = build_scored_features(telem_score, meter_score, visit_score, review_df, gm_df, monday)
        scores = compute_composite_score(features, monday)

        ranked = scores.sort_values(ascending=False).head(VISITS_PER_WEEK)
        reasons = generate_reasons(features, ranked)

        for rank, (gw, sc) in enumerate(ranked.items(), 1):
            rows.append({
                "week_start": monday.isoformat(),
                "rank": rank,
                "gateway_id": gw,
                "score": float(sc),
                "reason": reasons[rank - 1],
            })

    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    here = pathlib.Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    default_data = here / "data" if (here / "data").exists() else here.parent / "data"
    parser.add_argument("--data", type=pathlib.Path, default=default_data)
    parser.add_argument("--out", type=pathlib.Path, default=here.parent / "predictions.csv")
    args = parser.parse_args(argv)

    print("Loading data...")
    frame = load_telemetry(args.data)
    print(f"  Telemetry: {len(frame):,} rows")

    ms = load_meter_read(args.data)
    print(f"  Meter read: {len(ms):,} rows")

    fv = load_field_visits(args.data)
    print(f"  Field visits: {len(fv):,} rows")

    review_df = load_engineer_review(args.data)
    print(f"  Engineer review: {len(review_df):,} rows")

    gm_df = load_gateway_master(args.data)
    print(f"  Gateway master: {len(gm_df):,} gateways")

    print("Building predictions...")
    predictions = build_predictions(frame, ms, fv, review_df, gm_df)

    predictions.to_csv(args.out, index=False)
    print(f"Wrote {args.out} - {len(predictions)} rows over {predictions.week_start.nunique()} weeks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
