"""Replay every local flood comparison model in a separate Python process."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

import joblib
import numpy as np
import pandas as pd

try:
    from scripts import benchmark_warranty_models as benchmark
except ModuleNotFoundError:
    import benchmark_warranty_models as benchmark


def verify_one(input_path: Path, artifact_path: Path, prediction_path: Path) -> dict:
    artifact = joblib.load(artifact_path)
    options = artifact["feature_preparation_options"]
    benchmark.configure_premise_context(options.get("premise_context", False))
    benchmark.configure_pest_context(options.get("normalize_pest_context", False))
    benchmark.configure_flood_context(options.get("flood_context", False))
    benchmark.configure_reported_flood_context(options.get("reported_flood_context", False))
    frame = benchmark.prepare_frame(benchmark.load_dataset_input(input_path))
    frame = frame[frame["population"].eq(artifact["population"])].copy()
    _, diagnostic, _ = benchmark.purged_split(frame, benchmark.REPORTING_START)
    expected = pd.read_csv(prediction_path, dtype={"sales_record_id": str})
    if diagnostic["sales_record_id"].astype(str).tolist() != expected["sales_record_id"].tolist():
        raise ValueError("Saved prediction package sequence differs from replay")
    if diagnostic["anchor_date"].dt.strftime("%Y-%m-%d").tolist() != expected["anchor_date"].tolist():
        raise ValueError("Saved prediction anchor sequence differs from replay")
    raw = artifact["pipeline"].predict_proba(diagnostic[artifact["features"]])[:, 1]
    probability = benchmark.apply_calibrator(artifact["calibrator"], raw)
    if not np.isfinite(probability).all() or not ((probability >= 0) & (probability <= 1)).all():
        raise ValueError("Replayed probabilities are not finite values in [0,1]")
    np.testing.assert_allclose(raw, expected["raw_probability"], rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(probability, expected["probability"], rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(expected["threshold"], artifact["threshold"], rtol=0, atol=1e-12)
    return {"artifact": str(artifact_path.resolve()), "diagnostic_rows": len(diagnostic),
            "feature_preparation_options": options,
            "max_probability_difference": float(np.max(
                np.abs(probability - expected["probability"].to_numpy()))),
            "finite_probabilities_between_zero_and_one": True,
            "fresh_process_replay_passed": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--input-json", type=Path)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--expected-predictions", type=Path)
    args = parser.parse_args()
    if args.artifact:
        print(json.dumps(verify_one(args.input_json, args.artifact,
                                   args.expected_predictions), allow_nan=False))
        return
    if not args.output_dir:
        raise SystemExit("Specify flood comparison --output-dir")
    comparison = json.loads((args.output_dir / "flood_comparison_results.json").read_text())
    population = comparison["baseline"]["population"]
    variants = [
        ("baseline", f"{population}_selected_model.joblib", f"{population}_diagnostic_predictions.csv"),
        ("flood", f"{population}_selected_model.joblib", f"{population}_diagnostic_predictions.csv"),
        ("locked_flood", "selected_model.joblib", "diagnostic_predictions.csv"),
        ("locked_observation_control", "selected_model.joblib", "diagnostic_predictions.csv"),
    ]
    if comparison.get("locked_baseline_winner_plus_reported_regional_flood") is not None:
        variants.append(("locked_reported_flood", "selected_model.joblib", "diagnostic_predictions.csv"))
    results = []
    for variant, artifact, predictions in variants:
        completed = subprocess.run([
            sys.executable, str(Path(__file__).resolve()),
            "--input-json", str(args.output_dir / "dataset_input.json"),
            "--artifact", str(args.output_dir / variant / artifact),
            "--expected-predictions", str(args.output_dir / variant / predictions),
        ], check=True, capture_output=True, text=True)
        results.append({"variant": variant, **json.loads(completed.stdout)})
    receipt = {"models_verified_in_separate_python_processes": len(results),
               "dataset_input_sha256": comparison["dataset_input_sha256"], "models": results}
    (args.output_dir / "artifact_replay_verification.json").write_text(
        json.dumps(receipt, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(receipt, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
