from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from agentstudio.domain.models import ArtifactRecord, RunEventRecord, RunRecord
from agentstudio.persistence import database_connection, initialize_database, utcnow


class RunService:
    def __init__(self, database_path: Path, artifacts_dir: Path) -> None:
        self.database_path = database_path
        self.artifacts_dir = artifacts_dir
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        initialize_database(database_path)

    def enqueue_run(
        self,
        agent_version_id: str,
        run_input: dict[str, Any],
        *,
        trigger_type: str,
        trigger_payload: dict[str, Any] | None = None,
    ) -> RunRecord:
        now = utcnow()
        run_id = str(uuid.uuid4())
        payload = trigger_payload or {}
        with database_connection(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO runs (
                    id, agent_version_id, status, trigger_type, trigger_payload_json,
                    input_json, created_at
                ) VALUES (?, ?, 'queued', ?, ?, ?, ?)
                """,
                (
                    run_id,
                    agent_version_id,
                    trigger_type,
                    json.dumps(payload),
                    json.dumps(run_input),
                    now.isoformat(),
                ),
            )
        self.append_event(run_id, "queued", {"trigger_type": trigger_type})
        return self.get_run(run_id)

    def list_runs(self) -> list[RunRecord]:
        with database_connection(self.database_path) as connection:
            rows = connection.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
        return [self._to_run(row) for row in rows]

    def get_run(self, run_id: str) -> RunRecord:
        with database_connection(self.database_path) as connection:
            row = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return self._to_run(row)

    def list_run_events(self, run_id: str) -> list[RunEventRecord]:
        with database_connection(self.database_path) as connection:
            rows = connection.execute(
                "SELECT * FROM run_events WHERE run_id = ? ORDER BY created_at ASC",
                (run_id,),
            ).fetchall()
        return [self._to_event(row) for row in rows]

    def list_artifacts(self, run_id: str) -> list[ArtifactRecord]:
        with database_connection(self.database_path) as connection:
            rows = connection.execute(
                "SELECT * FROM artifacts WHERE run_id = ? ORDER BY created_at ASC",
                (run_id,),
            ).fetchall()
        return [self._to_artifact(row) for row in rows]

    def claim_next_run(self, lease_owner: str, lease_seconds: int = 300) -> RunRecord | None:
        now = utcnow()
        expires_at = now + timedelta(seconds=lease_seconds)
        with database_connection(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT * FROM runs
                WHERE status = 'queued'
                   OR (status = 'running' AND lease_expires_at IS NOT NULL AND lease_expires_at < ?)
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (now.isoformat(),),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                """
                UPDATE runs
                SET status = 'running',
                    lease_owner = ?,
                    lease_expires_at = ?,
                    started_at = COALESCE(started_at, ?)
                WHERE id = ?
                """,
                (lease_owner, expires_at.isoformat(), now.isoformat(), row["id"]),
            )
        self.append_event(row["id"], "started", {"lease_owner": lease_owner})
        return self.get_run(row["id"])

    def complete_run(self, run_id: str, result: dict[str, Any]) -> RunRecord:
        now = utcnow()
        with database_connection(self.database_path) as connection:
            connection.execute(
                """
                UPDATE runs
                SET status = 'completed',
                    result_json = ?,
                    finished_at = ?,
                    lease_owner = NULL,
                    lease_expires_at = NULL
                WHERE id = ?
                """,
                (json.dumps(result), now.isoformat(), run_id),
            )
        self.append_event(run_id, "completed", {"result": result})
        return self.get_run(run_id)

    def fail_run(self, run_id: str, error: str) -> RunRecord:
        now = utcnow()
        with database_connection(self.database_path) as connection:
            connection.execute(
                """
                UPDATE runs
                SET status = 'failed',
                    error_text = ?,
                    finished_at = ?,
                    lease_owner = NULL,
                    lease_expires_at = NULL
                WHERE id = ?
                """,
                (error, now.isoformat(), run_id),
            )
        self.append_event(run_id, "failed", {"error": error})
        return self.get_run(run_id)

    def append_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> RunEventRecord:
        event_id = str(uuid.uuid4())
        now = utcnow()
        with database_connection(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO run_events (id, run_id, event_type, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_id, run_id, event_type, json.dumps(payload), now.isoformat()),
            )
        return RunEventRecord(id=event_id, run_id=run_id, event_type=event_type, payload=payload, created_at=now)

    def store_artifact(
        self,
        run_id: str,
        *,
        filename: str,
        content: str,
        mime_type: str,
        event_id: str | None = None,
    ) -> ArtifactRecord:
        artifact_id = str(uuid.uuid4())
        now = utcnow()
        relative_path = f"{run_id}/{artifact_id}-{filename}"
        absolute_path = self.artifacts_dir / relative_path
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_text(content, encoding="utf-8")
        size_bytes = absolute_path.stat().st_size
        with database_connection(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO artifacts (id, run_id, event_id, relative_path, mime_type, size_bytes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    run_id,
                    event_id,
                    relative_path,
                    mime_type,
                    size_bytes,
                    now.isoformat(),
                ),
            )
        return ArtifactRecord(
            id=artifact_id,
            run_id=run_id,
            event_id=event_id,
            relative_path=relative_path,
            mime_type=mime_type,
            size_bytes=size_bytes,
            created_at=now,
        )

    def _to_run(self, row: Any) -> RunRecord:
        return RunRecord(
            id=row["id"],
            agent_version_id=row["agent_version_id"],
            status=row["status"],
            trigger_type=row["trigger_type"],
            trigger_payload=json.loads(row["trigger_payload_json"]),
            lease_owner=row["lease_owner"],
            lease_expires_at=datetime.fromisoformat(row["lease_expires_at"]) if row["lease_expires_at"] else None,
            input=json.loads(row["input_json"]),
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            error=row["error_text"],
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
        )

    def _to_event(self, row: Any) -> RunEventRecord:
        return RunEventRecord(
            id=row["id"],
            run_id=row["run_id"],
            event_type=row["event_type"],
            payload=json.loads(row["payload_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _to_artifact(self, row: Any) -> ArtifactRecord:
        return ArtifactRecord(
            id=row["id"],
            run_id=row["run_id"],
            event_id=row["event_id"],
            relative_path=row["relative_path"],
            mime_type=row["mime_type"],
            size_bytes=row["size_bytes"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
