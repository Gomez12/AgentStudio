from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field

from agentstudio.catalog import scan_tools
from agentstudio.domain.models import AgentNodePayload, AgentVersionRecord, ProviderConfig, SelectedCatalogItem

try:  # pragma: no cover - import depends on optional provider package
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover
    ChatOpenAI = None

try:  # pragma: no cover - import is environment-dependent
    from deepagents import create_deep_agent
except Exception:  # pragma: no cover
    create_deep_agent = None


class CompiledAgent(BaseModel):
    name: str
    provider_id: str
    endpoint_url: str | None = None
    model_name: str
    system_prompt: str
    runtime_params: dict[str, Any] = Field(default_factory=dict)
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    subagents: list[dict[str, Any]] = Field(default_factory=list)


class RuntimeExecutionResult(BaseModel):
    output: dict[str, Any] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)


class RuntimeExecutor(Protocol):
    def execute(self, compiled: CompiledAgent, run_input: dict[str, Any]) -> RuntimeExecutionResult:
        ...


class DeepAgentsExecutor:
    def __init__(self, tools_root: Path) -> None:
        self.tools_root = tools_root

    def execute(self, compiled: CompiledAgent, run_input: dict[str, Any]) -> RuntimeExecutionResult:
        if create_deep_agent is None:
            return RuntimeExecutionResult(
                output={"error": "deepagents is unavailable"},
                events=[{"event_type": "error", "payload": {"message": "deepagents is unavailable"}}],
            )

        tool_items = scan_tools(self.tools_root).items
        tools = []
        for slug in compiled.tools:
            item = next((candidate for candidate in tool_items if candidate.slug == slug), None)
            if item is None:
                continue
            module_globals: dict[str, Any] = {}
            exec(Path(item.module_path).read_text(encoding="utf-8"), module_globals)  # noqa: S102
            builder = module_globals.get(item.builder_name)
            if callable(builder):
                tools.append(builder())

        agent = create_deep_agent(
            model=_build_chat_model(compiled.provider_id, compiled.endpoint_url, compiled.model_name),
            tools=tools,
            system_prompt=compiled.system_prompt,
            subagents=[_materialize_subagent(subagent) for subagent in compiled.subagents],
            skills=compiled.skills or None,
            name=compiled.name,
        )
        prompt = str(run_input.get("prompt") or run_input.get("input") or "Run the configured agent.")
        response = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
        messages = response.get("messages", [])
        final_message = messages[-1].content if messages else ""
        return RuntimeExecutionResult(
            output={"summary": final_message, "messages": [getattr(message, "content", "") for message in messages]},
            events=[{"event_type": "message", "payload": {"text": str(final_message)}}],
        )


def compile_agent_version(
    version: AgentVersionRecord,
    *,
    skills_root: Path,
    tools_root: Path,
    app_defaults: dict[str, Any],
) -> CompiledAgent:
    provider_id, endpoint_url, model_name = _resolve_model_config(version.model, app_defaults)
    return CompiledAgent(
        name=version.name,
        provider_id=provider_id,
        endpoint_url=endpoint_url,
        model_name=model_name,
        system_prompt=version.instructions,
        runtime_params=version.runtime_params,
        skills=[_skill_source_path(item) for item in version.skills],
        tools=[item.slug for item in version.tools],
        subagents=[_compile_child(child, skills_root, tools_root, app_defaults) for child in version.children],
    )


def _compile_child(
    child: AgentNodePayload,
    skills_root: Path,
    tools_root: Path,
    app_defaults: dict[str, Any],
) -> dict[str, Any]:
    provider_id, endpoint_url, model_name = _resolve_model_config(child.model, app_defaults)
    return {
        "name": child.name,
        "description": f"Sub-agent: {child.name}",
        "system_prompt": child.instructions,
        "provider_id": provider_id,
        "endpoint_url": endpoint_url,
        "model": model_name,
        "skills": [_skill_source_path(item) for item in child.skills],
        "tools": [item.slug for item in child.tools],
    }


def _skill_source_path(item: SelectedCatalogItem) -> str:
    return f"/skills/{item.slug}/"


def _resolve_model_config(config: dict[str, Any], defaults: dict[str, Any]) -> tuple[str, str | None, str]:
    providers = [
        ProviderConfig.model_validate(item)
        for item in defaults.get("providers", [])
    ]
    provider_lookup = {provider.id: provider for provider in providers}
    provider_id = str(
        config.get("provider_id")
        or config.get("provider")
        or defaults.get("default_provider_id")
        or defaults.get("provider")
        or "openai"
    )
    model_name = str(config.get("model") or defaults.get("default_model") or defaults.get("model") or "gpt-4.1-mini")
    provider = provider_lookup.get(provider_id)
    endpoint_url = provider.endpoint_url if provider and provider.endpoint_url else None
    return provider_id, endpoint_url, model_name


def _build_chat_model(provider_id: str, endpoint_url: str | None, model_name: str):
    if endpoint_url:
        if ChatOpenAI is None:
            raise RuntimeError("langchain-openai is required for custom endpoint providers")
        return ChatOpenAI(
            model=model_name,
            base_url=endpoint_url,
            api_key=os.getenv("OPENAI_API_KEY", "not-needed"),
        )
    return f"{provider_id}:{model_name}"


def _materialize_subagent(subagent: dict[str, Any]) -> dict[str, Any]:
    materialized = dict(subagent)
    materialized["model"] = _build_chat_model(
        subagent["provider_id"],
        subagent.get("endpoint_url"),
        subagent["model"],
    )
    materialized.pop("provider_id", None)
    materialized.pop("endpoint_url", None)
    return materialized
