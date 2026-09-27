"""Key-aligned paired evaluation for saved callback predictions.

Prediction logs can arrive in any file order. Canonicalizing the cohort before
resampling keeps labels, scores, segments and connected groups on the same rows.
Historical feature/model code is deliberately left unchanged.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

try:
    from scripts import benchmark_warranty_models as b
    from scripts.compare_callback_blind_spots import budget_alert, masks
except ModuleNotFoundError:
    import benchmark_warranty_models as b
    from compare_callback_blind_spots import budget_alert, masks

KEYS = ["population", "sales_record_id", "anchor_date"]


def paired_intervals(frame, baseline, candidate, repeats=300):
    """Resample paired connected components with explicit one-to-one key joins."""
    if frame.empty or not isinstance(repeats, int) or repeats < 1:
        raise ValueError("Nonempty paired cohort and positive repeat count required")
    cohort = frame.sort_values(KEYS, kind="stable").reset_index(drop=True)
    if cohort[KEYS + [b.TARGET, "validation_group"]].isna().any().any():
        raise ValueError("Paired cohort keys, outcomes and groups cannot be null")
    if not cohort[b.TARGET].isin([True, False, 0, 1]).all():
        raise ValueError("Paired cohort requires resolved binary outcomes")
    if cohort.duplicated(KEYS).any():
        raise ValueError("Duplicate paired cohort keys")

    def align(predictions):
        columns = KEYS + [b.TARGET, "probability"]
        if predictions[KEYS].isna().any().any():
            raise ValueError("Paired prediction keys cannot be null")
        joined = cohort[KEYS + [b.TARGET]].assign(_row_position=np.arange(len(cohort))).merge(
            predictions[columns], on=KEYS, how="outer", validate="one_to_one",
            indicator=True, suffixes=("", "_saved"))
        if (not joined["_merge"].eq("both").all()
                or not joined[b.TARGET].eq(joined[b.TARGET + "_saved"]).all()):
            raise ValueError("Paired cohort or outcomes differ")
        # Outer joins are free to sort their keys. Never use their incidental
        # row order as the order of the caller's labels or component indices.
        scores = joined.sort_values("_row_position")["probability"].to_numpy(dtype=float)
        if not np.isfinite(scores).all() or not ((scores >= 0) & (scores <= 1)).all():
            raise ValueError("Paired scores must be finite probabilities in [0,1]")
        return scores

    p0, p1 = align(baseline), align(candidate)
    y = cohort[b.TARGET].to_numpy(dtype=bool)
    groups = list(cohort.groupby("validation_group", sort=False).indices.values())
    target_masks = {name: mask.to_numpy() for name, mask in masks(cohort).items()
                    if name in ["all", "first_service", "mixed_pest", "target_union"]}
    values = {name: [] for name in ["roc_auc", "average_precision"]
              + [name + "_budget_recall" for name in target_masks]}
    rng = np.random.default_rng(42)
    for _ in range(repeats):
        idx = np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        if np.unique(y[idx]).size < 2:
            continue
        metrics = [b.score(y[idx], probability[idx]) for probability in [p0, p1]]
        for name in ["roc_auc", "average_precision"]:
            values[name].append(metrics[1][name] - metrics[0][name])
        alerts = [budget_alert(probability[idx]) for probability in [p0, p1]]
        for name, mask in target_masks.items():
            positives = y[idx] & mask[idx]
            if positives.sum():
                values[name + "_budget_recall"].append(float(
                    (alerts[1] & positives).sum() / positives.sum()
                    - (alerts[0] & positives).sum() / positives.sum()))
    return {"direction": "candidate_minus_baseline", "groups": len(groups),
            "requested_repeats": repeats,
            "valid_repeats": {name: len(v) for name, v in values.items()},
            "confidence_95pct": {name: np.quantile(v, [.025, .975]).tolist() if v else None
                                 for name, v in values.items()}}
