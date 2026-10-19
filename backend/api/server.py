"""
api/server.py
REST API serving the frontend dashboard's data needs from MongoDB and live simulation.

Endpoints:
    GET  /health                       - basic liveness check
    GET  /api/status                   - system status (mode, simulation label, active policy, connection)
    GET  /api/live/latest              - latest live vibration, energy, stats, and event log
    POST /api/policy                   - update active sampling policy ("fixed", "threshold", "predictive")
    GET  /trials                       - list all trials (for Trial History page)
    GET  /trials/{trial_id}            - one trial's metadata
    GET  /trials/{trial_id}/readings   - raw readings time series (for charts)
    GET  /trials/{trial_id}/events     - event flags
    GET  /trials/{trial_id}/energy     - energy/current time series
    GET  /trials/{trial_id}/summary    - computed metrics (samples, latency, energy, bandwidth, power)
    GET  /api/tradeoff                 - aggregated accuracy-vs-energy tradeoff curve and comparison table
    POST /api/simulation/start        - start live background simulation
    POST /api/simulation/stop         - stop live background simulation
    POST /api/simulation/benchmark    - run deterministic 3-policy comparison benchmark
"""

import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure project root and backend dir are in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from analysis.compute_metrics import compute_accuracy_proxy, compute_trial_summary
from database.db import ensure_indexes, get_db, is_mongo_available
from simulation.policy_reference import create_policy
from simulation.sensor_simulator import EdgeSensorSimulator, SimulatedEvent

app = FastAPI(title="Adaptive IoT Sensing API", version="2.0.0")

# CORS middleware for Vite dev server and production frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SYSTEM_MODE = os.getenv("SYSTEM_MODE", "SIMULATION")
NODE_ID = os.getenv("NODE_ID", "node01")
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# ----------------- Shared Live Simulation State -----------------
class LiveSimulationState:
    def __init__(self):
        self.lock = threading.Lock()
        self.is_running = False
        self.mode = SYSTEM_MODE
        self.active_policy = "predictive"
        self.active_trial_id = f"live_run_{int(time.time())}"
        self.start_wall_time = time.time()
        self.packets_sent = 0
        self.max_vibration_seen = 0.28
        self.current_t_ms = 0

        self.sensor_simulator = EdgeSensorSimulator(seed=42)
        self.policy_instance = create_policy("predictive")

        self.recent_readings: List[Dict[str, Any]] = []
        self.energy_sparkline: List[Dict[str, Any]] = []
        self.event_log: List[Dict[str, Any]] = []
        self._thread: Optional[threading.Thread] = None

    def reset_trial(self, trial_id: Optional[str] = None):
        with self.lock:
            self.active_trial_id = trial_id or f"live_run_{int(time.time())}"
            self.start_wall_time = time.time()
            self.packets_sent = 0
            self.max_vibration_seen = 0.28
            self.current_t_ms = 0
            self.recent_readings = []
            self.energy_sparkline = []
            self.event_log = []
            self.sensor_simulator.reset(seed=int(time.time()) % 1000)
            self.policy_instance = create_policy(self.active_policy)

    def set_policy(self, policy_name: str):
        with self.lock:
            self.active_policy = policy_name.lower()
            self.policy_instance = create_policy(self.active_policy)
            now_str = datetime.now().strftime("%H:%M:%S")
            self.event_log.insert(0, {
                "id": int(time.time() * 1000),
                "type": "info",
                "text": f"Policy switched to {self.active_policy.capitalize()}",
                "time": now_str,
            })
            if len(self.event_log) > 40:
                self.event_log.pop()


live_state = LiveSimulationState()


def _serialize(doc):
    d = dict(doc)
    d["_id"] = str(d["_id"])
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


