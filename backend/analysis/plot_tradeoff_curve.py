"""
plot_tradeoff_curve.py
Builds the project's key result: the accuracy-vs-energy trade-off curve
across all logged trials, grouped by policy. This is the offline
equivalent of the Trial Results page's chart in the frontend, and is
what ultimately feeds Deliverable 8 (Experimental Evaluation).

Run:
    python analysis/plot_tradeoff_curve.py --true-event-start-ms 10000
Produces:
    tradeoff_curve.png

Note: "accuracy" here is estimated as 1 / (1 + detection_latency_s) when
a true_event_start_ms is supplied, purely as a placeholder scoring
function until a real labeled multi-event dataset (Deliverable 5) is
available. Replace compute_accuracy() below once you have ground-truth
labels for correct/incorrect detections across multiple induced events
per trial, rather than a single-event proxy.
"""

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from database.db import get_db  # noqa: E402
from analysis.compute_metrics import compute_trial_summary  # noqa: E402

POLICY_COLORS = {
    "fixed": "#3366cc",
    "threshold": "#e08a2c",
    "predictive": "#1a9b6c",
}
POLICY_LABELS = {
    "fixed": "Fixed-rate",
    "threshold": "Threshold-adaptive",
    "predictive": "Predictive-adaptive",
}


def compute_accuracy(detection_latency_ms):
    """Placeholder single-event accuracy proxy — see module docstring."""
    if detection_latency_ms is None:
        return 0.0
    latency_s = max(detection_latency_ms, 0) / 1000.0
    return round(100.0 / (1.0 + latency_s), 1)


def main():
    parser = argparse.ArgumentParser(description="Plot accuracy-vs-energy trade-off curve across all trials.")
    parser.add_argument("--true-event-start-ms", type=int, required=True,
                         help="Ground-truth device_t_ms when the induced event started (shared across trials in this run)")
    parser.add_argument("--out", default="tradeoff_curve.png")
    args = parser.parse_args()

    db = get_db()
    trial_ids = [t["trial_id"] for t in db.trials.find({}, {"trial_id": 1})]

    by_policy = {"fixed": [], "threshold": [], "predictive": []}
    for trial_id in trial_ids:
        try:
            summary = compute_trial_summary(trial_id, args.true_event_start_ms)
        except ValueError:
            continue
        policy = summary["policy"]
        if policy not in by_policy or summary["energy_mJ"] is None:
            continue
        accuracy = compute_accuracy(summary["detection_latency_ms"])
        by_policy[policy].append((summary["energy_mJ"], accuracy, trial_id))

    fig, ax = plt.subplots(figsize=(9, 6))
    any_points = False
    for policy, points in by_policy.items():
        if not points:
            continue
        points.sort()
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        ax.plot(xs, ys, marker="o", color=POLICY_COLORS[policy], label=POLICY_LABELS[policy])
        any_points = True

    if not any_points:
        print("No trials with both energy and latency data found yet \u2014 "
              "run a few real trials via mqtt_logger.py first.")
        return

    ax.set_xlabel("Energy Consumption per Trial (mJ)")
    ax.set_ylabel("Detection Accuracy (%) [latency-based proxy]")
    ax.set_title("Accuracy vs. Energy Trade-off Curve")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(args.out, dpi=150)
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
