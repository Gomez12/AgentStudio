from __future__ import annotations

import argparse
import time

import uvicorn

from agentstudio.api import create_app
from agentstudio.config import load_config
from agentstudio.services.runs import RunService
from agentstudio.services.schedules import ScheduleService
from agentstudio.services.worker import WorkerService


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Studio")
    parser.add_argument("role", choices=["api", "worker", "scheduler"], nargs="?", default="api")
    parser.add_argument("--once", action="store_true", help="Process one loop iteration and exit")
    parser.add_argument("--poll-interval", type=float, default=5.0, help="Polling interval for worker/scheduler")
    args = parser.parse_args()

    config = load_config()
    config.artifacts_dir.mkdir(parents=True, exist_ok=True)
    config.skills_root.mkdir(parents=True, exist_ok=True)
    config.tools_root.mkdir(parents=True, exist_ok=True)

    if args.role == "api":
        app = create_app(
            database_path=config.database_path,
            artifacts_dir=config.artifacts_dir,
            skills_root=config.skills_root,
            tools_root=config.tools_root,
            frontend_dist=config.frontend_dist,
        )
        uvicorn.run(app, host=config.host, port=config.port)
        return

    if args.role == "worker":
        worker = WorkerService(
            database_path=config.database_path,
            artifacts_dir=config.artifacts_dir,
            skills_root=config.skills_root,
            tools_root=config.tools_root,
        )
        _run_loop(worker.process_next_run, once=args.once, poll_interval=args.poll_interval)
        return

    run_service = RunService(config.database_path, config.artifacts_dir)
    scheduler = ScheduleService(config.database_path, run_service=run_service)
    _run_loop(scheduler.tick, once=args.once, poll_interval=args.poll_interval)


def _run_loop(callback, *, once: bool, poll_interval: float) -> None:
    while True:
        callback()
        if once:
            return
        time.sleep(poll_interval)
