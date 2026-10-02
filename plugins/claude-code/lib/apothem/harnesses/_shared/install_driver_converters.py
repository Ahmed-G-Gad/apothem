# SPDX-License-Identifier: MIT

"""Harness-native agent/command/skill text converters (pure render helpers)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from apothem.lib.frontmatter import field_value


def _strip_markdown_frontmatter(text: str) -> str:
    """Return Markdown body text with leading YAML frontmatter removed."""
    if not text.startswith("---\n"):
        return text
    marker = "\n---"
    end = text.find(marker, 4)
    if end == -1:
        return text
    remainder = text[end + len(marker) :]
    return remainder.lstrip("\r\n")


def _strip_leading_html_comment(text: str) -> str:
    """Return Markdown text without the leading authorship comment block."""
    stripped = text.lstrip()
    if not stripped.startswith("<!--"):
        return text
    comment_start = len(text) - len(stripped)
    comment_end = text.find("-->", comment_start)
    if comment_end == -1:
        return text
    return text[comment_end + len("-->") :].lstrip("\r\n")


def _toml_string(value: str) -> str:
    """Return *value* encoded as a TOML basic string."""
    return json.dumps(value, ensure_ascii=False)


def _toml_multiline_string(value: str) -> str:
    """Return *value* encoded as a TOML multiline basic string.

    Backslashes are escaped first so arbitrary content — for example a
    Markdown-escaped table pipe ``\\|`` — never forms an invalid TOML escape
    sequence; the ``\"\"\"`` delimiter is then escaped so it cannot close the
    string early. Order matters: the delimiter escaping introduces its own
    backslashes, so it must run after the content backslashes are doubled.
    """
    escaped = value.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return f'"""\n{escaped.rstrip()}\n"""'


def _installed_reference_note(harness_name: str, install_root: Path) -> str:
    """Return the generated skill note for installed reference paths."""
    if harness_name == "codex":
        codex_root = install_root
        support_root = Path.home() / ".config" / "apothem"
        return (
            "\n## Installed Reference Paths\n\n"
            "When this skill is installed by Apothem, resolve repository-style "
            f"references such as `rules/...` and `templates/...` under "
            f"`{support_root}`, and `hooks/...` under `{codex_root}` unless a "
            "project-local file with the same relative path exists.\n"
        )
    if harness_name == "antigravity":
        plugin_root = install_root / "antigravity-cli" / "plugins" / "apothem"
        support_root = plugin_root / "apothem"
        return (
            "\n## Installed Reference Paths\n\n"
            "When this skill is installed by Apothem, resolve repository-style "
            f"references such as `rules/...` under `{plugin_root}`, "
            f"`templates/...` and `hooks/...` under `{support_root}`, unless a "
            "project-local file with the same relative path exists.\n"
        )
    if harness_name == "claude_code":
        support_root = install_root / "apothem"
        return (
            "\n## Installed Reference Paths\n\n"
            "When this skill is installed by Apothem, resolve repository-style "
            f"references such as `rules/...` under `{install_root}`, "
            f"`templates/...` and `hooks/...` under `{support_root}`, unless a "
            "project-local file with the same relative path exists.\n"
        )
    if harness_name in {"hermes", "open_claw"}:
        support_root = install_root / "apothem"
        return (
            "\n## Installed Reference Paths\n\n"
            "When this skill is installed by Apothem, resolve repository-style "
            f"references such as `rules/...`, `templates/...`, and `hooks/...` "
            f"under `{support_root}` unless a project-local file with the same "
            "relative path exists.\n"
        )
    return (
        "\n## Installed Reference Paths\n\n"
        "When this skill is installed by Apothem, resolve repository-style "
        f"references such as `rules/...`, `templates/...`, and `hooks/...` "
        f"under `{install_root}` unless a project-local file with the same "
        "relative path exists.\n"
    )


def _generated_skill_text(
    source_path: Path,
    *,
    harness_name: str,
    install_root: Path,
) -> str:
    """Render a command Markdown file as a native skill entrypoint."""
    text = source_path.read_text(encoding="utf-8")
    reference_note = _installed_reference_note(harness_name, install_root)
    if "## Installed Reference Paths" in text:
        return text
    return text.rstrip() + "\n" + reference_note


def _agent_body(source_path: Path) -> str:
    """Return a Markdown agent's body text without YAML frontmatter."""
    return _strip_markdown_frontmatter(source_path.read_text(encoding="utf-8"))


