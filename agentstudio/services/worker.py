from __future__ import annotations

import socket
from pathlib import Path

from agentstudio.runtime import DeepAgentsExecutor, RuntimeExecutor, compile_agent_version
from agentstudio.services.agents import AgentService
from agentstudio.services.runs import RunService
from agentstudio.services.settings import SettingsService


class WorkerService:
    def __init__(
        self,
        *,
        database_path: Path,
        artifacts_dir: Path,
        skills_root: Path,
        tools_root: Path,
        executor: RuntimeExecutor | None = None,
    ) -> None:
        self.database_path = database_path
        self.artifacts_dir = artifacts_dir
        self.skills_root = skills_root
        self.tools_root = tools_root
        self.run_service = RunService(database_path, artifacts_dir)
        self.agent_service = AgentService(database_path)
        self.settings_service = SettingsService(database_path)
        self.executor = executor or DeepAgentsExecutor(tools_root)

    def process_next_run(self):
        lease_owner = f"worker@{socket.gethostname()}"
        run = self.run_service.claim_next_run(lease_owner)
        if run is None:
            return None
        try:
            version = self.agent_service.get_version(run.agent_version_id)
            defaults = self.settings_service.get_llm_defaults().model_dump()
            compiled = compile_agent_version(
                version,
                skills_root=self.skills_root,
                tools_root=self.tools_root,
                app_defaults=defaults,
            )
            execution = self.executor.execute(compiled, run.input)
            for event in execution.events:
                self.run_service.append_event(
                    run.id,
                    event["event_type"],
                    event.get("payload", {}),
                )
            for artifact in execution.artifacts:
                self.run_service.store_artifact(
                    run.id,
                    filename=artifact["filename"],
                    content=artifact["content"],
                    mime_type=artifact.get("mime_type", "text/plain"),
                )
            return self.run_service.complete_run(run.id, execution.output)
        except Exception as exc:
            return self.run_service.fail_run(run.id, str(exc))
