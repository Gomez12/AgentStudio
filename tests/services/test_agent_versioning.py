from pathlib import Path

from agentstudio.domain.models import AgentDraftPayload, AgentNodePayload, SelectedCatalogItem
from agentstudio.persistence import initialize_database
from agentstudio.services.agents import AgentService


def test_agent_versions_are_immutable_and_keep_catalog_snapshots(tmp_path: Path) -> None:
    database_path = tmp_path / "agentstudio.db"
    initialize_database(database_path)
    service = AgentService(database_path)

    agent = service.create_or_update_agent(
        AgentDraftPayload(
            agent_id=None,
            name="Research Crew",
            description="Runs a supervisor with specialist children",
            instructions="Coordinate a research and writing workflow.",
            model={"provider": "openai", "model": "gpt-4.1"},
            runtime_params={"temperature": 0.1},
            skills=[
                SelectedCatalogItem(
                    slug="writer",
                    name="writer",
                    description="Draft clear copy",
                    snapshot={"name": "writer", "description": "Draft clear copy"},
                )
            ],
            tools=[
                SelectedCatalogItem(
                    slug="search_tool",
                    name="search",
                    description="Search external sources",
                    snapshot={"name": "search", "description": "Search external sources"},
                )
            ],
            children=[
                AgentNodePayload(
                    name="Researcher",
                    instructions="Collect source material.",
                    model={"provider": "openai", "model": "gpt-4.1-mini"},
                    runtime_params={},
                    skills=[],
                    tools=[],
                )
            ],
        )
    )

    first_version = service.publish_version(agent.id)
    service.create_or_update_agent(
        AgentDraftPayload(
            agent_id=agent.id,
            name="Research Crew",
            description="Updated description",
            instructions="Coordinate a research and writing workflow with editing.",
            model={"provider": "openai", "model": "gpt-4.1"},
            runtime_params={"temperature": 0.2},
            skills=[
                SelectedCatalogItem(
                    slug="writer",
                    name="writer",
                    description="Draft and edit copy",
                    snapshot={"name": "writer", "description": "Draft and edit copy"},
                )
            ],
            tools=[],
            children=[],
        )
    )
    second_version = service.publish_version(agent.id)

    stored_first = service.get_version(first_version.id)
    stored_second = service.get_version(second_version.id)

    assert stored_first.version_number == 1
    assert stored_first.description == "Runs a supervisor with specialist children"
    assert stored_first.skills[0].snapshot["description"] == "Draft clear copy"
    assert stored_first.children[0].name == "Researcher"

    assert stored_second.version_number == 2
    assert stored_second.description == "Updated description"
    assert stored_second.skills[0].snapshot["description"] == "Draft and edit copy"
    assert stored_second.children == []
