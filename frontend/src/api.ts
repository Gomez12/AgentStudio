import type {
  AgentExport,
  AgentRecord,
  CatalogResponse,
  LLMSettings,
  RunEventRecord,
  RunRecord,
  ScheduleRecord,
  SkillCatalogItem,
  ToolCatalogItem,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`Request failed for ${path}: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getSkills: () => request<CatalogResponse<SkillCatalogItem>>("/catalog/skills"),
  getTools: () => request<CatalogResponse<ToolCatalogItem>>("/catalog/tools"),
  getAgents: () => request<AgentRecord[]>("/agents"),
  getAgent: (agentId: string) => request<AgentRecord>(`/agents/${agentId}`),
  saveAgent: (payload: Record<string, unknown>) =>
    request<AgentRecord>("/agents", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  publishAgent: (agentId: string) =>
    request(`/agents/${agentId}/versions`, {
      method: "POST",
    }),
  getRuns: () => request<RunRecord[]>("/runs"),
  getRunEvents: (runId: string) => request<RunEventRecord[]>(`/runs/${runId}/events`),
  getRunArtifacts: (runId: string) => request(`/runs/${runId}/artifacts`),
  enqueueRun: (versionId: string, input: Record<string, unknown>) =>
    request<RunRecord>(`/agent-versions/${versionId}/run`, {
      method: "POST",
      body: JSON.stringify({ input, trigger_type: "manual", trigger_payload: {} }),
    }),
  getSchedules: () => request<ScheduleRecord[]>("/schedules"),
  createSchedule: (payload: Record<string, unknown>) =>
    request<ScheduleRecord>("/schedules", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateLlmSettings: (payload: LLMSettings) =>
    request<LLMSettings>("/settings/llm", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  getLlmSettings: () => request<LLMSettings>("/settings/llm"),
  exportAgent: (agentId: string) => request<AgentExport>(`/exports/agents/${agentId}`),
  importAgent: (payload: AgentExport) =>
    request<AgentRecord>("/imports/agents", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
