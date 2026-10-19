"""
api/server.py
REST API serving the frontend dashboard's data needs from MongoDB.

Run:
    uvicorn api.server:app --reload --port 8000
    (run from the backend/ directory so the database/analysis packages resolve)

Endpoints:
    GET /trials                        - list all trials (for Trial History page)
    GET /trials/{trial_id}             - one trial's metadata
    GET /trials/{trial_id}/readings    - raw readings time series (for Live/Results charts)
    GET /trials/{trial_id}/events      - ground-truth event flags
    GET /trials/{trial_id}/energy      - energy/current time series
    GET /trials/{trial_id}/summary     - computed metrics (samples, latency, energy, bandwidth)
    GET /health                        - basic liveness check
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from database.db import ensure_indexes, get_db  # noqa: E402
from analysis.compute_metrics import compute_trial_summary  # noqa: E402

app = FastAPI(title="Adaptive IoT Sensing API", version="1.0.0")

# Allow the Vite dev server (and a built frontend served elsewhere) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    ensure_indexes()


def _serialize(doc):
    """Mongo ObjectId and datetime aren't directly JSON-serializable by
    FastAPI's default encoder in all cases; stringify _id and leave
    datetimes to FastAPI's built-in ISO handling."""
    doc = dict(doc)
    doc["_id"] = str(doc["_id"])
    return doc


@app.get("/health")
def health():
    return {"status": "ok"}


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
def get_summary(trial_id: str, true_event_start_ms: int | None = None):
    try:
        return compute_trial_summary(trial_id, true_event_start_ms)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
