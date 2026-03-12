export type SkillCatalogItem = {
  slug: string;
  name: string;
  description: string;
  tags: string[];
  body: string;
  path: string;
};

export type ToolCatalogItem = {
  slug: string;
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  module_path: string;
  builder_name: string;
};

export type CatalogResponse<T> = {
  items: T[];
  issues: string[];
};

export type SelectedCatalogItem = {
  slug: string;
  name: string;
  description: string;
  snapshot: Record<string, unknown>;
};

export type AgentNodePayload = {
  name: string;
  instructions: string;
  model: Record<string, unknown>;
  runtime_params: Record<string, unknown>;
  skills: SelectedCatalogItem[];
  tools: SelectedCatalogItem[];
};

export type AgentRecord = {
  id: string;
  name: string;
  description: string;
  instructions: string;
  model: Record<string, unknown>;
  runtime_params: Record<string, unknown>;
  skills: SelectedCatalogItem[];
  tools: SelectedCatalogItem[];
  children: AgentNodePayload[];
  created_at: string;
  updated_at: string;
  versions?: AgentVersionRecord[];
};

export type AgentVersionRecord = {
  id: string;
  agent_id: string;
  version_number: number;
  name: string;
  description: string;
  instructions: string;
  model: Record<string, unknown>;
  runtime_params: Record<string, unknown>;
  skills: SelectedCatalogItem[];
  tools: SelectedCatalogItem[];
  children: AgentNodePayload[];
  created_at: string;
};

export type RunRecord = {
  id: string;
  agent_version_id: string;
  status: string;
  trigger_type: string;
  trigger_payload: Record<string, unknown>;
  input: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type RunEventRecord = {
  id: string;
  run_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type ArtifactRecord = {
  id: string;
  run_id: string;
  event_id: string | null;
  relative_path: string;
  mime_type: string;
  size_bytes: number;
  created_at: string;
};

export type ScheduleRecord = {
  id: string;
  agent_version_id: string;
  status: string;
  schedule_type: string;
  expression: string;
  next_run_at: string | null;
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ProviderConfig = {
  id: string;
  label: string;
  endpoint_url: string;
  models: string[];
};

export type LLMSettings = {
  default_provider_id: string;
  default_model: string;
  providers: ProviderConfig[];
};

export type AgentExport = {
  agent: AgentRecord;
  versions: AgentVersionRecord[];
};
