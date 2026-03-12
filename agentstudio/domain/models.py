from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SelectedCatalogItem(BaseModel):
    slug: str
    name: str
    description: str
    snapshot: dict[str, Any] = Field(default_factory=dict)


class AgentNodePayload(BaseModel):
    name: str
    instructions: str
    model: dict[str, Any] = Field(default_factory=dict)
    runtime_params: dict[str, Any] = Field(default_factory=dict)
    skills: list[SelectedCatalogItem] = Field(default_factory=list)
    tools: list[SelectedCatalogItem] = Field(default_factory=list)


class AgentDraftPayload(BaseModel):
    agent_id: str | None = None
    name: str
    description: str
    instructions: str
    model: dict[str, Any] = Field(default_factory=dict)
    runtime_params: dict[str, Any] = Field(default_factory=dict)
    skills: list[SelectedCatalogItem] = Field(default_factory=list)
    tools: list[SelectedCatalogItem] = Field(default_factory=list)
    children: list[AgentNodePayload] = Field(default_factory=list)


class AgentRecord(AgentDraftPayload):
    id: str
    created_at: datetime
    updated_at: datetime


class AgentVersionRecord(BaseModel):
    id: str
    agent_id: str
    version_number: int
    name: str
    description: str
    instructions: str
    model: dict[str, Any] = Field(default_factory=dict)
    runtime_params: dict[str, Any] = Field(default_factory=dict)
    skills: list[SelectedCatalogItem] = Field(default_factory=list)
    tools: list[SelectedCatalogItem] = Field(default_factory=list)
    children: list[AgentNodePayload] = Field(default_factory=list)
    created_at: datetime


class ProviderConfig(BaseModel):
    id: str
    label: str
    endpoint_url: str = ""
    models: list[str] = Field(default_factory=list)


class LLMSettings(BaseModel):
    default_provider_id: str = "openai"
    default_model: str = "gpt-4.1-mini"
    providers: list[ProviderConfig] = Field(
        default_factory=lambda: [
            ProviderConfig(
                id="openai",
                label="OpenAI",
                endpoint_url="https://api.openai.com/v1",
                models=["gpt-4.1-mini", "gpt-4.1"],
            )
        ]
    )


class RunCreatePayload(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)
    trigger_type: str = "manual"
    trigger_payload: dict[str, Any] = Field(default_factory=dict)


class RunRecord(BaseModel):
    id: str
    agent_version_id: str
    status: str
    trigger_type: str
    trigger_payload: dict[str, Any] = Field(default_factory=dict)
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RunEventRecord(BaseModel):
    id: str
    run_id: str
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ArtifactRecord(BaseModel):
    id: str
    run_id: str
    event_id: str | None = None
    relative_path: str
    mime_type: str
    size_bytes: int
    created_at: datetime


class ScheduleCreatePayload(BaseModel):
    agent_version_id: str
    schedule_type: str
    expression: str
    status: str = "active"


class ScheduleUpdatePayload(BaseModel):
    status: str | None = None
    expression: str | None = None


class ScheduleRecord(BaseModel):
    id: str
    agent_version_id: str
    status: str
    schedule_type: str
    expression: str
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AgentExport(BaseModel):
    agent: AgentRecord
    versions: list[AgentVersionRecord] = Field(default_factory=list)