def _agent_name(source_path: Path) -> str:
    """Return a portable agent name from frontmatter or filename."""
    name = field_value(source_path, "name") or source_path.stem
    return name.strip().lower().replace("-", "_")


def _agent_description(source_path: Path) -> str:
    """Return the agent description from frontmatter or a generated fallback."""
    return field_value(source_path, "description") or f"{source_path.stem} agent"


def _agent_scalar_list(source_path: Path, field_name: str) -> list[str]:
    """Return a comma-separated scalar frontmatter field as clean items."""
    value = field_value(source_path, field_name)
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _agent_tool_names(
    source_path: Path,
    field_name: str,
    mapping: dict[str, str],
) -> list[str]:
    """Return harness-native tool names from an Apothem agent tool field."""
    names: list[str] = []
    for item in _agent_scalar_list(source_path, field_name):
        key = item.lower().replace("-", "").replace("_", "")
        mapped = mapping.get(key)
        if mapped and mapped not in names:
            names.append(mapped)
    return names


def _yaml_scalar(value: str) -> str:
    """Return a conservative YAML double-quoted scalar."""
    return json.dumps(value, ensure_ascii=False)


def _yaml_list(name: str, values: list[str]) -> str:
    """Return a small YAML list block, or an empty string for no values."""
    if not values:
        return ""
    items = "\n".join(f"  - {_yaml_scalar(value)}" for value in values)
    return f"{name}:\n{items}\n"


def _codex_agent_text(source_path: Path) -> str:
    """Convert a Markdown agent definition into Codex's TOML agent format."""
    name = _agent_name(source_path)
    description = _agent_description(source_path)
    body = _agent_body(source_path).strip()
    return (
        f"name = {_toml_string(name)}\n"
        f"description = {_toml_string(description)}\n"
        'model_reasoning_effort = "medium"\n'
        "developer_instructions = "
        f"{_toml_multiline_string(body)}\n"
    )


def _gemini_agent_text(source_path: Path) -> str:
    """Normalize a Markdown agent definition for Gemini CLI subagents."""
    name = (field_value(source_path, "name") or source_path.stem).strip().lower()
    description = _agent_description(source_path)
    body = _agent_body(source_path).strip()
    return (
        f"---\nname: {_yaml_scalar(name)}\n"
        f"description: {_yaml_scalar(description)}\n"
        f"kind: local\n---\n\n{body}\n"
    )


_QWEN_TOOL_MAP: dict[str, str] = {
    "bash": "run_shell_command",
    "edit": "edit",
    "glob": "glob",
    "grep": "grep_search",
    "read": "read_file",
    "todowrite": "todo_write",
    "write": "write_file",
}


def _qwen_approval_mode(source_path: Path) -> str | None:
    """Return a Qwen-native approval mode from portable agent frontmatter."""
    raw = field_value(source_path, "approvalMode") or field_value(
        source_path, "permissionMode"
    )
    if not raw:
        return None
    key = raw.strip().lower().replace("_", "-")
    mapping = {
        "ask": "default",
        "default": "default",
        "plan": "plan",
        "auto": "auto-edit",
        "auto-edit": "auto-edit",
        "autoedit": "auto-edit",
        "accept-edits": "auto-edit",
        "yolo": "yolo",
    }
    return mapping.get(key, "default")


