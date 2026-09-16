"""Generate evaluation plot (baseline vs this model, bad gateways per week)."""

from __future__ import annotations

import argparse
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASELINE_BAD_PER_WEEK = [3, 3, 3, 2, 2, 2, 3, 4]


def main(argv: list[str] | None = None) -> int:
    here = pathlib.Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=pathlib.Path, default=here / "data")
    parser.add_argument("--predictions", type=pathlib.Path, default=here / "predictions.csv")
    parser.add_argument("--out", type=pathlib.Path, default=here / "plots" / "evaluation.png")
    args = parser.parse_args(argv)

    review = pd.read_excel(args.data / "engineer_review_2026-02.xlsx")
    review["gw_norm"] = review["gateway_id"].str.replace(":", "").str.upper()
    bad_gws = set(review.loc[review["Kategorie"] == "Schlecht", "gw_norm"])

    pred = pd.read_csv(args.predictions)
    pred["gw_norm"] = pred["gateway_id"].str.replace(":", "").str.upper()

    ours_per_week = []
    weeks = []
    for wk in sorted(pred["week_start"].unique()):
        weeks.append(wk)
        wk_gws = set(pred[pred["week_start"] == wk]["gw_norm"])
        ours_per_week.append(len(wk_gws & bad_gws))

    bpw = np.array(BASELINE_BAD_PER_WEEK)
    opw = np.array(ours_per_week)

    args.out.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(weeks))
    width = 0.38

    bars1 = ax.bar(x - width / 2, bpw, width, label="Baseline 3-sigma", color="#8b8b8b")
    bars2 = ax.bar(x + width / 2, opw, width, label="This solution", color="#2a72b3")

    ax.set_ylabel("Broken gateways flagged (out of 15)")
    ax.set_title("Broken gateways caught per week — baseline vs this solution")
    ax.set_xticks(x)
    ax.set_xticklabels([w[5:] for w in weeks], rotation=45, ha="right")
    ax.legend()
    ax.set_ylim(0, 16)
    for b in list(bars1) + list(bars2):
        ax.annotate(str(int(b.get_height())), (b.get_x() + b.get_width() / 2, b.get_height() + 0.3),
                    ha="center", fontsize=9)
    ax.axhline(15, color="grey", ls="--", lw=0.8, alpha=0.6)
    ax.text(0.02, 15.4, "15 visits/week hard limit", color="grey", fontsize=8)

    fig.tight_layout()
    fig.savefig(args.out, dpi=150)
    print(f"Wrote {args.out}")

    # Also write a small summary plot showing cumulative unique broken gateways caught
    cum_ours = len(set(pred["gw_norm"]) & bad_gws)
    fig2, ax2 = plt.subplots(figsize=(7, 4))
    ax2.bar(["Baseline", "This\nsolution"], [12, cum_ours], color=["#8b8b8b", "#2a72b3"], width=0.5)
    ax2.set_ylabel("Unique broken gateways flagged")
    ax2.set_title("Total broken gateways caught across 8 weeks (target: 60)")
    ax2.axhline(60, color="grey", ls="--", lw=0.8)
    ax2.text(1.5, 60.5, "60 truly broken", color="grey", fontsize=8, ha="center")
    for i, v in enumerate([12, cum_ours]):
        ax2.text(i, v + 1.2, str(v), ha="center", fontsize=11)
    fig2.tight_layout()
    fig2.savefig(args.out.with_name("total_recall.png"), dpi=150)
    print(f"Wrote {args.out.with_name('total_recall.png')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
