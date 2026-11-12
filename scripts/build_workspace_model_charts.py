"""Render aggregate historical assessment charts for the Nomobug workspace."""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import auc, precision_recall_curve, roc_curve

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "notebooks/evidence"
STATIC = ROOT / "webapp/static"
BLUE, TEAL, GREY = "#535cc5", "#147689", "#667085"


def rows(name):
    with (EVIDENCE / name).open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def save(fig, name):
    fig.savefig(STATIC / f"model-{name}.png", dpi=160, facecolor="white")
    plt.close(fig)


def plot_classification():
    predictions = rows("return_test_predictions.csv")
    labels = [row["warranty_signal_within_30d"] == "True" for row in predictions]
    scores = [float(row["probability"]) for row in predictions]
    metrics = json.loads((EVIDENCE / "model_results.json").read_text())["return30"]
    false_positive, true_positive, _ = roc_curve(labels, scores)
    precision, recall, _ = precision_recall_curve(labels, scores)
    assert abs(auc(false_positive, true_positive) - metrics["roc_auc"]) < 1e-9

    for name, x, y, x_label, y_label, baseline in [
        ("roc", false_positive, true_positive, "False positive rate", "True positive rate", [0, 1]),
        ("precision-recall", recall, precision, "Recall", "Precision", [metrics["prevalence"]] * 2),
    ]:
        fig, ax = plt.subplots(figsize=(5.5, 3.65), layout="constrained")
        ax.step(x, y, where="post", color=BLUE, linewidth=2, label="ExtraTrees")
        ax.plot([0, 1], baseline, "--", color=GREY, label="Baseline")
        ax.set(xlim=(0, 1), ylim=(0, 1.04), xlabel=x_label, ylabel=y_label)
        ax.legend(loc="best", frameon=False)
        ax.grid(alpha=.22)
        save(fig, name)

    names = ["Accuracy", "Precision", "Recall", "F1"]
    values = [metrics[key] for key in ("accuracy", "precision", "recall", "f1")]
    fig, ax = plt.subplots(figsize=(5.5, 3.65), layout="constrained")
    bars = ax.barh(names, values, color=BLUE)
    ax.bar_label(bars, labels=[f"{value:.0%}" for value in values], padding=4)
    ax.scatter(metrics["majority_class_accuracy"], "Accuracy", color=TEAL, zorder=3,
               label="Always predict no return")
    ax.invert_yaxis()
    ax.set(xlim=(0, 1.15), xlabel="Proportion")
    ax.legend(loc="lower right", frameon=False)
    save(fig, "threshold")


def plot_forecast(source, name, unit):
    assessment = rows(source)
    fig, ax = plt.subplots(figsize=(6, 3.7), layout="constrained")
    dates = [row["origin"][5:] for row in assessment]
    for field, label, color, style in [
        ("actual", "Recorded", "#242940", "-"),
        ("selected", "Model forecast", BLUE, "-"),
        ("baseline", "Baseline", GREY, "--"),
    ]:
        ax.plot(dates, [float(row[field]) for row in assessment], style, color=color,
                marker="o" if field == "actual" else None, markersize=3, label=label)
    ax.set_xticks(range(0, len(dates), 3))
    ax.set(xlabel="Forecast date (2026)", ylabel=unit)
    ax.legend(loc="best", frameon=False)
    ax.grid(axis="y", alpha=.22)
    save(fig, name)


def plot_input_removal():
    trials = rows("individual_removal_decisions.csv")
    field = "Mean AP change after removal"
    strongest = sorted(trials, key=lambda row: abs(float(row[field])), reverse=True)[:8]
    values = [float(row[field]) for row in strongest]
    fig, ax = plt.subplots(figsize=(6.2, 4.3), layout="constrained")
    ax.barh([row["Variable"] for row in strongest], values,
            color=[TEAL if value > 0 else BLUE for value in values])
    ax.axvline(0, color=GREY, linewidth=1)
    ax.invert_yaxis()
    ax.set_xlabel("Change in average precision after removing one input")
    ax.tick_params(axis="y", labelsize=8)
    save(fig, "input-removal")


if __name__ == "__main__":
    plot_classification()
    plot_input_removal()
    plot_forecast("booking_entries_h2_assessment.csv", "booking", "Bookings")
    plot_forecast("booked_hours_h1_assessment.csv", "hours", "Appointment hours")
