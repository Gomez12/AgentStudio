import { FormEvent, useEffect, useState } from "react";

import { api } from "./api";
import type {
  AgentExport,
  AgentNodePayload,
  AgentRecord,
  AgentVersionRecord,
  LLMSettings,
  ProviderConfig,
  RunEventRecord,
  RunRecord,
  ScheduleRecord,
  SelectedCatalogItem,
  SkillCatalogItem,
  ToolCatalogItem,
} from "./types";

type AgentFormState = {
  agentId: string | null;
  name: string;
  description: string;
  instructions: string;
  providerId: string;
  model: string;
  temperature: string;
  skillSlugs: string[];
  toolSlugs: string[];
  children: AgentNodePayload[];
};

const fallbackProvider: ProviderConfig = {
  id: "openai",
  label: "OpenAI",
  endpoint_url: "https://api.openai.com/v1",
  models: ["gpt-4.1-mini", "gpt-4.1"],
};

const fallbackSettings: LLMSettings = {
  default_provider_id: fallbackProvider.id,
  default_model: fallbackProvider.models[0],
  providers: [fallbackProvider],
};

const initialAgentForm: AgentFormState = {
  agentId: null,
  name: "",
  description: "",
  instructions: "",
  providerId: fallbackSettings.default_provider_id,
  model: fallbackSettings.default_model,
  temperature: "0.2",
  skillSlugs: [],
  toolSlugs: [],
  children: [],
};

const initialChild = (): AgentNodePayload => ({
  name: "",
  instructions: "",
  model: { provider_id: fallbackProvider.id, model: fallbackSettings.default_model },
  runtime_params: {},
  skills: [],
  tools: [],
});

