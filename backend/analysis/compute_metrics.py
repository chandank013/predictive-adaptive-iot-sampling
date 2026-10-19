"""
compute_metrics.py
Computes the Deliverable 1 evaluation metrics (accuracy, energy, latency,
bandwidth) for one trial, reading from MongoDB. Used by both the API
(for the dashboard's Trial Results page) and ad-hoc analysis.

Run directly for a quick CLI summary:
    python analysis/compute_metrics.py --trial-id predictive_run_03
"""

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from database.db import get_db  # noqa: E402

ASSUMED_PAYLOAD_BYTES = 80  # rough JSON payload size per MQTT message, for bandwidth estimate


def get_trial_readings(db, trial_id):
    return list(db.readings.find({"trial_id": trial_id}).sort("device_t_ms", 1))


def get_trial_events(db, trial_id):
    return list(db.events.find({"trial_id": trial_id}).sort("device_t_ms", 1))


def get_trial_energy(db, trial_id):
    return list(db.energy.find({"trial_id": trial_id}).sort("device_t_ms", 1))


def compute_detection_latency_ms(events, true_event_start_ms):
    """Time of the first logged event==true, minus the true event start
    time. Can be negative — that's the predictive policy's whole point
    (triggering before the event officially starts) and should be kept,
    not discarded. Returns None if no event was logged, or if
    true_event_start_ms wasn't provided (can't score latency without a
    ground-truth time)."""
    if true_event_start_ms is None:
        return None
    for e in events:
        if e.get("event"):
            return e["device_t_ms"] - true_event_start_ms
    return None


def compute_energy_mJ(energy_docs, sample_duration_ms_estimate=None):
    """Rough trapezoidal-ish energy estimate: for each energy reading,
    assume it represents the current draw for the interval since the
    previous reading (energy[mJ] = current[mA] * voltage[V] * time[s]).
    Assumes a nominal 3.7V Li-ion supply voltage; adjust if measured
    differently."""
    VOLTAGE = 3.7
    if len(energy_docs) < 2:
        return None
    total_mJ = 0.0
    for prev, curr in zip(energy_docs, energy_docs[1:]):
        dt_s = (curr["device_t_ms"] - prev["device_t_ms"]) / 1000.0
        if dt_s <= 0:
            continue
        total_mJ += prev["current_mA"] * VOLTAGE * dt_s
    return round(total_mJ, 2)


def compute_bandwidth_bytes(readings, events, energy_docs):
    total_messages = len(readings) + len(events) + len(energy_docs)
    return total_messages * ASSUMED_PAYLOAD_BYTES


def compute_trial_summary(trial_id, true_event_start_ms=None):
    db = get_db()
    trial = db.trials.find_one({"trial_id": trial_id})
    if trial is None:
        raise ValueError(f"No trial found with trial_id='{trial_id}'")

    readings = get_trial_readings(db, trial_id)
    events = get_trial_events(db, trial_id)
    energy_docs = get_trial_energy(db, trial_id)

    latency_ms = compute_detection_latency_ms(events, true_event_start_ms)
    energy_mJ = compute_energy_mJ(energy_docs)
    bandwidth_bytes = compute_bandwidth_bytes(readings, events, energy_docs)

    return {
        "trial_id": trial_id,
        "policy": trial.get("policy"),
        "trigger_sensitivity": trial.get("trigger_sensitivity"),
        "samples_taken": len(readings),
        "events_logged": sum(1 for e in events if e.get("event")),
        "detection_latency_ms": latency_ms,
        "energy_mJ": energy_mJ,
        "bandwidth_bytes": bandwidth_bytes,
    }


def main():
    parser = argparse.ArgumentParser(description="Compute evaluation metrics for one trial.")
    parser.add_argument("--trial-id", required=True)
    parser.add_argument("--true-event-start-ms", type=int, default=None,
                         help="Ground-truth device_t_ms when the induced event actually started, for latency scoring")
    args = parser.parse_args()

    summary = compute_trial_summary(args.trial_id, args.true_event_start_ms)
    print(f"\n=== Trial summary: {summary['trial_id']} ===")
    for k, v in summary.items():
        print(f"{k:22s}: {v}")


if __name__ == "__main__":
    main()
