"""
simulation/sensor_simulator.py
Realistic, reproducible dummy sensor generation for the Adaptive IoT Sensing project.
Simulates:
  - ADXL345 3-axis accelerometer (vibration magnitude deviation from 1g baseline)
  - INA219 current/power sensor (active vs light-sleep current on 3.7V Li-ion supply)
  - Configurable deterministic event generator with onset ramp, peak, duration, and recovery decay.
  - Fixed random seed support for reproducible comparative trials.

NOTE: All generated data is strictly marked as simulated data.
"""

import math
import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class SimulatedEvent:
    start_ms: int
    duration_ms: int
    peak_g: float = 1.35
    ramp_up_ms: int = 800   # onset ramp before peak
    ramp_down_ms: int = 600 # decay back to baseline

    @property
    def end_ms(self) -> int:
        return self.start_ms + self.duration_ms


@dataclass
class SensorReading:
    device_t_ms: int
    seq_num: int
    vibration_g: float
    current_mA: float
    voltage_V: float
    power_mW: float
    ground_truth_event: bool
    is_simulated: bool = True


class EdgeSensorSimulator:
    """
    Simulates the physical edge hardware (ESP32 + ADXL345 + INA219).
    """

    def __init__(
        self,
        seed: Optional[int] = 42,
        baseline_noise_std: float = 0.025,
        nominal_voltage: float = 3.7,
        active_current_mA: float = 78.0,
        tx_burst_current_mA: float = 140.0,
        light_sleep_current_mA: float = 3.2,
        sample_active_duration_ms: float = 18.0,
        events: Optional[List[SimulatedEvent]] = None,
    ):
        self.seed = seed
        self.rng = random.Random(seed)
        self.baseline_noise_std = baseline_noise_std
        self.nominal_voltage = nominal_voltage
        self.active_current_mA = active_current_mA
        self.tx_burst_current_mA = tx_burst_current_mA
        self.light_sleep_current_mA = light_sleep_current_mA
        self.sample_active_duration_ms = sample_active_duration_ms

        if events is None:
            # Default deterministic event schedule: realistic motor vibration bursts with onset ramp
            self.events = [
                SimulatedEvent(start_ms=10000, duration_ms=8000, peak_g=1.45, ramp_up_ms=1800, ramp_down_ms=800),
                SimulatedEvent(start_ms=26000, duration_ms=8000, peak_g=1.50, ramp_up_ms=1800, ramp_down_ms=800),
            ]
        else:
            self.events = events

        self.seq_num = 0

    def reset(self, seed: Optional[int] = None):
        """Reset random generator and sequence counter."""
        if seed is not None:
            self.seed = seed
        self.rng = random.Random(self.seed)
        self.seq_num = 0

    def is_in_ground_truth_event(self, t_ms: int) -> bool:
        """Ground truth event state (true when within any scheduled event window)."""
        for ev in self.events:
            if ev.start_ms <= t_ms <= ev.end_ms:
                return True
        return False

    def generate_vibration_g(self, t_ms: int) -> Tuple[float, bool]:
        """
        Generates simulated vibration magnitude deviation from 1g.
        Returns (vibration_g, is_ground_truth_event).
        """
        # Baseline noise (ambient bench / motor off)
        t_sec = t_ms / 1000.0
        ambient = 0.08 + 0.02 * math.sin(t_sec * 2.0) + self.rng.gauss(0, self.baseline_noise_std)
        ambient = max(0.01, ambient)

        event_val = 0.0
        is_event = False

        for ev in self.events:
            if ev.start_ms <= t_ms <= ev.end_ms:
                is_event = True
                elapsed = t_ms - ev.start_ms
                remaining = ev.end_ms - t_ms

                # Onset ramp: gradual build up of vibration
                if elapsed < ev.ramp_up_ms:
                    progress = elapsed / ev.ramp_up_ms
                    envelope = 0.15 + (ev.peak_g - 0.15) * (progress ** 1.5)
                # Recovery ramp: gradual decay back to quiet
                elif remaining < ev.ramp_down_ms:
                    progress = remaining / ev.ramp_down_ms
                    envelope = 0.15 + (ev.peak_g - 0.15) * (progress ** 1.2)
                # Steady-state peak vibration with motor harmonic
                else:
                    envelope = ev.peak_g

                # Motor harmonic oscillations + vibration noise
                harmonic = 0.18 * math.sin(t_sec * 35.0) + 0.08 * math.cos(t_sec * 72.0)
                jitter = self.rng.gauss(0, 0.04)
                event_val = max(event_val, envelope + harmonic + jitter)

        final_g = max(0.01, ambient + event_val)
        return round(final_g, 4), is_event

    def generate_energy(self, interval_ms: int) -> Tuple[float, float, float]:
        """
        Simulates INA219 current, voltage, and instantaneous power based on ESP32 light-sleep cycle.
        Interval-averaged current:
          I_avg = (t_active * I_active + (interval - t_active) * I_sleep) / interval
        """
        t_active = min(float(interval_ms), self.sample_active_duration_ms)
        t_sleep = max(0.0, float(interval_ms) - t_active)

        # Base active current with occasional WiFi TX spike
        has_tx = (self.rng.random() < 0.4)
        active_draw = self.tx_burst_current_mA if has_tx else self.active_current_mA
        active_draw += self.rng.gauss(0, 2.5)

        sleep_draw = self.light_sleep_current_mA + self.rng.gauss(0, 0.2)
        sleep_draw = max(1.0, sleep_draw)

        avg_current_mA = (t_active * active_draw + t_sleep * sleep_draw) / float(interval_ms)
        # Small battery voltage droop under higher current
        voltage_drop = (avg_current_mA / 1000.0) * 0.15
        voltage_V = round(max(3.3, self.nominal_voltage - voltage_drop + self.rng.gauss(0, 0.01)), 3)
        power_mW = round(avg_current_mA * voltage_V, 2)

        return round(avg_current_mA, 2), voltage_V, power_mW

    def sample(self, t_ms: int, interval_ms: int) -> SensorReading:
        """Generate a complete simulated sensor reading packet."""
        self.seq_num += 1
        vibration, is_event = self.generate_vibration_g(t_ms)
        current_mA, voltage_V, power_mW = self.generate_energy(interval_ms)

        return SensorReading(
            device_t_ms=t_ms,
            seq_num=self.seq_num,
            vibration_g=vibration,
            current_mA=current_mA,
            voltage_V=voltage_V,
            power_mW=power_mW,
            ground_truth_event=is_event,
            is_simulated=True,
        )
