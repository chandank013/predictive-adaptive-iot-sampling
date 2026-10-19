"""
tests/test_simulator.py
Unit tests verifying the simulated edge IoT sensor models:
  - ADXL345 vibration model
  - INA219 current/power model
  - Deterministic reproducibility with random seeds
"""

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from simulation.sensor_simulator import EdgeSensorSimulator, SimulatedEvent


class TestEdgeSensorSimulator(unittest.TestCase):

    def test_ambient_resting_signal(self):
        sim = EdgeSensorSimulator(seed=100)
        # At t=1000ms (calm period before any scheduled event)
        sample = sim.sample(t_ms=1000, interval_ms=800)

        self.assertTrue(sample.is_simulated)
        self.assertFalse(sample.ground_truth_event)
        self.assertGreater(sample.vibration_g, 0.01)
        self.assertLess(sample.vibration_g, 0.25)
        self.assertGreater(sample.voltage_V, 3.3)
        self.assertLessEqual(sample.voltage_V, 3.75)
        self.assertGreater(sample.current_mA, 1.0)
        self.assertGreater(sample.power_mW, 0.0)

    def test_event_onset_and_peak(self):
        event = SimulatedEvent(start_ms=5000, duration_ms=4000, peak_g=1.5, ramp_up_ms=1000)
        sim = EdgeSensorSimulator(seed=42, events=[event])

        # Before event
        s_before = sim.sample(4000, 800)
        self.assertFalse(s_before.ground_truth_event)
        self.assertLess(s_before.vibration_g, 0.30)

        # During event peak
        s_peak = sim.sample(7000, 100)
        self.assertTrue(s_peak.ground_truth_event)
        self.assertGreater(s_peak.vibration_g, 1.0)

        # After event recovery
        s_after = sim.sample(11000, 800)
        self.assertFalse(s_after.ground_truth_event)
        self.assertLess(s_after.vibration_g, 0.30)

    def test_deterministic_reproducibility(self):
        sim1 = EdgeSensorSimulator(seed=42)
        sim2 = EdgeSensorSimulator(seed=42)

        readings1 = [sim1.sample(t, 100).vibration_g for t in range(0, 10000, 1000)]
        readings2 = [sim2.sample(t, 100).vibration_g for t in range(0, 10000, 1000)]

        self.assertEqual(readings1, readings2)

    def test_current_scaling_with_sampling_rate(self):
        sim = EdgeSensorSimulator(seed=42)
        # Fast sampling (100ms) has higher duty cycle -> higher avg current
        fast_samples = [sim.generate_energy(100)[0] for _ in range(20)]
        # Slow sampling (800ms) spends most time in light sleep -> lower avg current
        slow_samples = [sim.generate_energy(800)[0] for _ in range(20)]

        avg_fast = sum(fast_samples) / len(fast_samples)
        avg_slow = sum(slow_samples) / len(slow_samples)

        self.assertGreater(avg_fast, avg_slow)


if __name__ == "__main__":
    unittest.main()
