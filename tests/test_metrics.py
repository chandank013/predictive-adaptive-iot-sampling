"""
tests/test_metrics.py
Unit tests verifying evaluation metrics calculations:
  - Energy (Riemann sum trapezoidal integration)
  - Power (average and peak)
  - Latency and Accuracy proxy
  - Bandwidth estimate
  - Policy rate switching
"""

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from backend.analysis.compute_metrics import (
    compute_energy_mJ,
    compute_power_metrics,
    compute_detection_latency_ms,
    compute_accuracy_proxy,
    compute_bandwidth_bytes,
    compute_policy_switches,
)


class TestMetricsCalculations(unittest.TestCase):

    def test_energy_mJ_trapezoidal(self):
        # 10 seconds of 20 mA at 3.7V:
        # Energy = 20 mA * 3.7 V * 10 s = 740 mJ
        docs = [
            {"device_t_ms": 0, "current_mA": 20.0, "voltage_V": 3.7},
            {"device_t_ms": 5000, "current_mA": 20.0, "voltage_V": 3.7},
            {"device_t_ms": 10000, "current_mA": 20.0, "voltage_V": 3.7},
        ]
        energy = compute_energy_mJ(docs)
        self.assertAlmostEqual(energy, 740.0, delta=0.5)

    def test_power_metrics(self):
        docs = [
            {"current_mA": 10.0},
            {"current_mA": 30.0},
            {"current_mA": 20.0},
        ]
        stats = compute_power_metrics(docs)
        self.assertEqual(stats["avg_current_mA"], 20.0)
        self.assertEqual(stats["peak_current_mA"], 30.0)
        # Power = I * 3.7V
        self.assertEqual(stats["avg_power_mW"], 74.0)
        self.assertEqual(stats["peak_power_mW"], 111.0)

    def test_latency_and_accuracy(self):
        # Detected 500ms after event started -> latency = 500 ms
        events = [{"device_t_ms": 10500, "event": True}]
        readings = []
        latency = compute_detection_latency_ms(events, readings, true_event_start_ms=10000)
        self.assertEqual(latency, 500)

        # Accuracy = 100 / (1 + 0.5s) = 66.7%
        acc = compute_accuracy_proxy(latency)
        self.assertAlmostEqual(acc, 66.7, places=1)

        # Predictive pre-trigger: detected 200ms BEFORE event starts -> latency = -200 ms
        latency_pred = -200
        acc_pred = compute_accuracy_proxy(latency_pred)
        self.assertEqual(acc_pred, 100.0)

    def test_bandwidth_bytes(self):
        # 10 readings + 2 events + 10 energy docs = 22 messages * 80 bytes = 1760 bytes
        readings = [{}] * 10
        events = [{}] * 2
        energy = [{}] * 10
        bw = compute_bandwidth_bytes(readings, events, energy)
        self.assertEqual(bw, 1760)

    def test_policy_switches(self):
        readings = [
            {"next_interval_ms": 800},
            {"next_interval_ms": 800},
            {"next_interval_ms": 100},  # switch 1
            {"next_interval_ms": 100},
            {"next_interval_ms": 800},  # switch 2
        ]
        switches = compute_policy_switches(readings)
        self.assertEqual(switches, 2)


if __name__ == "__main__":
    unittest.main()
