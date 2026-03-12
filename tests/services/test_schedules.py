from datetime import timedelta
from pathlib import Path

from agentstudio.domain.models import AgentDraftPayload, ScheduleCreatePayload
from agentstudio.persistence import initialize_database, utcnow
from agentstudio.services.agents import AgentService
from agentstudio.services.runs import RunService
from agentstudio.services.schedules import ScheduleService


def test_schedule_tick_enqueues_a_run_without_duplication(tmp_path: Path) -> None:
    database_path = tmp_path / "agentstudio.db"
    initialize_database(database_path)
    agent_service = AgentService(database_path)
    run_service = RunService(database_path, tmp_path / "artifacts")
    schedule_service = ScheduleService(database_path, run_service=run_service)

    agent = agent_service.create_or_update_agent(
        AgentDraftPayload(
            name="Writer",
            description="Writes",
            instructions="Write.",
            model={"provider": "openai", "model": "gpt-4.1"},
        )
    )
    version = agent_service.publish_version(agent.id)
    schedule = schedule_service.create_schedule(
        ScheduleCreatePayload(
            agent_version_id=version.id,
            schedule_type="interval",
            expression="15m",
        )
    )

    due_time = schedule.next_run_at + timedelta(seconds=1)
    first = schedule_service.tick(due_time)
    second = schedule_service.tick(due_time)

    runs = run_service.list_runs()
    updated_schedule = schedule_service.get_schedule(schedule.id)

    assert len(first) == 1
    assert second == []
    assert len(runs) == 1
    assert runs[0].trigger_type == "schedule"
    assert updated_schedule.last_run_at == due_time
