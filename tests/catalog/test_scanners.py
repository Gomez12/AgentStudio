from pathlib import Path

from agentstudio.catalog import scan_skills, scan_tools


def test_scan_skills_reads_frontmatter_and_body(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    writer = skills_dir / "writer"
    writer.mkdir(parents=True)
    (writer / "SKILL.md").write_text(
        """---
name: writer
description: Draft clear copy
tags:
  - content
  - editing
---
# Writer

Help write concise text.
""",
        encoding="utf-8",
    )

    broken = skills_dir / "broken"
    broken.mkdir(parents=True)
    (broken / "SKILL.md").write_text(
        """---
name: broken
description: [not valid yaml
---
""",
        encoding="utf-8",
    )

    result = scan_skills(skills_dir)

    assert [item.slug for item in result.items] == ["writer"]
    skill = result.items[0]
    assert skill.name == "writer"
    assert skill.description == "Draft clear copy"
    assert skill.tags == ["content", "editing"]
    assert "Help write concise text." in skill.body
    assert result.issues == [
        "Failed to parse skill metadata for broken/SKILL.md"
    ]


def test_scan_tools_loads_valid_modules_and_reports_invalid_ones(tmp_path: Path) -> None:
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    (tools_dir / "search_tool.py").write_text(
        """
TOOL_METADATA = {
    "name": "search",
    "description": "Search external sources",
    "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
}

def build_tool():
    return {"callable": "search"}
""".strip(),
        encoding="utf-8",
    )
    (tools_dir / "broken_tool.py").write_text(
        """
TOOL_METADATA = {
    "name": "broken",
    "description": "Missing builder",
}
""".strip(),
        encoding="utf-8",
    )

    result = scan_tools(tools_dir)

    assert [item.slug for item in result.items] == ["search_tool"]
    tool = result.items[0]
    assert tool.name == "search"
    assert tool.description == "Search external sources"
    assert tool.module_path.endswith("search_tool.py")
    assert result.issues == [
        "Tool module broken_tool.py does not expose a callable builder"
    ]
