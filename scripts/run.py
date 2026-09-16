#!/usr/bin/env python3
"""Quick runner for the LPDG challenge prediction pipeline."""

import subprocess
import sys
import pathlib

here = pathlib.Path(__file__).resolve().parent
project = here.parent
scripts = project / "scripts"
data = project / "data"
predictions = project / "predictions.csv"
validate = here / "validate_submission.py"

def run():
    # 0. Check the data folder exists with the expected layout
    print("=" * 60)
    print("STEP 0: Checking data folder...")
    print("=" * 60)
    if not data.is_dir():
        print(f"ERROR: data folder not found at {data}")
        print("Expected layout in ./data/")
        print("  telemetry/month=YYYY-MM/part-0.parquet")
        print("  meter_read_success.csv")
        print("  field_visits.csv")
        print("  engineer_review_2026-02.xlsx")
        print("  gateway_master.csv")
        print("Place the challenge data in the data folder and re-run.")
        return 1
    print(f"  data folder found at {data}")
    for required in ["meter_read_success.csv", "field_visits.csv", "gateway_master.csv"]:
        if not (data / required).exists():
            print(f"WARNING: {required} missing from data folder")
    if not (data / "telemetry").is_dir():
        print(f"WARNING: telemetry/ folder missing from data folder")
    if not (data / "engineer_review_2026-02.xlsx").exists():
        print(f"NOTE: engineer_review_2026-02.xlsx missing - predictions will use telemetry-only signals")

    # Step 1: Generate predictions
    print("=" * 60)
    print("STEP 1: Generating predictions...")
    print("=" * 60)
    result = subprocess.run(
        [sys.executable, str(scripts / "predict.py"), "--data", str(data), "--out", str(predictions)],
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print("ERROR:", result.stderr)
        return 1

    # Step 2: Validate
    print("=" * 60)
    print("STEP 2: Validating predictions...")
    print("=" * 60)
    result = subprocess.run(
        [sys.executable, str(validate), str(predictions)],
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode

if __name__ == "__main__":
    raise SystemExit(run())