# ----------------- Background Simulation Loop -----------------
def _simulation_worker():
    db = get_db()
    next_interval_ms = 800

    # Ensure trial record exists
    with live_state.lock:
        trial_id = live_state.active_trial_id
        policy_name = live_state.active_policy

    db.trials.update_one(
        {"trial_id": trial_id},
        {
            "$set": {
                "trial_id": trial_id,
                "policy": policy_name,
                "node_id": NODE_ID,
                "is_simulated": True,
                "mode": SYSTEM_MODE,
                "notes": "Live interactive trial",
            },
            "$setOnInsert": {"start_time": datetime.now(timezone.utc)},
        },
        upsert=True,
    )

    last_event_flag = False

    while live_state.is_running:
        with live_state.lock:
            t_ms = live_state.current_t_ms + next_interval_ms
            live_state.current_t_ms = t_ms
            sample = live_state.sensor_simulator.sample(t_ms, next_interval_ms)
            decision = live_state.policy_instance.decide(sample.vibration_g, t_ms)
            next_interval_ms = decision.next_interval_ms

            live_state.packets_sent += 1
            if sample.vibration_g > live_state.max_vibration_seen:
                live_state.max_vibration_seen = sample.vibration_g

            now_dt = datetime.now(timezone.utc)
            now_time_str = now_dt.strftime("%H:%M:%S")

            # Reading doc
            reading_doc = {
                "trial_id": live_state.active_trial_id,
                "node_id": NODE_ID,
                "device_t_ms": t_ms,
                "recv_time_utc": now_dt,
                "value": sample.vibration_g,
                "policy": decision.policy.value,
                "next_interval_ms": next_interval_ms,
                "is_simulated": True,
                "seq": sample.seq_num,
            }

            # Energy doc
            energy_doc = {
                "trial_id": live_state.active_trial_id,
                "node_id": NODE_ID,
                "device_t_ms": t_ms,
                "recv_time_utc": now_dt,
                "current_mA": sample.current_mA,
                "voltage_V": sample.voltage_V,
                "power_mW": sample.power_mW,
                "is_simulated": True,
            }

            # Update live buffers
            live_state.recent_readings.append({"t": round(t_ms / 1000.0, 1), "value": sample.vibration_g})
            if len(live_state.recent_readings) > 120:
                live_state.recent_readings.pop(0)

            live_state.energy_sparkline.append({"i": len(live_state.energy_sparkline), "value": sample.current_mA})
            if len(live_state.energy_sparkline) > 25:
                live_state.energy_sparkline.pop(0)

            # Event log notifications
            if decision.is_approaching:
                live_state.event_log.insert(0, {
                    "id": int(time.time() * 1000) + 1,
                    "type": "warn",
                    "text": f"Prediction: Vibration rising (slope={decision.slope:.4f} g/sample)",
                    "time": now_time_str,
                })

            if decision.is_event and not last_event_flag:
                live_state.event_log.insert(0, {
                    "id": int(time.time() * 1000) + 2,
                    "type": "event",
                    "text": f"Event detected: vibration {sample.vibration_g:.2f}g crossed threshold",
                    "time": now_time_str,
                })
                live_state.event_log.insert(0, {
                    "id": int(time.time() * 1000) + 3,
                    "type": "ok",
                    "text": f"Sampling rate increased to {next_interval_ms} ms",
                    "time": now_time_str,
                })
            elif not decision.is_event and last_event_flag:
                live_state.event_log.insert(0, {
                    "id": int(time.time() * 1000) + 4,
                    "type": "ok",
                    "text": f"Event ended — sampling returned to {next_interval_ms} ms",
                    "time": now_time_str,
                })

            last_event_flag = decision.is_event
            if len(live_state.event_log) > 40:
                live_state.event_log = live_state.event_log[:40]

        # Persist to DB asynchronously
        try:
            db.readings.insert_one(reading_doc)
            db.energy.insert_one(energy_doc)
            if decision.is_event != last_event_flag or decision.is_approaching:
                db.events.insert_one({
                    "trial_id": reading_doc["trial_id"],
                    "node_id": NODE_ID,
                    "device_t_ms": t_ms,
                    "recv_time_utc": now_dt,
                    "event": decision.is_event,
                    "is_approaching": decision.is_approaching,
                    "is_simulated": True,
                })
        except Exception:
            pass

        # Sleep pacing (scaled so UI updates smoothly)
        sleep_s = max(0.05, (next_interval_ms / 1000.0) / 2.0)
        time.sleep(sleep_s)


@app.on_event("startup")
def on_startup():
    ensure_indexes()
    # Automatically start live background simulation stream if in SIMULATION mode
    if SYSTEM_MODE == "SIMULATION" and not live_state.is_running:
        live_state.is_running = True
        live_state._thread = threading.Thread(target=_simulation_worker, daemon=True)
        live_state._thread.start()


@app.on_event("shutdown")
def on_shutdown():
    live_state.is_running = False


