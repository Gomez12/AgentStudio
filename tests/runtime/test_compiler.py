from pathlib import Path

from agentstudio.domain.models import AgentNodePayload, AgentVersionRecord, SelectedCatalogItem
from agentstudio.runtime import compile_agent_version


def test_compile_single_agent_version_to_deepagents_spec(tmp_path: Path) -> None:
    version = AgentVersionRecord(
        id="version-1",
        agent_id="agent-1",
        version_number=1,
        name="Writer",
        description="Writes responses",
        instructions="Write a polished answer.",
        model={"provider": "openai", "model": "gpt-4.1"},
        runtime_params={"temperature": 0.2},
        skills=[
            SelectedCatalogItem(
                slug="writer",
                name="writer",
                description="Draft clear copy",
                snapshot={"name": "writer"},
            )
        ],
        tools=[
            SelectedCatalogItem(
                slug="search_tool",
                name="search",
                description="Search the web",
                snapshot={"name": "search"},
            )
        ],
        children=[],
        created_at="2026-03-12T00:00:00Z",
    )

    compiled = compile_agent_version(
        version,
        skills_root=tmp_path / "skills",
        tools_root=tmp_path / "tools",
        app_defaults={"provider": "openai", "model": "gpt-4.1-mini"},
    )

    assert compiled.name == "Writer"
    assert compiled.provider_id == "openai"
    assert compiled.endpoint_url is None
    assert compiled.model_name == "gpt-4.1"
    assert compiled.skills == ["/skills/writer/"]
    assert compiled.tools == ["search_tool"]
    assert compiled.subagents == []


def test_compile_supervisor_includes_child_agents_and_default_model(tmp_path: Path) -> None:
    version = AgentVersionRecord(
        id="version-2",
        agent_id="agent-2",
        version_number=3,
        name="Research Crew",
        description="Supervisor agent",
        instructions="Delegate research and writing tasks.",
        model={},
        runtime_params={},
        skills=[],
        tools=[],
        children=[
            AgentNodePayload(
                name="Researcher",
                instructions="Gather facts.",
                model={"provider": "openai", "model": "gpt-4.1-mini"},
                runtime_params={},
                skills=[
                    SelectedCatalogItem(
                        slug="research",
                        name="research",
                        description="Research skill",
                        snapshot={"name": "research"},
                    )
                ],
                tools=[],
            )
        ],
        created_at="2026-03-12T00:00:00Z",
    )

    compiled = compile_agent_version(
        version,
        skills_root=tmp_path / "skills",
        tools_root=tmp_path / "tools",
        app_defaults={
            "default_provider_id": "anthropic",
            "default_model": "claude-sonnet-4-5",
            "providers": [
                {
                    "id": "openai",
                    "label": "OpenAI",
                    "endpoint_url": "https://api.openai.com/v1",
                    "models": ["gpt-4.1-mini"],
                },
                {
                    "id": "anthropic",
                    "label": "Anthropic",
                    "endpoint_url": "",
                    "models": ["claude-sonnet-4-5"],
                },
            ],
        },
    )

    assert compiled.provider_id == "anthropic"
    assert compiled.model_name == "claude-sonnet-4-5"
    assert compiled.subagents == [
        {
            "name": "Researcher",
            "description": "Sub-agent: Researcher",
            "system_prompt": "Gather facts.",
            "provider_id": "openai",
            "endpoint_url": "https://api.openai.com/v1",
            "model": "gpt-4.1-mini",
            "skills": ["/skills/research/"],
            "tools": [],
        }
    ]


def test_compile_uses_saved_provider_registry_entry(tmp_path: Path) -> None:
    version = AgentVersionRecord(
        id="version-3",
        agent_id="agent-3",
        version_number=1,
        name="Local Model Agent",
        description="Uses a custom endpoint",
        instructions="Answer with the local model.",
        model={"provider_id": "local-openai", "model": "qwen2.5-14b"},
        runtime_params={},
        skills=[],
        tools=[],
        children=[],
        created_at="2026-03-12T00:00:00Z",
    )

    compiled = compile_agent_version(
        version,
        skills_root=tmp_path / "skills",
        tools_root=tmp_path / "tools",
        app_defaults={
            "default_provider_id": "openai",
            "default_model": "gpt-4.1-mini",
            "providers": [
                {
                    "id": "openai",
                    "label": "OpenAI",
                    "endpoint_url": "https://api.openai.com/v1",
                    "models": ["gpt-4.1-mini"],
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

    assert compiled.provider_id == "local-openai"
    assert compiled.endpoint_url == "http://localhost:11434/v1"
    assert compiled.model_name == "qwen2.5-14b"
