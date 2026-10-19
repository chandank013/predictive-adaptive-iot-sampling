"""
db.py
MongoDB connection helper, shared by mqtt_logger.py, api/server.py, and
the analysis scripts.

Reads connection settings from environment variables (see .env.example):
    MONGO_URI      - e.g. mongodb://localhost:27017/
    MONGO_DB_NAME  - e.g. adaptive_iot_sensing

Usage:
    from database.db import get_db
    db = get_db()
    db.readings.insert_one({...})
"""

import os
from functools import lru_cache

from pymongo import ASCENDING, MongoClient

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv is optional; if it's not installed, environment
    # variables must already be set some other way (shell export, etc).
    pass

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "adaptive_iot_sensing")


@lru_cache(maxsize=1)
def get_client() -> MongoClient:
    """Returns a cached MongoClient. pymongo's client is lazy and
    connection-pooled, so a single shared client is the right pattern
    rather than opening a new connection per call."""
    return MongoClient(MONGO_URI)


def get_db():
    """Returns the project's database handle."""
    return get_client()[MONGO_DB_NAME]


def ensure_indexes():
    """Creates the compound indexes described in database/schema.md.
    Safe to call repeatedly - create_index is a no-op if the index
    already exists with the same spec. Call this once at startup
    (mqtt_logger.py and api/server.py both do this)."""
    db = get_db()
    for collection_name in ("readings", "events", "energy"):
        db[collection_name].create_index(
            [("trial_id", ASCENDING), ("device_t_ms", ASCENDING)],
            name="trial_id_device_t_ms",
        )
    db.trials.create_index([("trial_id", ASCENDING)], unique=True, name="trial_id_unique")


if __name__ == "__main__":
    # Quick connectivity smoke test: python database/db.py
    ensure_indexes()
    print(f"Connected to MongoDB at {MONGO_URI}, database '{MONGO_DB_NAME}'.")
    print("Collections:", get_db().list_collection_names())
