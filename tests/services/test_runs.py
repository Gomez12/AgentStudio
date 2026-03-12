from pathlib import Path

from agentstudio.domain.models import AgentDraftPayload
from agentstudio.persistence import initialize_database
from agentstudio.runtime import CompiledAgent, RuntimeExecutor, RuntimeExecutionResult
from agentstudio.services.agents import AgentService
from agentstudio.services.runs import RunService
from agentstudio.services.settings import SettingsService
from agentstudio.services.worker import WorkerService


class FakeExecutor(RuntimeExecutor):
    def execute(self, compiled: CompiledAgent, run_input: dict) -> RuntimeExecutionResult:
        return RuntimeExecutionResult(
            output={
                "summary": f"Executed {compiled.name}",
                "input": run_input,
            },
            events=[
                {"event_type": "message", "payload": {"text": "started"}},
                {"event_type": "message", "payload": {"text": "finished"}},
            ],
            artifacts=[
                {
                    "filename": "result.txt",
                    "content": "Execution result",
                    "mime_type": "text/plain",
                }
            ],
        )


def test_enqueue_and_process_run_with_events_and_artifacts(tmp_path: Path) -> None:
    database_path = tmp_path / "agentstudio.db"
    artifacts_dir = tmp_path / "artifacts"
    initialize_database(database_path)

    agent_service = AgentService(database_path)
    run_service = RunService(database_path, artifacts_dir)
    settings_service = SettingsService(database_path)
    settings_service.update_llm_defaults(
        {
            "default_provider_id": "openai",
            "default_model": "gpt-4.1-mini",
            "providers": [
                {
                    "id": "openai",
                    "label": "OpenAI",
                    "endpoint_url": "https://api.openai.com/v1",
                    "models": ["gpt-4.1-mini", "gpt-4.1"],
                }
            ],
        }
    )

    agent = agent_service.create_or_update_agent(
        AgentDraftPayload(
            name="Writer",
            description="Writes responses",
            instructions="Produce a concise answer.",
            model={"provider": "openai", "model": "gpt-4.1"},
        )
    )
    version = agent_service.publish_version(agent.id)
    run = run_service.enqueue_run(version.id, {"prompt": "Hello"}, trigger_type="manual")

    worker = WorkerService(
        database_path=database_path,
        artifacts_dir=artifacts_dir,
        skills_root=tmp_path / "skills",
        tools_root=tmp_path / "tools",
        executor=FakeExecutor(),
    )
    processed = worker.process_next_run()

    stored_run = run_service.get_run(run.id)
    events = run_service.list_run_events(run.id)
    artifacts = run_service.list_artifacts(run.id)

    assert processed is not None
    assert processed.id == run.id
    assert stored_run.status == "completed"
    assert stored_run.result["summary"] == "Executed Writer"
    assert [event.event_type for event in events] == ["queued", "started", "message", "message", "completed"]
    assert artifacts[0].mime_type == "text/plain"
    assert (artifacts_dir / artifacts[0].relative_path).read_text(encoding="utf-8") == "Execution result"
