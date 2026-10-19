"""
simulation/sim_runner.py
Simulation Runner for Predictive Adaptive IoT Sensing.
Operates the complete simulated sensor -> sampling policy -> MQTT/DB pipeline.

Supports:
  1. Continuous real-time streaming (publishes to MQTT if broker is up, logs to MongoDB & live state)
  2. Multi-policy benchmark execution (runs identical deterministic scenarios across fixed, threshold, predictive)
  3. Seamless fallback when no MQTT broker is present.
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

# Ensure project root and backend dir are on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
for p in (str(PROJECT_ROOT), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    import paho.mqtt.client as mqtt
    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False

from database.db import ensure_indexes, get_db
from simulation.policy_reference import (
    FixedRatePolicy,
    PolicyDecision,
    PolicyType,
    PredictiveAdaptivePolicy,
    SamplingPolicy,
    ThresholdAdaptivePolicy,
    create_policy,
)
from simulation.sensor_simulator import EdgeSensorSimulator, SimulatedEvent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sim_runner")


class SimulationController:
    """Manages sensor simulation state, policy execution, MQTT publishing, and DB persistence."""

    def __init__(
        self,
        node_id: str = "node01",
        broker: str = "localhost",
        port: int = 1883,
        trial_id: Optional[str] = None,
        policy_name: str = "predictive",
        seed: int = 42,
        trigger_sensitivity: float = 0.035,
        threshold_g: float = 0.35,
    ):
        self.node_id = node_id
        self.broker = broker
        self.port = port
        self.trial_id = trial_id or f"sim_{policy_name}_{int(time.time())}"
        self.seed = seed
        self.trigger_sensitivity = trigger_sensitivity
        self.threshold_g = threshold_g

        self.policy: SamplingPolicy = create_policy(
            policy_name,
            threshold_g=threshold_g,
            trend_slope_trigger=trigger_sensitivity,
        )
        self.active_policy_name = policy_name

        self.simulator = EdgeSensorSimulator(seed=seed)
        self.mqtt_client: Optional[mqtt.Client] = None
        self.mqtt_connected = False
        self.running = False
        self.current_t_ms = 0
        self.latest_reading: Optional[Dict] = None
        self.recent_readings: List[Dict] = []
        self.recent_events: List[Dict] = []
        self.recent_energy: List[Dict] = []
        self.last_published_event_state: Optional[bool] = None
        self.last_ground_truth_state: Optional[bool] = None
        self.total_packets_sent = 0
        self.start_time: Optional[datetime] = None

        self.db = get_db()
        ensure_indexes()
        self._init_mqtt()

    def _init_mqtt(self):
        if not PAHO_AVAILABLE:
            logger.info("[MQTT] paho-mqtt not available; using direct storage fallback.")
            return

        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                self.mqtt_connected = True
                logger.info(f"[MQTT] Connected to broker at {self.broker}:{self.port}")
                topic_policy = f"sensor/{self.node_id}/policy/set"
                client.subscribe(topic_policy)
                logger.info(f"[MQTT] Subscribed to {topic_policy}")
            else:
                self.mqtt_connected = False
                logger.warning(f"[MQTT] Connection failed with code {rc}")

        def on_message(client, userdata, msg):
            payload = msg.payload.decode().strip()
            logger.info(f"[MQTT] Received policy update command: {payload}")
            self.set_policy(payload)

        try:
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.on_connect = on_connect
            self.mqtt_client.on_message = on_message
            self.mqtt_client.connect_async(self.broker, self.port, 60)
            self.mqtt_client.loop_start()
        except Exception as exc:
            logger.warning(f"[MQTT] Broker not reachable at {self.broker}:{self.port} ({exc}). Using direct fallback.")
            self.mqtt_connected = False

    def set_policy(self, policy_name: str):
        try:
            self.policy = create_policy(
                policy_name,
                threshold_g=self.threshold_g,
                trend_slope_trigger=self.trigger_sensitivity,
            )
            self.active_policy_name = policy_name
            logger.info(f"Switched active policy to: {policy_name}")
        except ValueError as e:
            logger.error(f"Cannot switch policy: {e}")

    def _publish_mqtt(self, topic: str, payload_dict: dict):
        if self.mqtt_client and self.mqtt_connected:
            try:
                self.mqtt_client.publish(topic, json.dumps(payload_dict))
            except Exception as e:
                logger.debug(f"[MQTT] Publish error: {e}")

    def record_trial_start(self, notes: str = "Simulated trial run"):
        self.start_time = datetime.now(timezone.utc)
        self.db.trials.update_one(
            {"trial_id": self.trial_id},
            {
                "$set": {
                    "trial_id": self.trial_id,
                    "policy": self.active_policy_name,
                    "node_id": self.node_id,
                    "trigger_sensitivity": self.trigger_sensitivity,
                    "threshold_g": self.threshold_g,
                    "notes": notes,
                    "is_simulated": True,
                    "mode": "SIMULATION",
                    "true_event_start_ms": self.simulator.events[0].start_ms if self.simulator.events else 10000,
                    "events_ground_truth": [
                        {"start_ms": e.start_ms, "duration_ms": e.duration_ms, "end_ms": e.end_ms, "peak_g": e.peak_g}
                        for e in self.simulator.events
                    ],
                },
                "$setOnInsert": {"start_time": self.start_time},
            },
            upsert=True,
        )

    def record_trial_end(self):
        end_time = datetime.now(timezone.utc)
        self.db.trials.update_one(
            {"trial_id": self.trial_id},
            {"$set": {"end_time": end_time}},
        )

    def step(self, interval_ms: int) -> Tuple[Dict, PolicyDecision]:
        """
        Executes a single step in the simulation:
        1. Samples simulated vibration & current.
        2. Evaluates the active sampling policy.
        3. Persists records to MongoDB.
        4. Publishes MQTT messages.
        """
        self.current_t_ms += interval_ms
        sample = self.simulator.sample(self.current_t_ms, interval_ms)
        decision = self.policy.decide(sample.vibration_g, self.current_t_ms)

        recv_time = datetime.now(timezone.utc)
        self.total_packets_sent += 1

        reading_doc = {
            "trial_id": self.trial_id,
            "node_id": self.node_id,
            "device_t_ms": sample.device_t_ms,
            "recv_time_utc": recv_time,
            "value": sample.vibration_g,
            "policy": decision.policy.value,
            "next_interval_ms": decision.next_interval_ms,
            "is_simulated": True,
            "seq": sample.seq_num,
        }
        self.db.readings.insert_one(reading_doc)
        self._publish_mqtt(f"sensor/{self.node_id}/reading", {
            "t": sample.device_t_ms,
            "value": sample.vibration_g,
            "policy": decision.policy.value,
            "seq": sample.seq_num,
            "is_simulated": True,
        })

        # Event flag change or approaching prediction trigger
        is_active_trigger = decision.is_event or decision.is_approaching
        if self.last_published_event_state is None or is_active_trigger != self.last_published_event_state:
            event_doc = {
                "trial_id": self.trial_id,
                "node_id": self.node_id,
                "device_t_ms": sample.device_t_ms,
                "recv_time_utc": recv_time,
                "event": is_active_trigger,
                "is_approaching": decision.is_approaching,
                "ground_truth": sample.ground_truth_event,
                "is_simulated": True,
            }
            self.db.events.insert_one(event_doc)
            self._publish_mqtt(f"sensor/{self.node_id}/event", {
                "t": sample.device_t_ms,
                "event": is_active_trigger,
                "is_approaching": decision.is_approaching,
                "is_simulated": True,
            })
            self.recent_events.append(event_doc)
            if len(self.recent_events) > 50:
                self.recent_events.pop(0)
            self.last_published_event_state = is_active_trigger

        # Energy document
        energy_doc = {
            "trial_id": self.trial_id,
            "node_id": self.node_id,
            "device_t_ms": sample.device_t_ms,
            "recv_time_utc": recv_time,
            "current_mA": sample.current_mA,
            "voltage_V": sample.voltage_V,
            "power_mW": sample.power_mW,
            "is_simulated": True,
        }
        self.db.energy.insert_one(energy_doc)
        self._publish_mqtt(f"sensor/{self.node_id}/energy", {
            "t": sample.device_t_ms,
            "current_mA": sample.current_mA,
            "power_mW": sample.power_mW,
            "is_simulated": True,
        })

        # Cache recent state for live API queries
        self.latest_reading = {
            "reading": reading_doc,
            "energy": energy_doc,
            "decision": {
                "policy": decision.policy.value,
                "next_interval_ms": decision.next_interval_ms,
                "is_event": decision.is_event,
                "is_approaching": decision.is_approaching,
                "slope": decision.slope,
                "reason": decision.reason,
            },
        }

        self.recent_readings.append(reading_doc)
        if len(self.recent_readings) > 200:
            self.recent_readings.pop(0)

        self.recent_energy.append(energy_doc)
        if len(self.recent_energy) > 50:
            self.recent_energy.pop(0)

        return self.latest_reading, decision

    def run_stream(self, duration_sec: Optional[int] = None, speed_factor: float = 1.0, callback: Optional[Callable] = None):
        """Runs continuous simulation at (1.0 / speed_factor) real time."""
        self.running = True
        self.record_trial_start()
        logger.info(f"Started simulation stream for trial '{self.trial_id}' (policy={self.active_policy_name}, speed={speed_factor}x)")

        next_interval_ms = 800 if self.active_policy_name != "fixed" else 1000
        start_wall_time = time.time()

        try:
            while self.running:
                data, decision = self.step(next_interval_ms)
                next_interval_ms = decision.next_interval_ms

                if callback:
                    callback(data)

                if duration_sec and (time.time() - start_wall_time) >= duration_sec:
                    logger.info(f"Reached specified duration of {duration_sec}s.")
                    break

                sleep_time_s = (next_interval_ms / 1000.0) / speed_factor
                time.sleep(max(0.001, sleep_time_s))

        except KeyboardInterrupt:
            logger.info("Simulation stream stopped by user.")
        finally:
            self.running = False
            self.record_trial_end()
            if self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()

    def run_benchmark(self, duration_ms: int = 45000) -> Dict[str, dict]:
        """
        Runs identical deterministic scenario across all 3 policies:
          - fixed
          - threshold
          - predictive
        Returns summary dictionary for each policy.
        """
        from analysis.compute_metrics import compute_trial_summary

        policies = ["fixed", "threshold", "predictive"]
        results = {}
        timestamp_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")

        events = [
            SimulatedEvent(start_ms=10000, duration_ms=8000, peak_g=1.45, ramp_up_ms=1800, ramp_down_ms=800),
            SimulatedEvent(start_ms=26000, duration_ms=8000, peak_g=1.50, ramp_up_ms=1800, ramp_down_ms=800),
        ]

        logger.info("==================================================")
        logger.info("Running deterministic multi-policy benchmark suite")
        logger.info("==================================================")

        for p_name in policies:
            trial_id = f"benchmark_{p_name}_{timestamp_suffix}"
            sim = SimulationController(
                node_id=self.node_id,
                broker=self.broker,
                port=self.port,
                trial_id=trial_id,
                policy_name=p_name,
                seed=self.seed,
                trigger_sensitivity=self.trigger_sensitivity,
                threshold_g=self.threshold_g,
            )
            sim.simulator.events = events
            sim.record_trial_start(notes=f"Deterministic benchmark for {p_name} policy")

            next_interval_ms = 1000 if p_name == "fixed" else 800
            sim.current_t_ms = 0

            while sim.current_t_ms < duration_ms:
                _, decision = sim.step(next_interval_ms)
                next_interval_ms = decision.next_interval_ms

            sim.record_trial_end()
            summary = compute_trial_summary(trial_id, true_event_start_ms=events[0].start_ms)
            results[p_name] = summary
            logger.info(f"[{p_name.upper()}] Samples: {summary['samples_taken']}, Energy: {summary['energy_mJ']} mJ, Latency: {summary['detection_latency_ms']} ms")

        logger.info("Benchmark complete!")
        return results


def main():
    parser = argparse.ArgumentParser(description="Simulation Runner for Adaptive IoT Sensing")
    parser.add_argument("--mode", choices=["stream", "benchmark"], default="stream")
    parser.add_argument("--policy", choices=["fixed", "threshold", "predictive"], default="predictive")
    parser.add_argument("--duration", type=int, default=None, help="Duration in seconds (stream mode)")
    parser.add_argument("--speed", type=float, default=1.0, help="Simulation speed factor (stream mode)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--trial-id", default=None, help="Trial ID to log under")
    parser.add_argument("--broker", default="localhost", help="MQTT broker address")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--node", default="node01", help="Node ID")
    args = parser.parse_args()

    controller = SimulationController(
        node_id=args.node,
        broker=args.broker,
        port=args.port,
        trial_id=args.trial_id,
        policy_name=args.policy,
        seed=args.seed,
    )

    if args.mode == "benchmark":
        controller.run_benchmark()
    else:
        controller.run_stream(duration_sec=args.duration, speed_factor=args.speed)


if __name__ == "__main__":
    main()
