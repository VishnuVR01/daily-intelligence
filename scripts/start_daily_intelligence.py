"""
Daily Intelligence Operational Launcher (Sprint 2 Stage 2C.2 Phase 5).
Safely launches and manages:
  1. FastAPI / Uvicorn Web Server
  2. Standalone APScheduler Daemon (scripts/run_scheduler.py)

Ensures process isolation, clear status logging, and graceful Ctrl+C shutdown.
"""
import os
import sys
import time
import signal
import subprocess
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("scripts.start_daily_intelligence")

web_process = None
scheduler_process = None


def shutdown_processes(signum=None, frame=None, exit_code=0):
    """Graceful shutdown handler for Ctrl+C and termination signals."""
    global web_process, scheduler_process
    logger.info("Initiating graceful shutdown of Daily Intelligence processes...")

    if scheduler_process and scheduler_process.poll() is None:
        logger.info("Terminating scheduler daemon process (PID: %s)...", scheduler_process.pid)
        try:
            scheduler_process.terminate()
            scheduler_process.wait(timeout=5)
        except Exception:
            scheduler_process.kill()

    if web_process and web_process.poll() is None:
        logger.info("Terminating Uvicorn web server process (PID: %s)...", web_process.pid)
        try:
            web_process.terminate()
            web_process.wait(timeout=5)
        except Exception:
            web_process.kill()

    logger.info("All Daily Intelligence processes shut down cleanly.")
    sys.exit(exit_code)


def main():
    global web_process, scheduler_process

    # Register signal handlers
    signal.signal(signal.SIGINT, shutdown_processes)
    signal.signal(signal.SIGTERM, shutdown_processes)

    venv_python = sys.executable
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    print("\n" + "=" * 75)
    print("DAILY INTELLIGENCE OPERATIONAL LAUNCHER")
    print("Starting Web Server & Autonomous Scheduler Daemon...")
    print("=" * 75 + "\n")

    env = os.environ.copy()
    env["PYTHONPATH"] = base_dir

    # 1. Start FastAPI / Uvicorn Server
    uvicorn_cmd = [
        venv_python,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]
    logger.info("Launching Web Application (http://127.0.0.1:8000)...")
    web_process = subprocess.Popen(uvicorn_cmd, cwd=base_dir, env=env)
    logger.info("Web Application started (PID: %s)", web_process.pid)

    # 2. Start Standalone Scheduler Daemon
    scheduler_cmd = [
        venv_python,
        "scripts/run_scheduler.py",
    ]
    logger.info("Launching Autonomous Scheduler Daemon (ingestion 30m / AI 10m)...")
    scheduler_process = subprocess.Popen(scheduler_cmd, cwd=base_dir, env=env)
    logger.info("Autonomous Scheduler Daemon started (PID: %s)", scheduler_process.pid)

    print("\n" + "-" * 75)
    print(f"System Running: Web App PID {web_process.pid} | Scheduler PID {scheduler_process.pid}")
    print("Press Ctrl+C to stop all processes cleanly.")
    print("-" * 75 + "\n")

    # Monitor process health
    try:
        while True:
            time.sleep(2)
            web_ret = web_process.poll()
            sched_ret = scheduler_process.poll()

            if web_ret is not None:
                logger.error("Web Application process exited unexpectedly with code %s.", web_ret)
                shutdown_processes(exit_code=1)

            if sched_ret is not None:
                logger.error("Scheduler Daemon process exited unexpectedly with code %s.", sched_ret)
                shutdown_processes(exit_code=1)
    except (KeyboardInterrupt, SystemExit):
        shutdown_processes(exit_code=0)



if __name__ == "__main__":
    main()
