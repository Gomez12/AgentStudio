from pathlib import Path

from agentstudio.persistence import initialize_database
from agentstudio.services.settings import SettingsService


def test_settings_service_stores_provider_registry_and_defaults(tmp_path: Path) -> None:
    database_path = tmp_path / "agentstudio.db"
    initialize_database(database_path)
    service = SettingsService(database_path)

    stored = service.update_llm_defaults(
        {
            "default_provider_id": "local-openai",
            "default_model": "qwen2.5-14b",
            "providers": [
                {
                    "id": "local-openai",
                    "label": "Local OpenAI",
                    "endpoint_url": "http://localhost:11434/v1",
                    "models": ["qwen2.5-14b", "llama3.1:8b"],
                }
            ],
        }
    )

    loaded = service.get_llm_defaults()

    assert stored.default_provider_id == "local-openai"
    assert loaded.default_model == "qwen2.5-14b"
    assert loaded.providers[0].endpoint_url == "http://localhost:11434/v1"
    assert loaded.providers[0].models == ["qwen2.5-14b", "llama3.1:8b"]