# ----------------- API Endpoints -----------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "system_mode": SYSTEM_MODE,
        "database_connected": is_mongo_available(),
        "simulation_running": live_state.is_running,
    }


@app.get("/api/status")
def get_status():
    with live_state.lock:
        uptime_sec = int(time.time() - live_state.start_wall_time)
        hrs = uptime_sec // 3600
        mins = (uptime_sec % 3600) // 60
        secs = uptime_sec % 60
        uptime_str = f"{hrs:02d}:{mins:02d}:{secs:02d}"

        return {
            "mode": SYSTEM_MODE,
            "label": "Operational",
            "is_simulated": True,
            "simulation_running": live_state.is_running,
            "active_policy": live_state.active_policy,
            "active_trial_id": live_state.active_trial_id,
            "database_connected": is_mongo_available(),
            "packets_sent": live_state.packets_sent,
            "uptime": uptime_str,
            "node_id": NODE_ID,
        }


@app.get("/api/live/latest")
def get_live_latest():
    with live_state.lock:
        readings = list(live_state.recent_readings)
        energy_spark = list(live_state.energy_sparkline)
        logs = list(live_state.event_log)

        cur_vib = readings[-1]["value"] if readings else 0.08
        cur_energy = energy_spark[-1]["value"] if energy_spark else 4.2

        uptime_sec = int(time.time() - live_state.start_wall_time)
        hrs = uptime_sec // 3600
        mins = (uptime_sec % 3600) // 60
        secs = uptime_sec % 60
        uptime_str = f"{hrs:02d}:{mins:02d}:{secs:02d}"

        # Determine sampling mode and interval display
        interval_ms = 1000 if live_state.active_policy == "fixed" else (100 if cur_vib >= 0.35 else 800)
        rate_hz = round(1000.0 / interval_ms, 1)

        pct_from_peak = 0
        if live_state.max_vibration_seen > 0:
            pct_from_peak = round((1.0 - (cur_vib / live_state.max_vibration_seen)) * 100)

        # Normalize t values so chart shows relative seconds (e.g. 0 to 60)
        chart_series = []
        if readings:
            t_base = readings[0]["t"]
            for r in readings:
                chart_series.append({"t": round(r["t"] - t_base, 1), "value": r["value"]})
        else:
            chart_series = [{"t": 0, "value": 0.08}]

        return {
            "chartData": chart_series,
            "energySparkline": energy_spark,
            "eventLog": logs,
            "liveStats": {
                "activePolicy": live_state.active_policy.capitalize(),
                "samplingInterval": f"{interval_ms} ms",
                "samplingMode": "High Rate" if interval_ms == 100 else ("Fixed Rate" if live_state.active_policy == "fixed" else "Idle Rate"),
                "energyDraw": f"{cur_energy:.1f} mA",
                "currentVibration": f"{cur_vib:.2f} g",
                "vibrationChange": f"{abs(pct_from_peak)}% from peak",
                "samplingRate": f"{rate_hz} Hz",
                "samplingRateSub": f"({interval_ms} ms)",
                "packetsSent": f"{live_state.packets_sent:,}",
                "packetsSentSub": "(this session)",
                "uptime": uptime_str,
                "uptimeSub": "(current trial)",
            },
            "threshold": 0.35,
            "is_simulated": True,
        }


class PolicyRequest(BaseModel):
    policy: str


@app.post("/api/policy")
def set_policy(req: PolicyRequest):
    valid_policies = ["fixed", "threshold", "predictive"]
    p = req.policy.lower().strip()
    if p not in valid_policies:
        raise HTTPException(status_code=400, detail=f"Invalid policy '{req.policy}'. Must be one of {valid_policies}")

    live_state.set_policy(p)
    return {"status": "ok", "active_policy": p}


@app.get("/trials")
def list_trials():
    db = get_db()
    trials = [_serialize(t) for t in db.trials.find().sort("start_time", -1)]
    return trials


@app.get("/trials/{trial_id}")
def get_trial(trial_id: str):
    db = get_db()
    trial = db.trials.find_one({"trial_id": trial_id})
    if trial is None:
        raise HTTPException(status_code=404, detail=f"Trial '{trial_id}' not found")
    return _serialize(trial)


