"""
tests/test_api.py
Integration tests for backend FastAPI server endpoints:
  - /health
  - /api/status
  - /api/live/latest
  - /api/policy
  - /trials
  - /api/tradeoff
"""

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from fastapi.testclient import TestClient
from backend.api.server import app


class TestApiServer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["system_mode"], "SIMULATION")

    def test_status(self):
        res = self.client.get("/api/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["mode"], "SIMULATION")
        self.assertEqual(data["label"], "Operational")
        self.assertTrue(data["is_simulated"])

    def test_live_latest(self):
        res = self.client.get("/api/live/latest")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("chartData", data)
        self.assertIn("liveStats", data)
        self.assertIn("energySparkline", data)
        self.assertIn("eventLog", data)

    def test_set_policy(self):
        # Switch to fixed
        res = self.client.post("/api/policy", json={"policy": "fixed"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["active_policy"], "fixed")

        # Switch back to predictive
        res = self.client.post("/api/policy", json={"policy": "predictive"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["active_policy"], "predictive")

        # Bad policy should return 400
        res_bad = self.client.post("/api/policy", json={"policy": "nonexistent"})
        self.assertEqual(res_bad.status_code, 400)

    def test_tradeoff_endpoint(self):
        res = self.client.get("/api/tradeoff")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("tradeoffCurve", data)
        self.assertIn("policyComparisonTable", data)
        self.assertTrue(data["is_simulated"])


if __name__ == "__main__":
    unittest.main()
