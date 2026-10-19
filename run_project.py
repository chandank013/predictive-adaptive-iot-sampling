"""
run_project.py
Unified startup runner for Predictive Adaptive IoT Sensing.

Launches:
  1. Backend REST API & Live Simulation Engine (uvicorn on port 8000)
  2. Frontend Dashboard (Vite on port 5173)
Handles graceful shutdown of all processes on Ctrl+C.
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"


def check_prerequisites():
    print("=" * 60)
    print("   PREDICTIVE ADAPTIVE IOT SENSING — SYSTEM RUNNER")
    print("   [SIMULATION MODE — NO PHYSICAL HARDWARE REQUIRED]")
    print("=" * 60)

    # Check MongoDB
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.0)
    mongo_up = s.connect_ex(("127.0.0.1", 27017)) == 0
    s.close()
    if mongo_up:
        print("[OK] MongoDB service detected on 127.0.0.1:27017.")
    else:
        print("[INFO] Local MongoDB not detected; system will use in-memory fallback store.")

    # Check MQTT broker
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.0)
    mqtt_up = s.connect_ex(("127.0.0.1", 1883)) == 0
    s.close()
    if mqtt_up:
        print("[OK] MQTT broker detected on 127.0.0.1:1883.")
    else:
        print("[INFO] MQTT broker not detected; using direct high-performance transport fallback.")

    print("-" * 60)


def main():
    parser = argparse.ArgumentParser(description="Start the Predictive Adaptive IoT Sensing Project")
    parser.add_argument("--api-port", type=int, default=8000, help="Backend API port (default: 8000)")
    parser.add_argument("--frontend-port", type=int, default=5173, help="Frontend Vite port (default: 5173)")
    parser.add_argument("--no-frontend", action="store_true", help="Launch backend API only (no frontend dev server)")
    parser.add_argument("--benchmark", action="store_true", help="Run deterministic 3-policy benchmark before launch")
    args = parser.parse_args()

    check_prerequisites()

    if args.benchmark:
        print("Running preliminary 3-policy benchmark suite...")
        from simulation.sim_runner import SimulationController
        controller = SimulationController(policy_name="predictive")
        controller.run_benchmark()
        print("-" * 60)

    processes = []

    def shutdown(sig=None, frame=None):
        print("\nInitiating graceful shutdown of all services...")
        for p in processes:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    p.kill()
        print("All processes stopped. Goodbye!")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

    # 1. Start Backend FastAPI Server
    api_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "api.server:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(args.api_port),
    ]
    print(f"Starting Backend API on http://127.0.0.1:{args.api_port} ...")
    env = os.environ.copy()
    env["SYSTEM_MODE"] = "SIMULATION"
    api_proc = subprocess.Popen(api_cmd, cwd=str(BACKEND_DIR), env=env)
    processes.append(api_proc)

    # Wait for backend to be healthy
    time.sleep(2)

    # 2. Start Frontend Dev Server
    if not args.no_frontend:
        npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
        fe_cmd = [npm_cmd, "run", "dev", "--", "--port", str(args.frontend_port), "--host", "127.0.0.1"]
        print(f"Starting Frontend Dashboard on http://127.0.0.1:{args.frontend_port} ...")
        fe_proc = subprocess.Popen(fe_cmd, cwd=str(FRONTEND_DIR))
        processes.append(fe_proc)

    print("=" * 60)
    print(f"  DASHBOARD URL : http://localhost:{args.frontend_port}")
    print(f"  API URL       : http://localhost:{args.api_port}")
    print(f"  SWAGGER DOCS  : http://localhost:{args.api_port}/docs")
    print(f"  MODE          : SIMULATION (No physical hardware connected)")
    print("=" * 60)
    print("Press Ctrl+C to stop all services.\n")

    try:
        while True:
            for p in processes:
                ret = p.poll()
                if ret is not None:
                    print(f"Process {p.args} exited with code {ret}. Shutting down...")
                    shutdown()
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