def _qwen_agent_text(source_path: Path) -> str:
    """Normalize a Markdown agent definition for Qwen Code subagents."""
    name = (field_value(source_path, "name") or source_path.stem).strip().lower()
    description = _agent_description(source_path)
    body = _agent_body(source_path).strip()
    tools = _agent_tool_names(source_path, "tools", _QWEN_TOOL_MAP)
    disallowed = _agent_tool_names(source_path, "disallowedTools", _QWEN_TOOL_MAP)
    approval_mode = _qwen_approval_mode(source_path)
    frontmatter = (
        "---\n"
        f"name: {_yaml_scalar(name)}\n"
        f"description: {_yaml_scalar(description)}\n"
        'model: "inherit"\n'
    )
    if approval_mode:
        frontmatter += f"approvalMode: {_yaml_scalar(approval_mode)}\n"
    frontmatter += _yaml_list("tools", tools)
    frontmatter += _yaml_list("disallowedTools", disallowed)
    return f"{frontmatter}---\n\n{body}\n"


_OPENCODE_PERMISSION_MAP: dict[str, str] = {
    "bash": "bash",
    "edit": "edit",
    "glob": "glob",
    "grep": "grep",
    "read": "read",
    "todowrite": "todowrite",
    "write": "edit",
}


def _opencode_permission_lines(source_path: Path) -> str:
    """Return OpenCode permission YAML from Apothem agent tool metadata."""
    permissions: dict[str, str] = {}
    for key in _agent_tool_names(source_path, "tools", _OPENCODE_PERMISSION_MAP):
        permissions[key] = "allow"
    for key in _agent_tool_names(
        source_path,
        "disallowedTools",
        _OPENCODE_PERMISSION_MAP,
    ):
        permissions[key] = "deny"
    if not permissions:
        return ""
    lines = ["permission:"]
    for key in sorted(permissions):
        lines.append(f"  {key}: {permissions[key]}")
    return "\n".join(lines) + "\n"


def _opencode_agent_text(source_path: Path) -> str:
    """Normalize a Markdown agent definition for OpenCode subagents."""
    description = _agent_description(source_path)
    body = _agent_body(source_path).strip()
    permissions = _opencode_permission_lines(source_path)
    return (
        f"---\ndescription: {_yaml_scalar(description)}\nmode: subagent\n"
        f"{permissions}---\n\n{body}\n"
    )


def _gemini_command_text(source_path: Path) -> str:
    """Convert a Markdown command definition into Gemini CLI TOML."""
    description = field_value(source_path, "description") or (
        f"Run the {source_path.stem} Apothem workflow."
    )
    prompt = source_path.read_text(encoding="utf-8")
    return (
        f"description = {_toml_string(description)}\n\n"
        f"prompt = {_toml_multiline_string(prompt)}\n"
    )


def _native_markdown_command_text(source_path: Path) -> str:
    """Convert an Apothem command to a native Markdown slash-command prompt."""
    description = field_value(source_path, "description") or (
        f"Run the {source_path.stem} Apothem workflow."
    )
    body = _strip_leading_html_comment(_agent_body(source_path)).strip()
    body = re.sub(r"\{\{\s*args\s*\}\}", "$ARGUMENTS", body)
    return f"---\ndescription: {_yaml_scalar(description)}\n---\n\n{body}\n"


def _claude_rule_text(source_path: Path) -> str:
    """Render a rule for ``~/.claude/rules/`` with Claude Code's native scoping.

    Claude Code loads every rule file at launch unless its frontmatter carries
    ``paths:``, the only rule field it reads
    (https://code.claude.com/docs/en/memory, retrieved 2026-10-02). The corpus
    marks a path-scoped rule with the harness-neutral ``pathFilter`` key, a
    comma-separated glob list, so this adds the equivalent ``paths:`` list just
    before the closing delimiter. An always-on rule (empty ``pathFilter``) is
    returned unchanged, and the body is never touched.
    """
    text = source_path.read_text(encoding="utf-8")
    path_filter = (field_value(source_path, "pathFilter") or "").strip()
    if not path_filter or not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    if end < 0:
        return text
    globs = [item.strip() for item in path_filter.split(",") if item.strip()]
    paths = _yaml_list("paths", globs)
    return text[: end + 1] + paths + text[end + 1 :]