export function App() {
  const [skills, setSkills] = useState<SkillCatalogItem[]>([]);
  const [tools, setTools] = useState<ToolCatalogItem[]>([]);
  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [events, setEvents] = useState<RunEventRecord[]>([]);
  const [schedules, setSchedules] = useState<ScheduleRecord[]>([]);
  const [settings, setSettings] = useState<LLMSettings>(fallbackSettings);
  const [form, setForm] = useState<AgentFormState>(initialAgentForm);
  const [providerDraft, setProviderDraft] = useState({ id: "", label: "", endpointUrl: "", models: "" });
  const [selectedAgent, setSelectedAgent] = useState<AgentRecord | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [exportJson, setExportJson] = useState("");
  const [importJson, setImportJson] = useState("");
  const [statusMessage, setStatusMessage] = useState("Loading studio data...");
  const [scheduleExpression, setScheduleExpression] = useState("15m");

  async function loadDashboard() {
    const [skillResponse, toolResponse, agentResponse, runResponse, scheduleResponse, settingsResponse] =
      await Promise.all([
        api.getSkills(),
        api.getTools(),
        api.getAgents(),
        api.getRuns(),
        api.getSchedules(),
        api.getLlmSettings(),
      ]);

    setSkills(skillResponse.items);
    setTools(toolResponse.items);
    setAgents(agentResponse);
    setRuns(runResponse);
    setSchedules(scheduleResponse);
    setSettings(settingsResponse);
    setForm((current) => applyProviderDefaults(current, settingsResponse));
    setStatusMessage("Studio data is current.");
  }

  useEffect(() => {
    void loadDashboard().catch((error: Error) => setStatusMessage(error.message));
  }, []);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      void Promise.all([api.getRuns(), api.getSchedules()])
        .then(([runResponse, scheduleResponse]) => {
          setRuns(runResponse);
          setSchedules(scheduleResponse);
        })
        .catch(() => undefined);
    }, 5000);
    return () => window.clearInterval(intervalId);
  }, []);

  useEffect(() => {
    if (!selectedRunId) {
      setEvents([]);
      return;
    }
    void api
      .getRunEvents(selectedRunId)
      .then(setEvents)
      .catch((error: Error) => setStatusMessage(error.message));
  }, [selectedRunId]);

  async function handleSelectAgent(agentId: string) {
    try {
      const agent = await api.getAgent(agentId);
      const providerId = String(agent.model.provider_id ?? agent.model.provider ?? settings.default_provider_id);
      const nextForm = applyProviderDefaults(
        {
          agentId: agent.id,
          name: agent.name,
          description: agent.description,
          instructions: agent.instructions,
          providerId,
          model: String(agent.model.model ?? ""),
          temperature: String(agent.runtime_params.temperature ?? 0.2),
          skillSlugs: agent.skills.map((item) => item.slug),
          toolSlugs: agent.tools.map((item) => item.slug),
          children: agent.children.length > 0 ? agent.children : [],
        },
        settings
      );
      setSelectedAgent(agent);
      setForm(nextForm);
      setStatusMessage(`Loaded agent ${agent.name}.`);
    } catch (error) {
      setStatusMessage((error as Error).message);
    }
  }

  async function handleSaveAgent(event: FormEvent) {
    event.preventDefault();
    const payload = {
      agent_id: form.agentId,
      name: form.name,
      description: form.description,
      instructions: form.instructions,
      model: { provider_id: form.providerId, model: form.model },
      runtime_params: { temperature: Number(form.temperature) },
      skills: form.skillSlugs.map((slug) => toSelectedSkill(slug, skills)),
      tools: form.toolSlugs.map((slug) => toSelectedTool(slug, tools)),
      children: form.children,
    };

    try {
      const saved = await api.saveAgent(payload);
      await loadDashboard();
      await handleSelectAgent(saved.id);
      setStatusMessage(`Saved draft ${saved.name}.`);
    } catch (error) {
      setStatusMessage((error as Error).message);
    }
  }

  async function handlePublish() {
    if (!selectedAgent) {
      setStatusMessage("Select or save an agent first.");
      return;
    }
    try {
      const version = (await api.publishAgent(selectedAgent.id)) as AgentVersionRecord;
      await handleSelectAgent(selectedAgent.id);
      setStatusMessage(`Published version ${version.version_number} for ${selectedAgent.name}.`);
    } catch (error) {
      setStatusMessage((error as Error).message);
    }
  }

  async function handleRun(versionId: string) {
    try {
      const run = await api.enqueueRun(versionId, { prompt: form.instructions || "Run this agent." });
      await loadDashboard();
      setSelectedRunId(run.id);
      setStatusMessage(`Queued run ${run.id.slice(0, 8)}.`);
    } catch (error) {
      setStatusMessage((error as Error).message);
    }
  }

  async function handleExport() {
    if (!selectedAgent) {
      setStatusMessage("Select an agent before exporting.");
      return;
    }
    try {
      const payload = await api.exportAgent(selectedAgent.id);
      setExportJson(JSON.stringify(payload, null, 2));
      setStatusMessage(`Exported ${selectedAgent.name}.`);
    } catch (error) {
      setStatusMessage((error as Error).message);
    }
  }

  async function handleImport() {
    try {
      const parsed = JSON.parse(importJson) as AgentExport;
      const imported = await api.importAgent(parsed);
      await loadDashboard();
      setStatusMessage(`Imported ${imported.name}.`);
    } catch (error) {
      setStatusMessage((error as Error).message);
    }
  }

  async function handleSaveSettings(event: FormEvent) {
    event.preventDefault();
    try {
      const payload = {
        ...settings,
        providers: settings.providers.map(normalizeProvider),
      };
      const saved = await api.updateLlmSettings(payload);
      setSettings(saved);
      setForm((current) => applyProviderDefaults(current, saved));
      setStatusMessage("Saved provider registry and defaults.");
    } catch (error) {
      setStatusMessage((error as Error).message);
    }
  }

  function handleProviderSelection(providerId: string) {
    const models = availableModels(settings.providers, providerId);
    setForm({
      ...form,
      providerId,
      model: models.includes(form.model) ? form.model : models[0] ?? "",
    });
  }

  function handleAddProvider() {
    const provider = normalizeProvider({
      id: providerDraft.id,
      label: providerDraft.label,
      endpoint_url: providerDraft.endpointUrl,
      models: providerDraft.models.split(","),
    });
    if (!provider.id || provider.models.length === 0) {
      setStatusMessage("Provider id en minstens een model zijn verplicht.");
      return;
    }
    const nextProviders = [...settings.providers.filter((item) => item.id !== provider.id), provider];
    const nextSettings = {
      ...settings,
      providers: nextProviders,
      default_provider_id:
        settings.default_provider_id && nextProviders.some((item) => item.id === settings.default_provider_id)
          ? settings.default_provider_id
          : provider.id,
      default_model:
        settings.default_provider_id === provider.id
          ? provider.models[0]
          : settings.default_model || provider.models[0],
    };
    setSettings(nextSettings);
    setProviderDraft({ id: "", label: "", endpointUrl: "", models: "" });
    setForm((current) => applyProviderDefaults(current, nextSettings));
  }

  async function handleCreateSchedule() {
    const versionId = selectedAgent?.versions?.[0]?.id;
    if (!versionId) {
      setStatusMessage("Publish an agent version before creating a schedule.");
      return;
    }
    try {
      await api.createSchedule({
        agent_version_id: versionId,
        schedule_type: "interval",
        expression: scheduleExpression,
        status: "active",
      });
      const refreshed = await api.getSchedules();
      setSchedules(refreshed);
      setStatusMessage(`Created schedule ${scheduleExpression}.`);
    } catch (error) {
      setStatusMessage((error as Error).message);
    }
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Agent repository + runtime</p>
          <h1>Agent Studio</h1>
          <p className="hero-copy">
            Define versioned deepagents, combine skills and tools, schedule runs, and inspect full execution history.
          </p>
        </div>
        <aside className="status-card">
          <h2>Studio status</h2>
          <p>{statusMessage}</p>
          <p>
            {agents.length} agents, {runs.length} runs, {schedules.length} schedules
          </p>
        </aside>
      </header>

      <main className="dashboard-grid">
        <section className="panel">
          <h2>Skill catalog</h2>
          <ul className="catalog-list">
            {skills.map((skill) => (
              <li key={skill.slug}>
                <strong>{skill.name}</strong>
                <span>{skill.description}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="panel">
          <h2>Tool catalog</h2>
          <ul className="catalog-list">
            {tools.map((tool) => (
              <li key={tool.slug}>
                <strong>{tool.name}</strong>
                <span>{tool.description}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="panel builder-panel">
          <div className="panel-header">
            <h2>Agent builder</h2>
            <button type="button" onClick={() => setForm(applyProviderDefaults(initialAgentForm, settings))}>
              New agent
            </button>
          </div>
          <form onSubmit={handleSaveAgent} className="form-grid">
            <label>
              Name
              <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
            </label>
            <label>
              Description
              <input
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
              />
            </label>
            <label className="full-width">
              Instructions
              <textarea
                rows={5}
                value={form.instructions}
                onChange={(event) => setForm({ ...form, instructions: event.target.value })}
              />
            </label>
            <label>
              Provider
              <select value={form.providerId} onChange={(event) => handleProviderSelection(event.target.value)}>
                {settings.providers.map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Model
              <select value={form.model} onChange={(event) => setForm({ ...form, model: event.target.value })}>
                {availableModels(settings.providers, form.providerId).map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Temperature
              <input
                value={form.temperature}
                onChange={(event) => setForm({ ...form, temperature: event.target.value })}
              />
            </label>
            <label>
              Skills
              <select
                multiple
                value={form.skillSlugs}
                onChange={(event) =>
                  setForm({
                    ...form,
                    skillSlugs: Array.from(event.target.selectedOptions).map((option) => option.value),
                  })
                }
              >
                {skills.map((skill) => (
                  <option key={skill.slug} value={skill.slug}>
                    {skill.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Tools
              <select
                multiple
                value={form.toolSlugs}
                onChange={(event) =>
                  setForm({
                    ...form,
                    toolSlugs: Array.from(event.target.selectedOptions).map((option) => option.value),
                  })
                }
              >
                {tools.map((tool) => (
                  <option key={tool.slug} value={tool.slug}>
                    {tool.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="full-width child-editor">
              <div className="panel-header">
                <h3>Child agents</h3>
                <button
                  type="button"
                  onClick={() => setForm({ ...form, children: [...form.children, initialChild()] })}
                >
                  Add child
                </button>
              </div>
              {form.children.length === 0 ? <p>No child agents configured.</p> : null}
              {form.children.map((child, index) => (
                <div key={`${child.name}-${index}`} className="child-card">
                  <input
                    placeholder="Child name"
                    value={child.name}
                    onChange={(event) => {
                      const nextChildren = [...form.children];
                      nextChildren[index] = { ...child, name: event.target.value };
                      setForm({ ...form, children: nextChildren });
                    }}
                  />
                  <textarea
                    rows={3}
                    placeholder="Child instructions"
                    value={child.instructions}
                    onChange={(event) => {
                      const nextChildren = [...form.children];
                      nextChildren[index] = { ...child, instructions: event.target.value };
                      setForm({ ...form, children: nextChildren });
                    }}
                  />
                </div>
              ))}
            </div>
            <div className="full-width actions">
              <button type="submit">Save draft</button>
              <button type="button" onClick={handlePublish}>
                Publish version
              </button>
              <button type="button" onClick={handleExport}>
                Export agent
              </button>
            </div>
          </form>
        </section>

        <section className="panel">
          <h2>Agent library</h2>
          <ul className="list-panel">
            {agents.map((agent) => (
              <li key={agent.id}>
                <button type="button" onClick={() => void handleSelectAgent(agent.id)}>
                  <strong>{agent.name}</strong>
                  <span>{agent.description}</span>
                </button>
              </li>
            ))}
          </ul>
          {selectedAgent ? (
            <div className="detail-block">
              <h3>Version history</h3>
              <ul className="version-list">
                {selectedAgent.versions?.map((version) => (
                  <li key={version.id}>
                    <div>
                      <strong>v{version.version_number}</strong>
                      <span>{new Date(version.created_at).toLocaleString()}</span>
                    </div>
                    <button type="button" onClick={() => void handleRun(version.id)}>
                      Run
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>

        <section className="panel">
          <h2>Run history</h2>
          <ul className="list-panel">
            {runs.map((run) => (
              <li key={run.id}>
                <button type="button" onClick={() => setSelectedRunId(run.id)}>
                  <strong>{run.status}</strong>
                  <span>{run.trigger_type}</span>
                </button>
              </li>
            ))}
          </ul>
          {selectedRunId ? (
            <div className="detail-block">
              <h3>Event timeline</h3>
              <ul className="event-list">
                {events.map((event) => (
                  <li key={event.id}>
                    <strong>{event.event_type}</strong>
                    <code>{JSON.stringify(event.payload)}</code>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>

        <section className="panel">
          <h2>Schedules</h2>
          <div className="inline-form">
            <input value={scheduleExpression} onChange={(event) => setScheduleExpression(event.target.value)} />
            <button type="button" onClick={() => void handleCreateSchedule()}>
              Create interval schedule
            </button>
          </div>
          <ul className="list-panel">
            {schedules.map((schedule) => (
              <li key={schedule.id}>
                <strong>{schedule.expression}</strong>
                <span>{schedule.next_run_at ?? "inactive"}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="panel">
          <h2>Provider registry</h2>
          <ul className="list-panel">
            {settings.providers.map((provider) => (
              <li key={provider.id}>
                <strong>{provider.label}</strong>
                <span>{provider.endpoint_url || "Built-in provider"}</span>
                <code>{provider.models.join(", ")}</code>
              </li>
            ))}
          </ul>
          <div className="form-grid compact">
            <label>
              Provider id
              <input
                value={providerDraft.id}
                onChange={(event) => setProviderDraft({ ...providerDraft, id: event.target.value })}
              />
            </label>
            <label>
              Label
              <input
                value={providerDraft.label}
                onChange={(event) => setProviderDraft({ ...providerDraft, label: event.target.value })}
              />
            </label>
            <label>
              Endpoint URL
              <input
                value={providerDraft.endpointUrl}
                onChange={(event) => setProviderDraft({ ...providerDraft, endpointUrl: event.target.value })}
              />
            </label>
            <label>
              Models
              <input
                value={providerDraft.models}
                onChange={(event) => setProviderDraft({ ...providerDraft, models: event.target.value })}
                placeholder="gpt-4.1-mini, qwen2.5-14b"
              />
            </label>
            <button type="button" onClick={handleAddProvider}>
              Add / update provider
            </button>
          </div>
        </section>

        <section className="panel">
          <h2>LLM defaults</h2>
          <form onSubmit={handleSaveSettings} className="form-grid compact">
            <label>
              Default provider
              <select
                value={settings.default_provider_id}
                onChange={(event) => {
                  const providerId = event.target.value;
                  const models = availableModels(settings.providers, providerId);
                  setSettings({
                    ...settings,
                    default_provider_id: providerId,
                    default_model: models[0] ?? settings.default_model,
                  });
                }}
              >
                {settings.providers.map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Default model
              <select
                value={settings.default_model}
                onChange={(event) => setSettings({ ...settings, default_model: event.target.value })}
              >
                {availableModels(settings.providers, settings.default_provider_id).map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit">Save defaults</button>
          </form>
        </section>

        <section className="panel">
          <h2>Import / export</h2>
          <label>
            Export JSON
            <textarea rows={8} value={exportJson} readOnly />
          </label>
          <label>
            Import JSON
            <textarea rows={8} value={importJson} onChange={(event) => setImportJson(event.target.value)} />
          </label>
          <button type="button" onClick={() => void handleImport()}>
            Import agent pack
          </button>
        </section>
      </main>
    </div>
  );
}

function availableModels(providers: ProviderConfig[], providerId: string): string[] {
  return providers.find((provider) => provider.id === providerId)?.models ?? [];
}

function applyProviderDefaults(current: AgentFormState, settings: LLMSettings): AgentFormState {
  const providerId = current.providerId || settings.default_provider_id;
  const models = availableModels(settings.providers, providerId);
  return {
    ...current,
    providerId,
    model: current.model || models[0] || settings.default_model,
  };
}

function normalizeProvider(provider: {
  id: string;
  label: string;
  endpoint_url: string;
  models: string[];
}): ProviderConfig {
  return {
    id: provider.id.trim(),
    label: provider.label.trim() || provider.id.trim(),
    endpoint_url: provider.endpoint_url.trim(),
    models: provider.models.map((item) => item.trim()).filter(Boolean),
  };
}

function toSelectedSkill(slug: string, skills: SkillCatalogItem[]): SelectedCatalogItem {
  const skill = skills.find((item) => item.slug === slug);
  return {
    slug,
    name: skill?.name ?? slug,
    description: skill?.description ?? "",
    snapshot: {
      slug,
      name: skill?.name ?? slug,
      description: skill?.description ?? "",
      body: skill?.body ?? "",
      tags: skill?.tags ?? [],
    },
  };
}

function toSelectedTool(slug: string, tools: ToolCatalogItem[]): SelectedCatalogItem {
  const tool = tools.find((item) => item.slug === slug);
  return {
    slug,
    name: tool?.name ?? slug,
    description: tool?.description ?? "",
    snapshot: {
      slug,
      name: tool?.name ?? slug,
      description: tool?.description ?? "",
      input_schema: tool?.input_schema ?? {},
    },
  };
}
