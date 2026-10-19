"""
compute_metrics.py
Computes edge IoT evaluation metrics (accuracy, energy, latency, power, bandwidth)
for experimental trials from MongoDB.

Formulas and Units Reference:
  - Samples Taken: Total sensor reading records collected during trial [count, simulated]
  - Trial Duration: (last_reading_t_ms - first_reading_t_ms) / 1000.0 [seconds, simulated]
  - Average Sampling Frequency: samples_taken / duration_s [Hz, calculated]
  - Detection Latency: (first_detected_event_t_ms - true_event_start_ms) [milliseconds, calculated]
      * Note: Can be negative when the predictive policy pre-triggers before the event peak.
  - Detection Accuracy: 100.0 / (1.0 + max(latency_ms, 0) / 1000.0) [%, latency-based proxy]
  - Energy Consumption: sum_{i} (current_mA_i * Supply_Voltage (3.7V) * dt_s_i) [mJ, estimated]
  - Average Power: avg_current_mA * Supply_Voltage (3.7V) [mW, simulated]
  - Peak Power: max_current_mA * Supply_Voltage (3.7V) [mW, simulated]
  - Network Bandwidth: total_messages * 80 bytes/payload [bytes, estimated]
  - Policy Transitions: Count of rate adjustments between idle and active [count, calculated]
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.append(str(Path(__file__).resolve().parent.parent))
from database.db import get_db  # noqa: E402

ASSUMED_PAYLOAD_BYTES = 80  # JSON payload size estimate per MQTT message
NOMINAL_VOLTAGE = 3.7       # 3.7V nominal Li-ion cell voltage


def get_trial_readings(db, trial_id: str) -> List[Dict[str, Any]]:
    return list(db.readings.find({"trial_id": trial_id}).sort("device_t_ms", 1))


def get_trial_events(db, trial_id: str) -> List[Dict[str, Any]]:
    return list(db.events.find({"trial_id": trial_id}).sort("device_t_ms", 1))


def get_trial_energy(db, trial_id: str) -> List[Dict[str, Any]]:
    return list(db.energy.find({"trial_id": trial_id}).sort("device_t_ms", 1))


def compute_detection_latency_ms(
    events: List[Dict[str, Any]],
    readings: List[Dict[str, Any]],
    true_event_start_ms: Optional[int],
) -> Optional[int]:
    """
    Time of the first logged event flag or first active interval onset during event,
    minus the ground-truth event start time. Can be negative for predictive policy.
    """
    if true_event_start_ms is None:
        return None

    # Check event collection
    for e in events:
        if e.get("event"):
            return int(e["device_t_ms"] - true_event_start_ms)

    # Fallback to high-rate reading transition
    for r in readings:
        if r.get("value", 0.0) >= 0.35 and r.get("device_t_ms", 0) >= true_event_start_ms - 2000:
            return int(r["device_t_ms"] - true_event_start_ms)

    return None


def compute_accuracy_proxy(detection_latency_ms: Optional[int]) -> float:
    """Latency-based accuracy proxy: 100% at <= 0 ms latency, scaling down with delay."""
    if detection_latency_ms is None:
        return 0.0
    latency_s = max(detection_latency_ms, 0) / 1000.0
    return round(100.0 / (1.0 + latency_s), 1)


def compute_energy_mJ(energy_docs: List[Dict[str, Any]]) -> Optional[float]:
    """Trapezoidal Riemann sum energy estimate: sum(I_mA * V * dt_s) [mJ]."""
    if len(energy_docs) < 2:
        return None
    total_mJ = 0.0
    for prev, curr in zip(energy_docs, energy_docs[1:]):
        dt_s = (curr["device_t_ms"] - prev["device_t_ms"]) / 1000.0
        if dt_s <= 0 or dt_s > 10.0:
            continue
        v = curr.get("voltage_V", NOMINAL_VOLTAGE)
        total_mJ += prev.get("current_mA", 0.0) * v * dt_s
    return round(total_mJ, 2)


def compute_power_metrics(energy_docs: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    if not energy_docs:
        return {
            "avg_current_mA": None,
            "peak_current_mA": None,
            "avg_power_mW": None,
            "peak_power_mW": None,
        }
    currents = [d.get("current_mA", 0.0) for d in energy_docs if d.get("current_mA") is not None]
    if not currents:
        return {
            "avg_current_mA": None,
            "peak_current_mA": None,
            "avg_power_mW": None,
            "peak_power_mW": None,
        }
    avg_i = sum(currents) / len(currents)
    peak_i = max(currents)
    return {
        "avg_current_mA": round(avg_i, 2),
        "peak_current_mA": round(peak_i, 2),
        "avg_power_mW": round(avg_i * NOMINAL_VOLTAGE, 2),
        "peak_power_mW": round(peak_i * NOMINAL_VOLTAGE, 2),
    }


def compute_bandwidth_bytes(readings: list, events: list, energy_docs: list) -> int:
    total_messages = len(readings) + len(events) + len(energy_docs)
    return total_messages * ASSUMED_PAYLOAD_BYTES


def compute_policy_switches(readings: List[Dict[str, Any]]) -> int:
    switches = 0
    prev_interval = None
    for r in readings:
        curr_interval = r.get("next_interval_ms")
        if curr_interval is not None:
            if prev_interval is not None and curr_interval != prev_interval:
                switches += 1
            prev_interval = curr_interval
    return switches


def compute_trial_summary(trial_id: str, true_event_start_ms: Optional[int] = None) -> Dict[str, Any]:
    db = get_db()
    trial = db.trials.find_one({"trial_id": trial_id})
    if trial is None:
        raise ValueError(f"No trial found with trial_id='{trial_id}'")

    readings = get_trial_readings(db, trial_id)
    events = get_trial_events(db, trial_id)
    energy_docs = get_trial_energy(db, trial_id)

    # Auto-resolve true_event_start_ms if saved in trial document
    if true_event_start_ms is None and trial.get("true_event_start_ms") is not None:
        true_event_start_ms = trial["true_event_start_ms"]

    latency_ms = compute_detection_latency_ms(events, readings, true_event_start_ms)
    accuracy_pct = compute_accuracy_proxy(latency_ms)
    energy_mJ = compute_energy_mJ(energy_docs)
    power_stats = compute_power_metrics(energy_docs)
    bandwidth_bytes = compute_bandwidth_bytes(readings, events, energy_docs)
    policy_switches = compute_policy_switches(readings)

    # Compute duration and average frequency
    duration_s = 0.0
    avg_freq_hz = 0.0
    if len(readings) >= 2:
        duration_s = round((readings[-1]["device_t_ms"] - readings[0]["device_t_ms"]) / 1000.0, 2)
        if duration_s > 0:
            avg_freq_hz = round(len(readings) / duration_s, 2)

    events_logged = sum(1 for e in events if e.get("event"))
    has_event_detected = events_logged > 0 or any(r.get("value", 0.0) >= 0.35 for r in readings)

    return {
        "trial_id": trial_id,
        "policy": trial.get("policy"),
        "trigger_sensitivity": trial.get("trigger_sensitivity"),
        "is_simulated": trial.get("is_simulated", True),
        "mode": trial.get("mode", "SIMULATION"),
        "samples_taken": len(readings),
        "duration_s": duration_s,
        "avg_sampling_freq_hz": avg_freq_hz,
        "events_logged": events_logged,
        "event_detected": has_event_detected,
        "detection_latency_ms": latency_ms,
        "accuracy_pct": accuracy_pct,
        "energy_mJ": energy_mJ,
        "avg_power_mW": power_stats["avg_power_mW"],
        "peak_power_mW": power_stats["peak_power_mW"],
        "avg_current_mA": power_stats["avg_current_mA"],
        "peak_current_mA": power_stats["peak_current_mA"],
        "bandwidth_bytes": bandwidth_bytes,
        "policy_switches": policy_switches,
    }


def main():
    parser = argparse.ArgumentParser(description="Compute evaluation metrics for one trial.")
    parser.add_argument("--trial-id", required=True)
    parser.add_argument(
        "--true-event-start-ms",
        type=int,
        default=None,
        help="Ground-truth device_t_ms when the induced event started",
    )
    args = parser.parse_args()

    summary = compute_trial_summary(args.trial_id, args.true_event_start_ms)
    print(f"\n=== Trial summary: {summary['trial_id']} ===")
    for k, v in summary.items():
        print(f"{k:24s}: {v}")


if __name__ == "__main__":
    main()
