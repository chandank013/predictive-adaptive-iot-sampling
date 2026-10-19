"""
db.py
MongoDB connection helper, shared by mqtt_logger.py, api/server.py, and
the analysis scripts.

Reads connection settings from environment variables (see .env.example):
    MONGO_URI      - e.g. mongodb://localhost:27017/
    MONGO_DB_NAME  - e.g. adaptive_iot_sensing
    SYSTEM_MODE    - SIMULATION or HARDWARE

Usage:
    from database.db import get_db, is_mongo_available
    db = get_db()
    db.readings.insert_one({...})
"""

import copy
import logging
import os
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional

from pymongo import ASCENDING, MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "adaptive_iot_sensing")
SYSTEM_MODE = os.getenv("SYSTEM_MODE", "SIMULATION")


class FallbackCursor:
    """In-memory cursor mimicking pymongo's Cursor for offline fallback."""

    def __init__(self, docs: List[Dict[str, Any]]):
        self._docs = docs

    def sort(self, key_or_list, direction=1):
        if isinstance(key_or_list, list):
            key, direction = key_or_list[0]
        else:
            key = key_or_list

        def sort_val(doc):
            val = doc.get(key)
            if val is None:
                return (0, "")
            if isinstance(val, (int, float)):
                return (1, val)
            if isinstance(val, datetime):
                return (2, val.isoformat())
            return (3, str(val))

        reverse = (direction == -1)
        self._docs = sorted(self._docs, key=sort_val, reverse=reverse)
        return self

    def limit(self, n: int):
        self._docs = self._docs[:n]
        return self

    def __iter__(self):
        return iter(copy.deepcopy(self._docs))

    def __len__(self):
        return len(self._docs)


class FallbackCollection:
    """In-memory collection mimicking pymongo's Collection."""

    def __init__(self, name: str):
        self.name = name
        self.docs: List[Dict[str, Any]] = []

    def create_index(self, keys, **kwargs):
        return f"{self.name}_idx"

    def insert_one(self, doc: Dict[str, Any]):
        copied = copy.deepcopy(doc)
        if "_id" not in copied:
            import uuid
            copied["_id"] = str(uuid.uuid4())
        self.docs.append(copied)
        return type("InsertResult", (), {"inserted_id": copied["_id"]})()

    def _matches(self, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        for k, v in query.items():
            if k not in doc:
                return False
            if doc[k] != v:
                return False
        return True

    def find_one(self, query: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None):
        query = query or {}
        for d in self.docs:
            if self._matches(d, query):
                res = copy.deepcopy(d)
                if projection and projection.get("_id") == 0:
                    res.pop("_id", None)
                return res
        return None

    def find(self, query: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None):
        query = query or {}
        matched = []
        for d in self.docs:
            if self._matches(d, query):
                res = copy.deepcopy(d)
                if projection and projection.get("_id") == 0:
                    res.pop("_id", None)
                matched.append(res)
        return FallbackCursor(matched)

    def count_documents(self, query: Optional[Dict[str, Any]] = None) -> int:
        query = query or {}
        return sum(1 for d in self.docs if self._matches(d, query))

    def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False):
        for d in self.docs:
            if self._matches(d, query):
                if "$set" in update:
                    d.update(copy.deepcopy(update["$set"]))
                return type("UpdateResult", (), {"matched_count": 1, "modified_count": 1})()

        if upsert:
            new_doc = copy.deepcopy(query)
            if "$set" in update:
                new_doc.update(copy.deepcopy(update["$set"]))
            if "$setOnInsert" in update:
                new_doc.update(copy.deepcopy(update["$setOnInsert"]))
            self.insert_one(new_doc)
            return type("UpdateResult", (), {"matched_count": 0, "upserted_id": new_doc.get("_id")})()

        return type("UpdateResult", (), {"matched_count": 0, "modified_count": 0})()

    def delete_many(self, query: Dict[str, Any]):
        initial_len = len(self.docs)
        self.docs = [d for d in self.docs if not self._matches(d, query)]
        return type("DeleteResult", (), {"deleted_count": initial_len - len(self.docs)})()


class FallbackDatabase:
    """In-memory database proxy when MongoDB is unavailable."""

    def __init__(self, name: str):
        self.name = name
        self._collections: Dict[str, FallbackCollection] = {}

    def __getitem__(self, col_name: str) -> FallbackCollection:
        if col_name not in self._collections:
            self._collections[col_name] = FallbackCollection(col_name)
        return self._collections[col_name]

    def __getattr__(self, col_name: str) -> FallbackCollection:
        return self[col_name]

    def list_collection_names(self) -> List[str]:
        return list(self._collections.keys())


_FALLBACK_DB: Optional[FallbackDatabase] = None
_MONGO_AVAILABLE: Optional[bool] = None


def is_mongo_available() -> bool:
    global _MONGO_AVAILABLE
    if _MONGO_AVAILABLE is not None:
        return _MONGO_AVAILABLE
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        client.close()
        _MONGO_AVAILABLE = True
    except (ConnectionFailure, ServerSelectionTimeoutError, Exception) as exc:
        logger.warning(f"MongoDB not reachable at {MONGO_URI}: {exc}. Using fallback in-memory store.")
        _MONGO_AVAILABLE = False
    return _MONGO_AVAILABLE


@lru_cache(maxsize=1)
def get_client() -> Optional[MongoClient]:
    if is_mongo_available():
        return MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    return None


def get_db():
    """Returns the project's database handle (real MongoDB or resilient in-memory fallback)."""
    global _FALLBACK_DB
    if is_mongo_available():
        client = get_client()
        if client is not None:
            return client[MONGO_DB_NAME]

    if _FALLBACK_DB is None:
        _FALLBACK_DB = FallbackDatabase(MONGO_DB_NAME)
    return _FALLBACK_DB


def ensure_indexes():
    """Creates indexes if MongoDB is available. Safe to call repeatedly."""
    if not is_mongo_available():
        return
    try:
        db = get_db()
        for collection_name in ("readings", "events", "energy"):
            db[collection_name].create_index(
                [("trial_id", ASCENDING), ("device_t_ms", ASCENDING)],
                name="trial_id_device_t_ms",
            )
        db.trials.create_index([("trial_id", ASCENDING)], unique=True, name="trial_id_unique")
    except Exception as exc:
        logger.warning(f"Could not ensure indexes: {exc}")


if __name__ == "__main__":
    ensure_indexes()
    db = get_db()
    status = "Real MongoDB" if is_mongo_available() else "In-Memory Fallback"
    print(f"Connected to database ({status}) at {MONGO_URI}, database '{MONGO_DB_NAME}'.")
    print("Collections:", db.list_collection_names())
