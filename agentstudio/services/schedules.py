from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from pathlib import Path

from croniter import croniter

from agentstudio.domain.models import ScheduleCreatePayload, ScheduleRecord, ScheduleUpdatePayload
from agentstudio.persistence import database_connection, initialize_database, utcnow
from agentstudio.services.runs import RunService


class ScheduleService:
    def __init__(self, database_path: Path, run_service: RunService | None = None) -> None:
        self.database_path = database_path
        self.run_service = run_service
        initialize_database(database_path)

    def create_schedule(self, payload: ScheduleCreatePayload) -> ScheduleRecord:
        now = utcnow()
        schedule_id = str(uuid.uuid4())
        next_run = self._next_run_at(payload.schedule_type, payload.expression, now)
        with database_connection(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO schedules (
                    id, agent_version_id, status, schedule_type, expression,
                    next_run_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    schedule_id,
                    payload.agent_version_id,
                    payload.status,
                    payload.schedule_type,
                    payload.expression,
                    next_run.isoformat() if next_run else None,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
        return self.get_schedule(schedule_id)

    def list_schedules(self) -> list[ScheduleRecord]:
        with database_connection(self.database_path) as connection:
            rows = connection.execute("SELECT * FROM schedules ORDER BY created_at DESC").fetchall()
        return [self._to_schedule(row) for row in rows]

    def get_schedule(self, schedule_id: str) -> ScheduleRecord:
        with database_connection(self.database_path) as connection:
            row = connection.execute("SELECT * FROM schedules WHERE id = ?", (schedule_id,)).fetchone()
        if row is None:
            raise KeyError(schedule_id)
        return self._to_schedule(row)

    def update_schedule(self, schedule_id: str, payload: ScheduleUpdatePayload) -> ScheduleRecord:
        current = self.get_schedule(schedule_id)
        status = payload.status or current.status
        expression = payload.expression or current.expression
        now = utcnow()
        next_run = self._next_run_at(current.schedule_type, expression, now) if status == "active" else None
        with database_connection(self.database_path) as connection:
            connection.execute(
                """
                UPDATE schedules
                SET status = ?, expression = ?, next_run_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    expression,
                    next_run.isoformat() if next_run else None,
                    now.isoformat(),
                    schedule_id,
                ),
            )
        return self.get_schedule(schedule_id)

    def tick(self, now: datetime | None = None) -> list[str]:
        if self.run_service is None:
            return []
        current_time = now or utcnow()
        triggered: list[str] = []
        with database_connection(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT * FROM schedules
                WHERE status = 'active' AND next_run_at IS NOT NULL AND next_run_at <= ?
                ORDER BY next_run_at ASC
                """,
                (current_time.isoformat(),),
            ).fetchall()
            for row in rows:
                run = self.run_service.enqueue_run(
                    row["agent_version_id"],
                    {},
                    trigger_type="schedule",
                    trigger_payload={"schedule_id": row["id"]},
                )
                next_run = self._next_run_at(row["schedule_type"], row["expression"], current_time)
                connection.execute(
                    """
                    UPDATE schedules
                    SET last_run_at = ?, next_run_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        current_time.isoformat(),
                        next_run.isoformat() if next_run else None,
                        current_time.isoformat(),
                        row["id"],
                    ),
                )
                triggered.append(run.id)
        return triggered

    def _next_run_at(self, schedule_type: str, expression: str, base: datetime) -> datetime | None:
        if schedule_type == "interval":
            return base + self._parse_interval(expression)
        if schedule_type == "cron":
            return croniter(expression, base).get_next(datetime)
        raise ValueError(f"Unsupported schedule_type: {schedule_type}")

    def _parse_interval(self, expression: str) -> timedelta:
        unit = expression[-1]
        value = int(expression[:-1])
        if unit == "m":
            return timedelta(minutes=value)
        if unit == "h":
            return timedelta(hours=value)
        raise ValueError(f"Unsupported interval expression: {expression}")

    def _to_schedule(self, row) -> ScheduleRecord:
        return ScheduleRecord(
            id=row["id"],
            agent_version_id=row["agent_version_id"],
            status=row["status"],
            schedule_type=row["schedule_type"],
            expression=row["expression"],
            next_run_at=datetime.fromisoformat(row["next_run_at"]) if row["next_run_at"] else None,
            last_run_at=datetime.fromisoformat(row["last_run_at"]) if row["last_run_at"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
