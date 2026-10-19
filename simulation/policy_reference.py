"""
simulation/policy_reference.py
Python reference implementation of the three edge IoT sampling policies:
  1. Fixed-Rate Sampling (Baseline)
  2. Threshold-Adaptive Sampling (with Hysteresis & Recovery Hold)
  3. Predictive-Adaptive Sampling (Linear Trend Slope Pre-trigger with Safe Fallback)

This serves as the exact reference model matching hardware/firmware/esp32_adaptive_sensing/esp32_adaptive_sensing.ino.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class PolicyType(str, Enum):
    FIXED = "fixed"
    THRESHOLD = "threshold"
    PREDICTIVE = "predictive"


@dataclass
class PolicyDecision:
    policy: PolicyType
    next_interval_ms: int
    is_event: bool
    is_approaching: bool
    slope: float
    reason: str


class SamplingPolicy:
    """Base class for edge sampling policies."""

    def __init__(
        self,
        fixed_interval_ms: int = 1000,
        idle_interval_ms: int = 800,
        active_interval_ms: int = 100,
        threshold_g: float = 0.35,
        **kwargs,
    ):
        self.fixed_interval_ms = fixed_interval_ms
        self.idle_interval_ms = idle_interval_ms
        self.active_interval_ms = active_interval_ms
        self.threshold_g = threshold_g
        self.last_event_state = False

    def decide(self, reading: float, device_t_ms: int) -> PolicyDecision:
        raise NotImplementedError

    def reset(self):
        self.last_event_state = False


class FixedRatePolicy(SamplingPolicy):
    """
    Policy A: Fixed-Rate Sampling.
    Samples at a strictly constant frequency (baseline).
    Evaluates threshold crossing only for ground-truth event tagging.
    """

    def decide(self, reading: float, device_t_ms: int) -> PolicyDecision:
        is_event = abs(reading) > self.threshold_g
        self.last_event_state = is_event
        return PolicyDecision(
            policy=PolicyType.FIXED,
            next_interval_ms=self.fixed_interval_ms,
            is_event=is_event,
            is_approaching=False,
            slope=0.0,
            reason="fixed_constant_rate",
        )


class ThresholdAdaptivePolicy(SamplingPolicy):
    """
    Policy B: Threshold-Adaptive Sampling.
    Hysteresis & Recovery Hold:
      When vibration exceeds threshold_g, immediately switches to high sampling rate (active_interval_ms).
      When vibration drops below threshold_g, maintains active rate for recovery_hold_samples
      before dropping back to idle_interval_ms. This eliminates rapid flapping/chattering.
    """

    def __init__(
        self,
        fixed_interval_ms: int = 1000,
        idle_interval_ms: int = 800,
        active_interval_ms: int = 100,
        threshold_g: float = 0.35,
        recovery_hold_samples: int = 4,
        **kwargs,
    ):
        super().__init__(fixed_interval_ms, idle_interval_ms, active_interval_ms, threshold_g, **kwargs)
        self.recovery_hold_samples = recovery_hold_samples
        self._hold_counter = 0

    def decide(self, reading: float, device_t_ms: int) -> PolicyDecision:
        is_event = abs(reading) > self.threshold_g

        if is_event:
            self._hold_counter = self.recovery_hold_samples
            next_interval = self.active_interval_ms
            reason = "threshold_exceeded"
        elif self._hold_counter > 0:
            self._hold_counter -= 1
            next_interval = self.active_interval_ms
            reason = f"recovery_hold_active ({self._hold_counter} remaining)"
        else:
            next_interval = self.idle_interval_ms
            reason = "below_threshold_idle"

        self.last_event_state = is_event
        return PolicyDecision(
            policy=PolicyType.THRESHOLD,
            next_interval_ms=next_interval,
            is_event=is_event,
            is_approaching=False,
            slope=0.0,
            reason=reason,
        )

    def reset(self):
        super().reset()
        self._hold_counter = 0


class PredictiveAdaptivePolicy(SamplingPolicy):
    """
    Policy C: Predictive-Adaptive Sampling.
    Predicts an impending event by tracking a sliding trend buffer.
    Prediction Method:
      - A circular buffer of size `trend_window` (default 6) stores recent sensor readings.
      - First-order slope is calculated: slope = (current_reading - oldest_in_window) / trend_window.
      - If |slope| > trend_slope_trigger, an impending event is predicted and sampling is
        pre-emptively ramped up to active_interval_ms before the threshold is officially crossed.
    Safe Fallbacks:
      - If the buffer is not yet full (< trend_window samples), falls back safely to threshold logic.
      - Includes recovery hold hysteresis post-event to prevent rapid oscillation.
    """

    def __init__(
        self,
        fixed_interval_ms: int = 1000,
        idle_interval_ms: int = 800,
        active_interval_ms: int = 100,
        threshold_g: float = 0.35,
        trend_window: int = 6,
        trend_slope_trigger: float = 0.035,
        recovery_hold_samples: int = 4,
        **kwargs,
    ):
        super().__init__(fixed_interval_ms, idle_interval_ms, active_interval_ms, threshold_g, **kwargs)
        self.trend_window = trend_window
        self.trend_slope_trigger = trend_slope_trigger
        self.recovery_hold_samples = recovery_hold_samples

        self._buffer: List[float] = []
        self._buffer_index = 0
        self._buffer_filled = False
        self._raw_buffer = [0.0] * trend_window
        self._hold_counter = 0

    def decide(self, reading: float, device_t_ms: int) -> PolicyDecision:
        # Update circular buffer (identical to esp32_adaptive_sensing.ino)
        oldest = self._raw_buffer[self._buffer_index]
        self._raw_buffer[self._buffer_index] = reading
        self._buffer_index = (self._buffer_index + 1) % self.trend_window
        if self._buffer_index == 0:
            self._buffer_filled = True

        slope = 0.0
        if self._buffer_filled:
            slope = (reading - oldest) / self.trend_window

        is_event = abs(reading) > self.threshold_g
        approaching_event = self._buffer_filled and (abs(slope) > self.trend_slope_trigger)

        if is_event:
            self._hold_counter = self.recovery_hold_samples
            next_interval = self.active_interval_ms
            reason = "event_active"
        elif approaching_event:
            self._hold_counter = self.recovery_hold_samples
            next_interval = self.active_interval_ms
            reason = f"predictive_pre_trigger (slope={slope:.4f})"
        elif self._hold_counter > 0:
            self._hold_counter -= 1
            next_interval = self.active_interval_ms
            reason = f"predictive_hold_active ({self._hold_counter} remaining)"
        else:
            next_interval = self.idle_interval_ms
            reason = "normal_idle"

        self.last_event_state = is_event
        return PolicyDecision(
            policy=PolicyType.PREDICTIVE,
            next_interval_ms=next_interval,
            is_event=is_event,
            is_approaching=approaching_event,
            slope=round(slope, 5),
            reason=reason,
        )

    def reset(self):
        super().reset()
        self._buffer_index = 0
        self._buffer_filled = False
        self._raw_buffer = [0.0] * self.trend_window
        self._hold_counter = 0


def create_policy(policy_name: str, **kwargs) -> SamplingPolicy:
    """Factory helper to instantiate a policy by name."""
    clean_name = policy_name.lower().strip()
    if clean_name in ("fixed", "fixed_rate", "fixed-rate"):
        return FixedRatePolicy(**kwargs)
    elif clean_name in ("threshold", "threshold_adaptive", "threshold-adaptive"):
        return ThresholdAdaptivePolicy(**kwargs)
    elif clean_name in ("predictive", "predictive_adaptive", "predictive-adaptive"):
        return PredictiveAdaptivePolicy(**kwargs)
    raise ValueError(f"Unknown policy name: {policy_name}")
