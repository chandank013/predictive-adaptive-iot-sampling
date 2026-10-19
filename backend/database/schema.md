# MongoDB Schema

Database: `adaptive_iot_sensing`

## Collection: `trials`
One document per experimental run — the parent record everything else
links back to via `trial_id`.

```json
{
  "_id": ObjectId,
  "trial_id": "predictive_run_03",
  "policy": "predictive",
  "node_id": "node01",
  "trigger_sensitivity": 0.035,
  "start_time": ISODate,
  "end_time": ISODate,
  "notes": "motor event induced at 00:02:14"
}
```

## Collection: `readings`
One document per sensor reading (mirrors the `sensor/<node>/reading`
MQTT topic).

```json
{
  "_id": ObjectId,
  "trial_id": "predictive_run_03",
  "node_id": "node01",
  "device_t_ms": 10432,
  "recv_time_utc": ISODate,
  "value": 0.421,
  "policy": "predictive"
}
```

## Collection: `events`
One document per ground-truth event flag change (mirrors
`sensor/<node>/event`).

```json
{
  "_id": ObjectId,
  "trial_id": "predictive_run_03",
  "node_id": "node01",
  "device_t_ms": 10400,
  "recv_time_utc": ISODate,
  "event": true
}
```

## Collection: `energy`
One document per energy/current reading (mirrors
`sensor/<node>/energy`).

```json
{
  "_id": ObjectId,
  "trial_id": "predictive_run_03",
  "node_id": "node01",
  "device_t_ms": 10432,
  "recv_time_utc": ISODate,
  "current_mA": 48.7
}
```

## Indexing

A compound index on `{trial_id: 1, device_t_ms: 1}` exists on each of
`readings`, `events`, and `energy` — this is the access pattern both the
API and the analysis scripts use most (fetch one trial's full time
series, in order). A unique index on `trial_id` exists on `trials`.

Both are created by `database/db.py::ensure_indexes()`, called once at
startup by `mqtt_logger.py` and `api/server.py`.
