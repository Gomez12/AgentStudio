from __future__ import annotations

from dataclasses import dataclass, field
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml
from pydantic import BaseModel, Field


class SkillCatalogItem(BaseModel):
    slug: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    body: str
    path: str


class ToolCatalogItem(BaseModel):
    slug: str
    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    module_path: str
    builder_name: str


class CatalogScanResult(BaseModel):
    items: list[SkillCatalogItem | ToolCatalogItem]
    issues: list[str] = Field(default_factory=list)


def scan_skills(root: Path) -> CatalogScanResult:
    items: list[SkillCatalogItem] = []
    issues: list[str] = []
    if not root.exists():
        return CatalogScanResult(items=[], issues=[])

    for skill_file in sorted(root.rglob("SKILL.md")):
        rel_path = skill_file.relative_to(root)
        try:
            metadata, body = _parse_markdown_document(skill_file.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            issues.append(f"Failed to parse skill metadata for {rel_path.as_posix()}")
            continue

        slug = rel_path.parent.as_posix()
        items.append(
            SkillCatalogItem(
                slug=slug,
                name=str(metadata.get("name") or rel_path.parent.name),
                description=str(metadata.get("description") or ""),
                tags=_normalize_tags(metadata.get("tags")),
                body=body.strip(),
                path=str(skill_file),
            )
        )
    return CatalogScanResult(items=items, issues=issues)


def scan_tools(root: Path) -> CatalogScanResult:
    items: list[ToolCatalogItem] = []
    issues: list[str] = []
    if not root.exists():
        return CatalogScanResult(items=[], issues=[])

    for tool_file in sorted(root.rglob("*.py")):
        if tool_file.name == "__init__.py":
            continue
        try:
            module = _load_module(tool_file)
        except Exception as exc:  # pragma: no cover - import error path
            issues.append(f"Failed to import tool module {tool_file.name}: {exc}")
            continue

        metadata = getattr(module, "TOOL_METADATA", None)
        builder = getattr(module, "build_tool", None)
        if not isinstance(metadata, dict):
            issues.append(f"Tool module {tool_file.name} does not expose TOOL_METADATA")
            continue
        if not callable(builder):
            issues.append(f"Tool module {tool_file.name} does not expose a callable builder")
            continue

        items.append(
            ToolCatalogItem(
                slug=tool_file.stem,
                name=str(metadata.get("name") or tool_file.stem),
                description=str(metadata.get("description") or ""),
                input_schema=dict(metadata.get("input_schema") or {}),
                module_path=str(tool_file),
                builder_name="build_tool",
            )
        )
    return CatalogScanResult(items=items, issues=issues)


def _parse_markdown_document(content: str) -> tuple[dict[str, Any], str]:
    if not content.startswith("---\n"):
        return {}, content
    _, _, remainder = content.partition("---\n")
    frontmatter, separator, body = remainder.partition("\n---\n")
    if not separator:
        return {}, content
    parsed = yaml.safe_load(frontmatter) or {}
    if not isinstance(parsed, dict):
        raise yaml.YAMLError("Frontmatter must be a mapping")
    return parsed, body


def _normalize_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _load_module(path: Path) -> ModuleType:
    spec = spec_from_file_location(f"agentstudio_tool_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
