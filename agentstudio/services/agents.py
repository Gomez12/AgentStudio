from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from agentstudio.domain.models import AgentDraftPayload, AgentExport, AgentRecord, AgentVersionRecord
from agentstudio.persistence import database_connection, initialize_database, load_json, utcnow


class AgentService:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        initialize_database(database_path)

    def create_or_update_agent(self, payload: AgentDraftPayload) -> AgentRecord:
        now = utcnow()
        agent_id = payload.agent_id or str(uuid.uuid4())
        stored_payload = payload.model_copy(update={"agent_id": None})

        with database_connection(self.database_path) as connection:
            current = connection.execute(
                "SELECT created_at FROM agents WHERE id = ?",
                (agent_id,),
            ).fetchone()
            created_at = current["created_at"] if current else now.isoformat()
            connection.execute(
                """
                INSERT INTO agents (id, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    agent_id,
                    stored_payload.model_dump_json(),
                    created_at,
                    now.isoformat(),
                ),
            )

        return AgentRecord(
            id=agent_id,
            created_at=now if not current else datetime.fromisoformat(created_at),
            updated_at=now,
            **stored_payload.model_dump(),
        )

    def get_agent(self, agent_id: str) -> AgentRecord:
        with database_connection(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM agents WHERE id = ?",
                (agent_id,),
            ).fetchone()
        if row is None:
            raise KeyError(agent_id)
        payload = AgentDraftPayload.model_validate_json(row["payload_json"])
        return AgentRecord(
            id=row["id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            **payload.model_dump(),
        )

    def list_agents(self) -> list[AgentRecord]:
        with database_connection(self.database_path) as connection:
            rows = connection.execute(
                "SELECT * FROM agents ORDER BY updated_at DESC"
            ).fetchall()
        agents: list[AgentRecord] = []
        for row in rows:
            payload = AgentDraftPayload.model_validate_json(row["payload_json"])
            agents.append(
                AgentRecord(
                    id=row["id"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    **payload.model_dump(),
                )
            )
        return agents

    def publish_version(self, agent_id: str) -> AgentVersionRecord:
        agent = self.get_agent(agent_id)
        now = utcnow()
        version_id = str(uuid.uuid4())

        with database_connection(self.database_path) as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version_number), 0) AS max_version FROM agent_versions WHERE agent_id = ?",
                (agent_id,),
            ).fetchone()
            next_version = int(row["max_version"]) + 1
            snapshot = agent.model_dump(mode="json")
            connection.execute(
                """
                INSERT INTO agent_versions (id, agent_id, version_number, snapshot_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    agent_id,
                    next_version,
                    AgentVersionRecord(
                        id=version_id,
                        agent_id=agent_id,
                        version_number=next_version,
                        created_at=now,
                        **{
                            key: value
                            for key, value in snapshot.items()
                            if key not in {"id", "created_at", "updated_at", "agent_id"}
                        },
                    ).model_dump_json(),
                    now.isoformat(),
                ),
            )

        return self.get_version(version_id)

    def get_version(self, version_id: str) -> AgentVersionRecord:
        with database_connection(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM agent_versions WHERE id = ?",
                (version_id,),
            ).fetchone()
        if row is None:
            raise KeyError(version_id)
        snapshot = AgentVersionRecord.model_validate_json(row["snapshot_json"])
        return snapshot

    def list_versions(self, agent_id: str) -> list[AgentVersionRecord]:
        with database_connection(self.database_path) as connection:
            rows = connection.execute(
                "SELECT id FROM agent_versions WHERE agent_id = ? ORDER BY version_number DESC",
                (agent_id,),
            ).fetchall()
        return [self.get_version(row["id"]) for row in rows]

    def export_agent(self, agent_id: str) -> AgentExport:
        return AgentExport(agent=self.get_agent(agent_id), versions=self.list_versions(agent_id))

    def import_agent(self, export_payload: AgentExport) -> AgentRecord:
        imported = self.create_or_update_agent(
            AgentDraftPayload(
                name=export_payload.agent.name,
                description=export_payload.agent.description,
                instructions=export_payload.agent.instructions,
                model=export_payload.agent.model,
                runtime_params=export_payload.agent.runtime_params,
                skills=export_payload.agent.skills,
                tools=export_payload.agent.tools,
                children=export_payload.agent.children,
            )
        )
        for version in sorted(export_payload.versions, key=lambda item: item.version_number):
            self._store_imported_version(imported.id, version)
        return imported

    def _store_imported_version(self, agent_id: str, version: AgentVersionRecord) -> None:
        with database_connection(self.database_path) as connection:
            existing = connection.execute(
                """
                SELECT id FROM agent_versions
                WHERE agent_id = ? AND version_number = ?
                """,
                (agent_id, version.version_number),
            ).fetchone()
            if existing:
                return
            new_id = str(uuid.uuid4())
            imported = version.model_copy(update={"id": new_id, "agent_id": agent_id})
            connection.execute(
                """
                INSERT INTO agent_versions (id, agent_id, version_number, snapshot_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    new_id,
                    agent_id,
                    version.version_number,
                    imported.model_dump_json(),
                    imported.created_at.isoformat(),
                ),
            )
