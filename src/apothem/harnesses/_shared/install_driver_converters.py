# SPDX-License-Identifier: MIT

"""Harness-native agent/command/skill text converters (pure render helpers)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final

from apothem.lib.frontmatter import (
    field_value,
    field_value_in_text,
    split_frontmatter,
)

from .install_driver_layout import (
    REFERENCE_NOTE_HEADING,
    harness_layout,
    reference_note,
)


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
    """Return the generated skill note for installed reference paths.

    The note names, for each cited corpus directory the harness installs
    (``rules/``, ``templates/``, ``schemas/``, ``hooks/``, ``conformity/``),
    the directory its manifest entry targets under *install_root*, so every
    path it names is one the install writes.
    """
    return reference_note(harness_layout(harness_name, install_root))


def _generated_skill_text(
    source_path: Path,
    *,
    harness_name: str,
    install_root: Path,
) -> str:
    """Render a command Markdown file as a native skill entrypoint."""
    text = source_path.read_text(encoding="utf-8")
    if REFERENCE_NOTE_HEADING in text:
        return text
    reference_note_text = _installed_reference_note(harness_name, install_root)
    return text.rstrip() + "\n" + reference_note_text


#: Codex policy file written beside a user-only skill's ``SKILL.md``. Codex
#: ignores ``disable-model-invocation``; it reads
#: ``policy.allow_implicit_invocation`` (default ``true``) from
#: ``agents/openai.yaml``, and ``false`` still allows explicit ``$skill``
#: invocation (https://developers.openai.com/codex/skills, retrieved 2026-10-02).
_CODEX_POLICY_PATH: Final[str] = "agents/openai.yaml"
_CODEX_USER_ONLY_POLICY: Final[str] = (
    "# Written by Apothem: the skill sets disable-model-invocation: true.\n"
    "policy:\n"
    "  allow_implicit_invocation: false\n"
)


#: Source skill keys renamed to the spelling Claude Code reads. Claude Code
#: reads ``user-invocable`` and silently ignores unknown keys such as the
#: source corpus's ``userInvocable`` (https://code.claude.com/docs/en/skills,
#: retrieved 2026-10-02). Only key names are translated; values are kept.
CLAUDE_CODE_SKILL_KEY_RENAMES: Final[dict[str, str]] = {
    "userInvocable": "user-invocable",
}


def _rename_frontmatter_keys(text: str, renames: dict[str, str]) -> str:
    """Return *text* with top-level frontmatter keys renamed per *renames*.

    Only unindented ``key:`` lines inside the byte-0 frontmatter block change;
    the body, nested keys and values are untouched.
    """
    parts = split_frontmatter(text)
    if parts is None:
        return text
    block, rest = parts
    lines = block.split("\n")
    for index, line in enumerate(lines):
        key, sep, value = line.partition(":")
        if sep and key in renames:
            lines[index] = f"{renames[key]}{sep}{value}"
    return "\n".join(lines) + rest


def _source_disables_model_invocation(skill_text: str) -> bool:
    """Return True when *skill_text* sets ``disable-model-invocation: true``."""
    value = field_value_in_text(skill_text, "disable-model-invocation") or ""
    return value.strip().lower() == "true"


def _native_skill_emission(
    harness_name: str, skill_text: str
) -> tuple[str, dict[str, str]]:
    """Return a harness's ``SKILL.md`` text and its sidecar files.

    Sidecars map a skill-directory-relative POSIX path to file text. Harnesses
    without a skill-level translation get the text unchanged and no sidecars:

    - ``claude_code``: source key names renamed to Claude Code's spelling
      (:data:`CLAUDE_CODE_SKILL_KEY_RENAMES`).
    - ``codex``: ``agents/openai.yaml`` disabling implicit invocation for a
      skill whose source sets ``disable-model-invocation: true``.
    """
    if harness_name == "claude_code":
        return _rename_frontmatter_keys(skill_text, CLAUDE_CODE_SKILL_KEY_RENAMES), {}
    if harness_name == "codex" and _source_disables_model_invocation(skill_text):
        return skill_text, {_CODEX_POLICY_PATH: _CODEX_USER_ONLY_POLICY}
    return skill_text, {}


def claude_code_skill_text(skill_text: str) -> str:
    """Return a source ``SKILL.md`` in the form the Claude Code plugin ships."""
    return _native_skill_emission("claude_code", skill_text)[0]


def _command_skill_files(
    source_path: Path, *, harness_name: str, install_root: Path
) -> dict[str, bytes]:
    """Return the files of a command rendered as a native skill directory."""
    text, sidecars = _native_skill_emission(
        harness_name,
        _generated_skill_text(
            source_path, harness_name=harness_name, install_root=install_root
        ),
    )
    files = {name: body.encode("utf-8") for name, body in sidecars.items()}
    files["SKILL.md"] = text.encode("utf-8")
    return files


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


#: Tools whose grant lets an agent author files. An agent granted none of them
#: (after its deny list) is the read-only kind its description advertises.
_FILE_WRITE_TOOLS: Final[frozenset[str]] = frozenset(
    {"write", "edit", "multiedit", "notebookedit"}
)


def _tool_key(name: str) -> str:
    """Return the case- and separator-insensitive key of a tool name."""
    return name.split("(", 1)[0].strip().lower().replace("-", "").replace("_", "")


def _agent_is_read_only(source_path: Path) -> bool:
    """Return True when the agent's effective tool grant authors no files.

    With an explicit ``tools`` grant, the grant minus ``disallowedTools`` must
    hold no file-writing tool. Without one the agent inherits every tool, so
    it is read-only only when ``disallowedTools`` denies both Write and Edit.
    """
    granted = {_tool_key(t) for t in _agent_scalar_list(source_path, "tools")}
    denied = {_tool_key(t) for t in _agent_scalar_list(source_path, "disallowedTools")}
    if not granted:
        return {"write", "edit"} <= denied
    return not ((granted - denied) & _FILE_WRITE_TOOLS)


def _codex_agent_text(source_path: Path) -> str:
    """Convert a Markdown agent definition into Codex's TOML agent format.

    Codex custom agents take ``name``, ``description`` and
    ``developer_instructions`` plus any ``config.toml`` key; omitted keys
    inherit from the parent session
    (https://developers.openai.com/codex/subagents, retrieved 2026-10-02). A
    read-only agent gets ``sandbox_mode = "read-only"``, Codex's native write
    restriction. Model and reasoning effort are left to inherit. Codex has no
    tool allowlist or turn-limit key, so ``tools`` and ``maxTurns`` do not map
    (declared in the codex ``conversion_losses``).
    """
    name = _agent_name(source_path)
    description = _agent_description(source_path)
    body = _agent_body(source_path).strip()
    sandbox = 'sandbox_mode = "read-only"\n' if _agent_is_read_only(source_path) else ""
    return (
        f"name = {_toml_string(name)}\n"
        f"description = {_toml_string(description)}\n"
        f"{sandbox}"
        "developer_instructions = "
        f"{_toml_multiline_string(body)}\n"
    )


#: Claude-Code-style tool names to Gemini CLI built-in tool names
#: (https://geminicli.com/docs/reference/tools, retrieved 2026-10-02).
_GEMINI_TOOL_MAP: Final[dict[str, tuple[str, ...]]] = {
    "read": ("read_file", "read_many_files", "list_directory"),
    "glob": ("glob",),
    "grep": ("grep_search",),
    "bash": ("run_shell_command",),
    "write": ("write_file",),
    "edit": ("replace",),
    "multiedit": ("replace",),
    "websearch": ("google_web_search",),
    "webfetch": ("web_fetch",),
    "todowrite": ("write_todos",),
}


def _gemini_tool_names(source_path: Path) -> list[str] | None:
    """Return the Gemini ``tools`` allowlist, or ``None`` to inherit all tools.

    The source grant minus its deny list, mapped to Gemini names. A tool with
    no Gemini equivalent is left out rather than widened to a wildcard.
    """
    granted = [_tool_key(t) for t in _agent_scalar_list(source_path, "tools")]
    if not granted:
        return None
    denied = {_tool_key(t) for t in _agent_scalar_list(source_path, "disallowedTools")}
    names: list[str] = []
    for key in granted:
        if key in denied:
            continue
        for native in _GEMINI_TOOL_MAP.get(key, ()):
            if native not in names:
                names.append(native)
    return names


def _gemini_agent_text(source_path: Path) -> str:
    """Normalize a Markdown agent definition for Gemini CLI subagents.

    Gemini subagents accept ``tools`` (an allowlist; omitted means every tool)
    and ``max_turns`` (https://geminicli.com/docs/core/subagents, retrieved
    2026-10-02), so the source grant and turn limit carry over natively.
    """
    name = (field_value(source_path, "name") or source_path.stem).strip().lower()
    description = _agent_description(source_path)
    body = _agent_body(source_path).strip()
    frontmatter = (
        f"---\nname: {_yaml_scalar(name)}\n"
        f"description: {_yaml_scalar(description)}\n"
        "kind: local\n"
    )
    tools = _gemini_tool_names(source_path)
    if tools is not None:
        frontmatter += _yaml_list("tools", tools) if tools else "tools: []\n"
    max_turns = (field_value(source_path, "maxTurns") or "").strip()
    if max_turns.isdigit():
        frontmatter += f"max_turns: {int(max_turns)}\n"
    return f"{frontmatter}---\n\n{body}\n"


_READ_ONLY_LEAD = re.compile(r"^Read-only\s+(\w)")
_READ_ONLY_SENTENCE = re.compile(r"\bRead-only:\s+(\w)")
_READ_ONLY_WORD = re.compile(r"\bread-only\s+", re.IGNORECASE)


def _drop_read_only_claim(description: str) -> str:
    """Return *description* without its read-only capability claim.

    Used where the harness has no verified native restriction to back the
    claim. Behavioural statements ("never fixes") stay; only the read-only
    label goes, with the following word re-capitalised where it starts a
    sentence.
    """
    text = _READ_ONLY_LEAD.sub(lambda m: m.group(1).upper(), description)
    text = _READ_ONLY_SENTENCE.sub(lambda m: m.group(1).upper(), text)
    return _READ_ONLY_WORD.sub("", text)


def _antigravity_agent_text(source_path: Path) -> str:
    """Normalize a Markdown agent definition for Antigravity subagents.

    Antigravity subagents require ``name`` and ``description``
    (https://antigravity.google/docs/subagents, retrieved 2026-10-02). Their
    ``tools`` list takes Antigravity tool names, and an unmapped name can hang
    the subagent, so no list is emitted; without a native restriction the
    description drops its read-only claim.
    """
    name = (field_value(source_path, "name") or source_path.stem).strip().lower()
    description = _agent_description(source_path)
    if _agent_is_read_only(source_path):
        description = _drop_read_only_claim(description)
    body = _agent_body(source_path).strip()
    return (
        f"---\nname: {_yaml_scalar(name)}\n"
        f"description: {_yaml_scalar(description)}\n---\n\n{body}\n"
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


def _antigravity_rule_text(source_path: Path) -> str:
    """Convert an Apothem rule into an Antigravity rule file.

    Antigravity discards any file in a ``rules/`` directory whose frontmatter
    lacks a valid ``trigger`` (``always_on`` | ``model_decision`` | ``glob`` |
    ``manual``); ``model_decision`` needs ``description`` and ``glob`` needs
    ``globs`` (https://antigravity.google/docs/rules, retrieved 2026-10-02).
    The source activation maps one-to-one: ``alwaysApply: true`` becomes
    ``always_on``, a non-empty ``pathFilter`` becomes ``glob`` with the same
    comma-separated patterns, and any other rule is ``model_decision``. Only
    the documented keys are emitted; the body follows unchanged.
    """
    description = field_value(source_path, "description") or (
        f"Apothem {source_path.stem} rule."
    )
    always = (field_value(source_path, "alwaysApply") or "").lower() == "true"
    path_filter = (field_value(source_path, "pathFilter") or "").strip()
    lines = ["---"]
    if always:
        lines.append("trigger: always_on")
    elif path_filter:
        lines.append("trigger: glob")
    else:
        lines.append("trigger: model_decision")
    lines.append(f"description: {_yaml_scalar(description)}")
    if not always and path_filter:
        lines.append(f"globs: {_yaml_scalar(path_filter)}")
    lines.append("---")
    body = _agent_body(source_path).strip()
    return "\n".join(lines) + f"\n\n{body}\n"


def _gemini_command_text(source_path: Path) -> str:
    """Convert a Markdown command definition into Gemini CLI TOML.

    ``description`` maps to the TOML ``description``; the prompt is the body
    with the source frontmatter and the leading license comment stripped, the
    same body the Markdown-command converter emits, so no metadata reaches the
    model as instructions. What happens to each other source key is declared
    in the gemini_cli ``conversion_losses``.
    """
    description = field_value(source_path, "description") or (
        f"Run the {source_path.stem} Apothem workflow."
    )
    prompt = _strip_leading_html_comment(_agent_body(source_path)).strip() + "\n"
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
