"""
mqtt_logger.py
Backend MQTT subscriber and MongoDB logger.

Subscribes to all three sensor topics for a given node and inserts each
message into the matching MongoDB collection (readings / events /
energy), tagged with the active trial_id. This replaces the CSV-logging
version from Deliverable 4 — same subscriber logic, MongoDB instead of
a flat file.

Usage:
    python mqtt_logger.py --broker 192.168.1.100 --node node01 \\
        --trial-id predictive_run_03 --policy predictive \\
        --trigger-sensitivity 0.035

Requires:
    pip install -r requirements.txt
    A running MongoDB instance (see ../.env.example for connection settings)
"""

import argparse
import json
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from database.db import ensure_indexes, get_db


def parse_args():
    parser = argparse.ArgumentParser(description="Log MQTT sensor data into MongoDB.")
    parser.add_argument("--broker", default="localhost", help="MQTT broker address")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--node", default="node01", help="Node ID (must match firmware NODE_ID)")
    parser.add_argument("--trial-id", required=True, help="Unique ID for this trial, e.g. predictive_run_03")
    parser.add_argument("--policy", default="unknown", choices=["fixed", "threshold", "predictive", "unknown"])
    parser.add_argument("--trigger-sensitivity", type=float, default=None,
                         help="TREND_SLOPE_TRIGGER value used for this trial (predictive policy only)")
    parser.add_argument("--notes", default="", help="Free-text notes for the trials collection")
    return parser.parse_args()


def main():
    args = parse_args()
    topics = [
        f"sensor/{args.node}/reading",
        f"sensor/{args.node}/event",
        f"sensor/{args.node}/energy",
    ]

    ensure_indexes()
    db = get_db()

    # Record (or update) the parent trial document.
    db.trials.update_one(
        {"trial_id": args.trial_id},
        {
            "$set": {
                "trial_id": args.trial_id,
                "policy": args.policy,
                "node_id": args.node,
                "trigger_sensitivity": args.trigger_sensitivity,
                "notes": args.notes,
            },
            "$setOnInsert": {"start_time": datetime.now(timezone.utc)},
        },
        upsert=True,
    )

    def on_connect(client, userdata, flags, rc):
        print(f"Connected to broker at {args.broker}:{args.port} (rc={rc})")
        for t in topics:
            client.subscribe(t)
            print("  subscribed:", t)

    def on_message(client, userdata, msg):
        recv_time = datetime.now(timezone.utc)
        try:
            data = json.loads(msg.payload.decode())
        except json.JSONDecodeError:
            print("WARNING: could not parse payload on", msg.topic, "->", msg.payload)
            return

        base_doc = {
            "trial_id": args.trial_id,
            "node_id": args.node,
            "device_t_ms": data.get("t"),
            "recv_time_utc": recv_time,
        }

        if msg.topic.endswith("/reading"):
            db.readings.insert_one({**base_doc, "value": data.get("value"), "policy": data.get("policy")})
        elif msg.topic.endswith("/event"):
            db.events.insert_one({**base_doc, "event": data.get("event")})
        elif msg.topic.endswith("/energy"):
            db.energy.insert_one({**base_doc, "current_mA": data.get("current_mA")})
        else:
            print("WARNING: unrecognized topic", msg.topic)
            return

        print(f"[{msg.topic}] {base_doc['device_t_ms']} ms -> {data}")

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"Connecting to {args.broker}:{args.port} ...")
    client.connect(args.broker, args.port)

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print(f"\nStopping logger for trial '{args.trial_id}'.")
    finally:
        db.trials.update_one(
            {"trial_id": args.trial_id},
            {"$set": {"end_time": datetime.now(timezone.utc)}},
        )


if __name__ == "__main__":
    main()
