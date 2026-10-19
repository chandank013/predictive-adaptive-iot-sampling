"""
tests/test_policies.py
Unit tests verifying the 3 edge IoT sampling policies:
  1. Fixed-Rate Sampling
  2. Threshold-Adaptive Sampling (with Hysteresis / Recovery Hold)
  3. Predictive-Adaptive Sampling (with Sliding Trend Buffer & Warmup Fallback)
"""

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from simulation.policy_reference import (
    FixedRatePolicy,
    ThresholdAdaptivePolicy,
    PredictiveAdaptivePolicy,
    PolicyType,
    create_policy,
)


class TestSamplingPolicies(unittest.TestCase):

    def test_fixed_rate_policy(self):
        policy = FixedRatePolicy(fixed_interval_ms=1000, threshold_g=0.35)

        # Baseline noise reading
        d1 = policy.decide(0.08, 1000)
        self.assertEqual(d1.next_interval_ms, 1000)
        self.assertFalse(d1.is_event)
        self.assertEqual(d1.policy, PolicyType.FIXED)

        # Spike reading: interval MUST stay strictly constant
        d2 = policy.decide(1.45, 2000)
        self.assertEqual(d2.next_interval_ms, 1000)
        self.assertTrue(d2.is_event)

    def test_threshold_adaptive_policy_with_hysteresis(self):
        policy = ThresholdAdaptivePolicy(
            idle_interval_ms=800,
            active_interval_ms=100,
            threshold_g=0.35,
            recovery_hold_samples=3,
        )

        # 1. Idle reading
        d = policy.decide(0.10, 800)
        self.assertEqual(d.next_interval_ms, 800)
        self.assertFalse(d.is_event)

        # 2. Exceed threshold -> switch to high rate
        d = policy.decide(0.65, 1600)
        self.assertEqual(d.next_interval_ms, 100)
        self.assertTrue(d.is_event)

        # 3. Reading drops below threshold -> recovery hold should keep rate at 100ms
        d_hold1 = policy.decide(0.12, 1700)
        self.assertEqual(d_hold1.next_interval_ms, 100)
        self.assertFalse(d_hold1.is_event)
        self.assertIn("recovery_hold_active", d_hold1.reason)

        d_hold2 = policy.decide(0.11, 1800)
        self.assertEqual(d_hold2.next_interval_ms, 100)

        d_hold3 = policy.decide(0.09, 1900)
        self.assertEqual(d_hold3.next_interval_ms, 100)

        # 4. Hold counter exhausted -> drops back to idle rate (800ms)
        d_idle = policy.decide(0.08, 2000)
        self.assertEqual(d_idle.next_interval_ms, 800)
        self.assertFalse(d_idle.is_event)

    def test_predictive_adaptive_policy(self):
        policy = PredictiveAdaptivePolicy(
            idle_interval_ms=800,
            active_interval_ms=100,
            threshold_g=0.35,
            trend_window=6,
            trend_slope_trigger=0.03,
            recovery_hold_samples=3,
        )

        # Warmup buffer with constant calm readings (buffer not yet filled)
        for i in range(5):
            d = policy.decide(0.08, i * 800)
            self.assertEqual(d.next_interval_ms, 800)
            self.assertFalse(d.is_approaching)

        # 6th sample fills buffer with flat signal
        d6 = policy.decide(0.08, 5 * 800)
        self.assertEqual(d6.next_interval_ms, 800)
        self.assertFalse(d6.is_approaching)

        # Feed rising vibration ramp that does NOT yet exceed threshold (0.28 < 0.35)
        # Oldest was 0.08, current is 0.32 -> slope = (0.32 - 0.08)/6 = 0.04 > 0.03 trigger!
        d_ramp = policy.decide(0.32, 6 * 800)
        self.assertEqual(d_ramp.next_interval_ms, 100)
        self.assertTrue(d_ramp.is_approaching)
        self.assertFalse(d_ramp.is_event)
        self.assertIn("predictive_pre_trigger", d_ramp.reason)

    def test_create_policy_factory(self):
        p_fixed = create_policy("fixed")
        self.assertIsInstance(p_fixed, FixedRatePolicy)

        p_thresh = create_policy("threshold")
        self.assertIsInstance(p_thresh, ThresholdAdaptivePolicy)

        p_pred = create_policy("predictive")
        self.assertIsInstance(p_pred, PredictiveAdaptivePolicy)

        with self.assertRaises(ValueError):
            create_policy("unknown_policy_name")


if __name__ == "__main__":
    unittest.main()
