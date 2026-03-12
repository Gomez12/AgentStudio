from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from agentstudio.catalog import scan_skills, scan_tools
from agentstudio.domain.models import (
    AgentDraftPayload,
    AgentExport,
    RunCreatePayload,
    ScheduleCreatePayload,
    ScheduleUpdatePayload,
)
from agentstudio.persistence import initialize_database
from agentstudio.runtime import RuntimeExecutor
from agentstudio.services.agents import AgentService
from agentstudio.services.runs import RunService
from agentstudio.services.schedules import ScheduleService
from agentstudio.services.settings import SettingsService


def create_app(
    *,
    database_path: Path,
    artifacts_dir: Path,
    skills_root: Path,
    tools_root: Path,
    frontend_dist: Path | None = None,
    executor: RuntimeExecutor | None = None,
) -> FastAPI:
    initialize_database(database_path)
    agent_service = AgentService(database_path)
    run_service = RunService(database_path, artifacts_dir)
    settings_service = SettingsService(database_path)
    schedule_service = ScheduleService(database_path, run_service=run_service)

    app = FastAPI(title="Agent Studio")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/catalog/skills")
    def get_skills() -> dict[str, Any]:
        return scan_skills(skills_root).model_dump(mode="json")

    @app.get("/catalog/tools")
    def get_tools() -> dict[str, Any]:
        return scan_tools(tools_root).model_dump(mode="json")

    @app.post("/catalog/refresh")
    def refresh_catalog() -> dict[str, Any]:
        return {
            "skills": scan_skills(skills_root).model_dump(mode="json"),
            "tools": scan_tools(tools_root).model_dump(mode="json"),
        }

    @app.get("/agents")
    def list_agents() -> list[dict[str, Any]]:
        return [agent.model_dump(mode="json") for agent in agent_service.list_agents()]

    @app.post("/agents")
    def create_agent(payload: AgentDraftPayload) -> dict[str, Any]:
        return agent_service.create_or_update_agent(payload).model_dump(mode="json")

    @app.get("/agents/{agent_id}")
    def get_agent(agent_id: str) -> dict[str, Any]:
        try:
            agent = agent_service.get_agent(agent_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Agent not found") from exc
        versions = agent_service.list_versions(agent_id)
        return {
            **agent.model_dump(mode="json"),
            "versions": [version.model_dump(mode="json") for version in versions],
        }

    @app.post("/agents/{agent_id}/versions")
    def publish_agent(agent_id: str) -> dict[str, Any]:
        try:
            return agent_service.publish_version(agent_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Agent not found") from exc

    @app.get("/agent-versions/{version_id}")
    def get_version(version_id: str) -> dict[str, Any]:
        try:
            return agent_service.get_version(version_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Version not found") from exc

    @app.post("/agent-versions/{version_id}/run")
    def create_run(version_id: str, payload: RunCreatePayload) -> dict[str, Any]:
        try:
            agent_service.get_version(version_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Version not found") from exc
        run = run_service.enqueue_run(
            version_id,
            payload.input,
            trigger_type=payload.trigger_type,
            trigger_payload=payload.trigger_payload,
        )
        return run.model_dump(mode="json")

    @app.get("/runs")
    def list_runs() -> list[dict[str, Any]]:
        return [run.model_dump(mode="json") for run in run_service.list_runs()]

    @app.get("/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        try:
            return run_service.get_run(run_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Run not found") from exc

    @app.get("/runs/{run_id}/events")
    def list_run_events(run_id: str) -> list[dict[str, Any]]:
        return [event.model_dump(mode="json") for event in run_service.list_run_events(run_id)]

    @app.get("/runs/{run_id}/artifacts")
    def list_artifacts(run_id: str) -> list[dict[str, Any]]:
        return [artifact.model_dump(mode="json") for artifact in run_service.list_artifacts(run_id)]

    @app.get("/schedules")
    def list_schedules() -> list[dict[str, Any]]:
        return [schedule.model_dump(mode="json") for schedule in schedule_service.list_schedules()]

    @app.post("/schedules")
    def create_schedule(payload: ScheduleCreatePayload) -> dict[str, Any]:
        return schedule_service.create_schedule(payload).model_dump(mode="json")

    @app.patch("/schedules/{schedule_id}")
    def update_schedule(schedule_id: str, payload: ScheduleUpdatePayload) -> dict[str, Any]:
        try:
            return schedule_service.update_schedule(schedule_id, payload).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Schedule not found") from exc

    @app.get("/exports/agents/{agent_id}")
    def export_agent(agent_id: str) -> dict[str, Any]:
        try:
            return agent_service.export_agent(agent_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Agent not found") from exc

    @app.post("/imports/agents")
    def import_agent(payload: AgentExport) -> dict[str, Any]:
        return agent_service.import_agent(payload).model_dump(mode="json")

    @app.get("/settings/llm")
    def get_llm_settings() -> dict[str, Any]:
        return settings_service.get_llm_defaults().model_dump(mode="json")

    @app.patch("/settings/llm")
    def patch_llm_settings(payload: dict[str, Any]) -> dict[str, Any]:
        return settings_service.update_llm_defaults(payload).model_dump(mode="json")

    if frontend_dist and frontend_dist.exists():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    return app
