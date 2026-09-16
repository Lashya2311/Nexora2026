#!/usr/bin/env python3
"""Evaluate predictions.csv against the engineer-review ground truth.

Usage:
    python scripts/evaluate.py --data data --predictions predictions.csv
"""

from __future__ import annotations

import argparse
import pathlib

import pandas as pd


def main(argv: list[str] | None = None) -> int:
    here = pathlib.Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=pathlib.Path, default=here / "data")
    parser.add_argument("--predictions", type=pathlib.Path, default=here / "predictions.csv")
    args = parser.parse_args(argv)

    review = pd.read_excel(args.data / "engineer_review_2026-02.xlsx")
    review["gw_norm"] = review["gateway_id"].str.replace(":", "").str.upper()
    bad_gws = set(review.loc[review["Kategorie"] == "Schlecht", "gw_norm"])

    pred = pd.read_csv(args.predictions)
    pred["gw_norm"] = pred["gateway_id"].str.replace(":", "").str.upper()
    unique = set(pred["gw_norm"].unique())

    caught = unique & bad_gws
    total = len(bad_gws)
    print(f"Unique gateways visited across all weeks: {len(unique)}")
    print(f"Truly broken (Schlecht) gateways seen by the engineer review: {total}")
    print(f"Broken gateways caught by this model: {len(caught)}/{total}")

    print("\nPer week:")
    print(f"  {'week_start':<12} {'bad /15':<10}")
    for wk in sorted(pred["week_start"].unique()):
        wk_gws = set(pred[pred["week_start"] == wk]["gw_norm"])
        n_bad = len(wk_gws & bad_gws)
        print(f"  {wk:<12} {n_bad:<10}")

    rec = len(caught) / total if total else 0
    print(f"\nRecall vs engineer review: {rec:.0%}")
    print("Reference: the supplied baseline (3-sigma) achieves 12/60 = 20%")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())