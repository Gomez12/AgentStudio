from pathlib import Path

from fastapi.testclient import TestClient

from agentstudio.api import create_app
from agentstudio.runtime import CompiledAgent, RuntimeExecutor, RuntimeExecutionResult
from agentstudio.services.worker import WorkerService


class FakeExecutor(RuntimeExecutor):
    def execute(self, compiled: CompiledAgent, run_input: dict) -> RuntimeExecutionResult:
        return RuntimeExecutionResult(
            output={"agent": compiled.name, "input": run_input},
            events=[{"event_type": "message", "payload": {"text": "done"}}],
            artifacts=[],
        )


def test_agent_studio_api_flow(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills" / "writer"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        """---
name: writer
description: Draft clear copy
---
Write clearly.
""",
        encoding="utf-8",
    )

    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    (tools_dir / "search_tool.py").write_text(
        """
TOOL_METADATA = {"name": "search", "description": "Search", "input_schema": {}}

def build_tool():
    return lambda query: query
""".strip(),
        encoding="utf-8",
    )

    app = create_app(
        database_path=tmp_path / "agentstudio.db",
        artifacts_dir=tmp_path / "artifacts",
        skills_root=tmp_path / "skills",
        tools_root=tmp_path / "tools",
        executor=FakeExecutor(),
    )
    client = TestClient(app)

    skills_response = client.get("/catalog/skills")
    tools_response = client.get("/catalog/tools")
    assert skills_response.json()["items"][0]["slug"] == "writer"
    assert tools_response.json()["items"][0]["slug"] == "search_tool"

    agent_response = client.post(
        "/agents",
        json={
            "name": "Writer",
            "description": "Writes answers",
            "instructions": "Produce polished answers.",
            "model": {"provider": "openai", "model": "gpt-4.1"},
            "runtime_params": {"temperature": 0.2},
            "skills": [
                {
                    "slug": "writer",
                    "name": "writer",
                    "description": "Draft clear copy",
                    "snapshot": {"name": "writer", "description": "Draft clear copy"},
                }
            ],
            "tools": [
                {
                    "slug": "search_tool",
                    "name": "search",
                    "description": "Search",
                    "snapshot": {"name": "search", "description": "Search"},
                }
            ],
            "children": [],
        },
    )
    agent_id = agent_response.json()["id"]

    version_response = client.post(f"/agents/{agent_id}/versions")
    version_id = version_response.json()["id"]

    run_response = client.post(
        f"/agent-versions/{version_id}/run",
        json={"input": {"prompt": "Hello"}, "trigger_type": "manual"},
    )
    run_id = run_response.json()["id"]

    worker = WorkerService(
        database_path=tmp_path / "agentstudio.db",
        artifacts_dir=tmp_path / "artifacts",
        skills_root=tmp_path / "skills",
        tools_root=tmp_path / "tools",
        executor=FakeExecutor(),
    )
    worker.process_next_run()

    run_detail = client.get(f"/runs/{run_id}")
    run_events = client.get(f"/runs/{run_id}/events")
    exported = client.get(f"/exports/agents/{agent_id}")
    imported = client.post("/imports/agents", json=exported.json())
    settings = client.patch(
        "/settings/llm",
        json={
            "default_provider_id": "local-openai",
            "default_model": "qwen2.5-14b",
            "providers": [
                {
                    "id": "openai",
                    "label": "OpenAI",
                    "endpoint_url": "https://api.openai.com/v1",
                    "models": ["gpt-4.1-mini", "gpt-4.1"],
                },
                {
                    "id": "local-openai",
                    "label": "Local OpenAI",
                    "endpoint_url": "http://localhost:11434/v1",
                    "models": ["qwen2.5-14b"],
                },
            ],
        },
    )
    schedule = client.post(
        "/schedules",
        json={
            "agent_version_id": version_id,
            "schedule_type": "interval",
            "expression": "15m",
        },
    )

    assert run_detail.json()["status"] == "completed"
    assert run_events.json()[2]["event_type"] == "message"
    assert imported.json()["name"] == "Writer"
    assert settings.json()["default_provider_id"] == "local-openai"
    assert settings.json()["providers"][1]["endpoint_url"] == "http://localhost:11434/v1"
    assert schedule.json()["schedule_type"] == "interval"
