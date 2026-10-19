# Adaptive IoT Sensing — Backend

MQTT-to-MongoDB logger, REST API, and analysis scripts for the
predictive adaptive-sampling project.

## Setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env     # then edit .env with your real Mongo/MQTT settings
```

You'll need a MongoDB instance reachable at the `MONGO_URI` in `.env`
(local install, or MongoDB Atlas free tier — see `.env.example`).

## 1. Log a trial

Run this while the ESP32 firmware is running and publishing over MQTT:

```bash
python mqtt_logger.py \
  --broker 192.168.1.100 \
  --node node01 \
  --trial-id predictive_run_03 \
  --policy predictive \
  --trigger-sensitivity 0.035 \
  --notes "motor event induced at 00:02:14"
```

Stop with Ctrl+C when the trial is done — this records the trial's
`end_time` in MongoDB.

## 2. Run the API (for the frontend dashboard)

```bash
uvicorn api.server:app --reload --port 8000
```

Then point the frontend's `fetch()` calls at `http://localhost:8000`
(see the frontend's own README for where to wire this in).

Quick manual check:
```bash
curl http://localhost:8000/trials
curl http://localhost:8000/trials/predictive_run_03/summary
```

## 3. Compute metrics / plot the trade-off curve offline

```bash
python analysis/compute_metrics.py --trial-id predictive_run_03 \
  --true-event-start-ms 10000

python analysis/plot_tradeoff_curve.py --true-event-start-ms 10000
```

`--true-event-start-ms` is the device clock time (`millis()` on the
ESP32) when you physically triggered the event during that trial — note
it down during data collection, since it's what latency/accuracy
scoring is computed against.

## Known limitation — the accuracy proxy

`plot_tradeoff_curve.py` currently scores "accuracy" as a simple
function of detection latency for a *single* induced event per trial.
This is a placeholder, not the real accuracy metric described in
Deliverable 1 (precision/recall/F1 across multiple labeled events). Once
Deliverable 5 (Dataset Collection) produces trials with several labeled
events each, replace `compute_accuracy()` in `plot_tradeoff_curve.py`
with real classification scoring against those labels.

## File structure

```
backend/
├── mqtt_logger.py          # MQTT subscriber -> MongoDB
├── api/
│   └── server.py           # FastAPI REST API for the frontend
├── database/
│   ├── db.py                # MongoDB connection + index setup
│   └── schema.md            # collection schema reference
├── analysis/
│   ├── compute_metrics.py   # per-trial metrics (samples, latency, energy, bandwidth)
│   └── plot_tradeoff_curve.py  # accuracy-vs-energy chart across all trials
├── requirements.txt
└── .env.example
```