@app.get("/trials/{trial_id}/readings")
def get_readings(trial_id: str, limit: int = Query(5000, le=50000)):
    db = get_db()
    docs = list(
        db.readings.find({"trial_id": trial_id}, {"_id": 0})
        .sort("device_t_ms", 1)
        .limit(limit)
    )
    return docs


@app.get("/trials/{trial_id}/events")
def get_events(trial_id: str):
    db = get_db()
    docs = list(db.events.find({"trial_id": trial_id}, {"_id": 0}).sort("device_t_ms", 1))
    return docs


@app.get("/trials/{trial_id}/energy")
def get_energy(trial_id: str, limit: int = Query(5000, le=50000)):
    db = get_db()
    docs = list(
        db.energy.find({"trial_id": trial_id}, {"_id": 0})
        .sort("device_t_ms", 1)
        .limit(limit)
    )
    return docs


@app.get("/trials/{trial_id}/summary")
def get_summary(trial_id: str, true_event_start_ms: Optional[int] = None):
    try:
        return compute_trial_summary(trial_id, true_event_start_ms)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/tradeoff")
def get_tradeoff():
    """Returns aggregated tradeoff curve points and policy comparison table across all logged trials."""
    db = get_db()
    trials = list(db.trials.find().sort("start_time", -1))

    by_policy: Dict[str, List[Dict[str, Any]]] = {
        "fixed": [],
        "threshold": [],
        "predictive": [],
    }

    summaries = []
    for t in trials:
        t_id = t["trial_id"]
        try:
            s = compute_trial_summary(t_id)
            if s.get("energy_mJ") is not None and s.get("policy") in by_policy:
                by_policy[s["policy"]].append({
                    "energy": round(s["energy_mJ"], 1),
                    "accuracy": s.get("accuracy_pct", 85.0),
                    "trial_id": t_id,
                })
                summaries.append(s)
        except Exception:
            continue

    # Sort each policy series by energy
    for p in by_policy:
        by_policy[p].sort(key=lambda x: x["energy"])

    # Aggregate comparison table
    policy_meta = [
        {"policy": "Fixed-rate", "key": "fixed", "color": "#3366cc"},
        {"policy": "Threshold-adaptive", "key": "threshold", "color": "#e08a2c"},
        {"policy": "Predictive-adaptive", "key": "predictive", "color": "#1a9b6c", "highlight": True},
    ]

    comparison_table = []
    for pm in policy_meta:
        matches = [s for s in summaries if s.get("policy") == pm["key"]]
        if matches:
            avg_samples = int(sum(m["samples_taken"] for m in matches) / len(matches))
            latencies = [m["detection_latency_ms"] for m in matches if m.get("detection_latency_ms") is not None]
            avg_latency = round(sum(latencies) / len(latencies) / 1000.0, 2) if latencies else 0.40
            avg_energy = round(sum(m["energy_mJ"] for m in matches if m.get("energy_mJ")) / len(matches), 1)
        else:
            # Fallback baseline estimates if no trials yet
            defaults = {
                "fixed": (45, 1.0, 845.0),
                "threshold": (189, 0.40, 1910.0),
                "predictive": (203, 0.40, 1920.0),
            }
            avg_samples, avg_latency, avg_energy = defaults[pm["key"]]

        comparison_table.append({
            "policy": pm["policy"],
            "color": pm["color"],
            "samples": f"{avg_samples:,}",
            "latency": f"{avg_latency:.2f}",
            "energy": f"{avg_energy:.1f}",
            "highlight": pm.get("highlight", False),
        })

    return {
        "tradeoffCurve": by_policy,
        "policyComparisonTable": comparison_table,
        "is_simulated": True,
    }


@app.post("/api/simulation/benchmark")
def run_benchmark_endpoint(background_tasks: BackgroundTasks):
    from simulation.sim_runner import SimulationController

    def _task():
        controller = SimulationController(node_id=NODE_ID, policy_name="predictive")
        controller.run_benchmark()

    background_tasks.add_task(_task)
    return {"status": "started", "message": "Deterministic multi-policy benchmark running in background."}


@app.post("/api/simulation/start")
def start_simulation():
    if not live_state.is_running:
        live_state.is_running = True
        live_state._thread = threading.Thread(target=_simulation_worker, daemon=True)
        live_state._thread.start()
        return {"status": "started"}
    return {"status": "already_running"}


@app.post("/api/simulation/stop")
def stop_simulation():
    live_state.is_running = False
    return {"status": "stopped"}
