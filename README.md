# Agent Studio

Self-hostable studio for defining, versioning, scheduling, and running `deepagents` with a FastAPI backend, React SPA, SQLite persistence, filesystem-based skills/tools, and artifact-backed run history.

The studio now includes a provider registry where you can store OpenAI-compatible providers as `endpoint_url + model list`, pick defaults, and attach saved provider/model combinations to agents.

## Structure

- `agentstudio/`: backend API, services, runtime compiler, worker and scheduler
- `frontend/`: React SPA for catalog browsing, agent building, run history, schedules, and import/export
- `skills/`: selectable `SKILL.md` sources
- `tools/`: selectable Python tool modules

## Run

Backend:

```bash
uv sync --dev
uv run python main.py api
```

Worker:

```bash
uv run python main.py worker
```

Scheduler:

```bash
uv run python main.py scheduler
```

Frontend:

```bash
cd frontend
npm install
npm run build
```

The API serves `frontend/dist` automatically when it exists. By default the app uses:

- database: `var/agentstudio.db`
- artifacts: `var/artifacts`
- skills: `skills/`
- tools: `tools/`

Override these with `AGENTSTUDIO_*` environment variables.

## Verify

Backend:

```bash
uv run python -m pytest
```

Frontend:

```bash
cd frontend
npm test
npm run build
```
