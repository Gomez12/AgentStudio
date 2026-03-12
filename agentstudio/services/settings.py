from __future__ import annotations

import json
from pathlib import Path

from agentstudio.domain.models import LLMSettings
from agentstudio.persistence import database_connection, initialize_database


class SettingsService:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        initialize_database(database_path)

    def get_llm_defaults(self) -> LLMSettings:
        with database_connection(self.database_path) as connection:
            row = connection.execute(
                "SELECT value_json FROM settings WHERE key = 'llm_defaults'"
            ).fetchone()
        if row is None:
            return LLMSettings()
        payload = json.loads(row["value_json"])
        if "provider" in payload or "model" in payload:
            return LLMSettings(
                default_provider_id=str(payload.get("provider") or "openai"),
                default_model=str(payload.get("model") or "gpt-4.1-mini"),
                providers=LLMSettings().providers,
            )
        return LLMSettings.model_validate(payload)

    def update_llm_defaults(self, payload: dict) -> LLMSettings:
        settings = LLMSettings.model_validate(payload)
        with database_connection(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO settings (key, value_json)
                VALUES ('llm_defaults', ?)
                ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json
                """,
                (settings.model_dump_json(),),
            )
        return settings
