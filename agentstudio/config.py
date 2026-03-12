from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    database_path: Path
    artifacts_dir: Path
    skills_root: Path
    tools_root: Path
    frontend_dist: Path
    host: str
    port: int


def load_config(base_dir: Path | None = None) -> AppConfig:
    root = base_dir or Path.cwd()
    return AppConfig(
        database_path=Path(os.getenv("AGENTSTUDIO_DATABASE", root / "var" / "agentstudio.db")),
        artifacts_dir=Path(os.getenv("AGENTSTUDIO_ARTIFACTS_DIR", root / "var" / "artifacts")),
        skills_root=Path(os.getenv("AGENTSTUDIO_SKILLS_DIR", root / "skills")),
        tools_root=Path(os.getenv("AGENTSTUDIO_TOOLS_DIR", root / "tools")),
        frontend_dist=Path(os.getenv("AGENTSTUDIO_FRONTEND_DIST", root / "frontend" / "dist")),
        host=os.getenv("AGENTSTUDIO_HOST", "127.0.0.1"),
        port=int(os.getenv("AGENTSTUDIO_PORT", "8000")),
    )
