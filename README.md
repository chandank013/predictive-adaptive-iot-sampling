# Predictive Adaptive Sampling for Energy-Efficient Edge IoT

An end-to-end edge IoT sensing architecture that dynamically optimizes sensor sampling rates using predictive heuristics. Implements **Fixed-Rate**, **Threshold-Adaptive**, and **Predictive-Adaptive** sampling policies to minimize energy consumption and network bandwidth while maintaining low event-detection latency.

> [!IMPORTANT]
> **SIMULATION MODE ACTIVE**: Physical hardware (ESP32, ADXL345, INA219) is not required for testing. The project runs end-to-end with high-fidelity simulated telemetry, reproducible benchmarks, and live visualization.

---

## Architecture Overview

```
+-----------------------------------------------------------------------------------------+
|                                    SENSING LAYER                                        |
|                                                                                         |
|   Physical Edge (ESP32 / ADXL345 / INA219)   OR   Synthetic Simulator (sensor_simulator)|
|                                      |                                                  |
|                   +------------------v------------------+                               |
|                   |        Policy Engine                |                               |
|                   |  - Fixed Rate (1000 ms)             |                               |
|                   |  - Threshold Adaptive (800/100 ms)  |                               |
|                   |  - Predictive Trend (Slope trigger) |                               |
|                   +------------------+------------------+                               |
+--------------------------------------|--------------------------------------------------+
                                       | MQTT / Direct In-Memory Transport
+--------------------------------------v--------------------------------------------------+
|                                    BACKEND LAYER                                        |
|                                                                                         |
|   +-----------------------+   +------------------------+   +------------------------+   |
|   | MQTT Logger           |   | MongoDB Storage        |   | FastAPI REST Server    |   |
|   | (mqtt_logger.py)      |   | (readings/events/energy|   | (api/server.py :8000)  |   |
|   +-----------------------+   +------------------------+   +-----------+------------+   |
+------------------------------------------------------------------------|----------------+
                                                                         | REST API / Polling
+------------------------------------------------------------------------v----------------+
|                                   DASHBOARD LAYER                                       |
|                                                                                         |
|   React 18 + Vite + Tailwind CSS + Recharts (:5173)                                     |
|   - Live Monitoring: Real-time waveform, sparkline, interactive policy switching        |
|   - Trial Results: Tradeoff curves (Accuracy vs. Energy), metric comparison table       |
|   - Trial History: Filterable, sortable historical experimental records                 |
+-----------------------------------------------------------------------------------------+
```

---

## Quick Start (One Command)

### 1. Prerequisites
- **Python 3.10+** (with pip)
- **Node.js 18+** (with npm)
- **MongoDB** (Local MongoDB on `localhost:27017` or built-in in-memory fallback)

### 2. Install Dependencies
```bash
# Backend dependencies
pip install -r backend/requirements.txt

# Frontend dependencies
cd frontend
npm install
cd ..
```

### 3. Run the Project
Launch both the backend API and the frontend dashboard with a single command:
```bash
python run_project.py
```
*(On Windows PowerShell, you can also run `.\start.ps1`)*

Access the applications:
- **Frontend Dashboard**: [http://localhost:5173](http://localhost:5173)
- **Backend REST API**: [http://localhost:8000](http://localhost:8000)
- **Interactive API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Sampling Policies

| Policy | Idle Interval | Active Interval | Trigger Condition | Energy Characteristics |
| :--- | :--- | :--- | :--- | :--- |
| **Fixed-Rate (Baseline)** | 1000 ms | 1000 ms | None (Constant frequency) | Baseline high latency during dynamic bursts |
| **Threshold-Adaptive** | 800 ms | 100 ms | \|vibration\| > 0.35 g (with 4-sample recovery hold) | Reduces idle power by ~50%; reacts post-crossing |
| **Predictive-Adaptive** | 800 ms | 100 ms | Sliding window (N=6) slope > 0.035 g/sample | Pre-triggers before threshold crossing, reducing detection delay |

---

## Running Multi-Policy Benchmark

To generate side-by-side experimental comparisons using the exact same deterministic event sequence (seed=42):
```bash
python simulation/sim_runner.py --mode benchmark
```
This logs `sim_fixed_baseline`, `sim_threshold_adaptive`, and `sim_predictive_adaptive` into MongoDB, populating the **Trial Results** and **Accuracy vs. Energy Trade-off** charts.

To plot the offline matplotlib trade-off curve:
```bash
python backend/analysis/plot_tradeoff_curve.py --true-event-start-ms 10000
```

---

## Automated Test Suite

Run the full unit and integration test suite:
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```
All 18 tests cover:
- Policy interval switching and recovery hysteresis
- Trend buffer prediction and safe warmup fallback
- Synthetic accelerometer and INA219 current models
- Riemann sum energy integration (mJ) and power calculations (mW)
- REST API health, live telemetry, and tradeoff endpoints

---

## Transitioning to Physical Hardware

See [hardware/README.md](hardware/README.md) for full wiring diagrams, I2C pinout tables, and step-by-step instructions to switch from `SIMULATION` to `HARDWARE` mode.
