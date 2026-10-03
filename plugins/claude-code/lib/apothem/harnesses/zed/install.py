# SPDX-License-Identifier: MIT

"""Install logic for the zed harness adapter.

Materializes the apothem Zed rules surface into the operator-supplied
project root. Zed reads project instructions from the first file it finds
in a fixed priority list, and ``.rules`` is first in that list (per
https://zed.dev/docs/ai/instructions, retrieved 2026-10-02). Zed now names
``AGENTS.md`` its primary instruction file and keeps project ``.rules`` as a
supported compatibility file. The global ``~/.config/zed/AGENTS.md`` target
is excluded because Apothem targets the current project surface.

Because only the first file is read, a new ``.rules`` hides any
lower-priority file (``AGENTS.md``, ``CLAUDE.md``,
``.github/copilot-instructions.md`` and the rest of the list) from Zed. The
install never edits those files; it reports the hidden file in an
``instruction_shadowing`` warning whenever ``.rules`` carries nothing but the
Apothem managed block and the hidden file holds operator text, so the
operator can copy the instructions they need into ``.rules`` outside the
block.

The propagation contract is declared in the canonical manifest at
``src/apothem/lib/propagation-manifest.yaml`` under the ``zed`` key
(a single ``sentinel_merge`` operation targeting
``${PROJECT_ROOT}/.rules``) and applied by the shared driver at
``apothem.harnesses._shared.install_driver``, which backs up any
pre-existing ``.rules`` before replace. The ``${PROJECT_ROOT}``
placeholder is substituted with the operator-supplied ``--project
<path>`` value the CLI threads through; absence of ``--project`` is
rejected upstream at ``apothem.cli._materialize`` via the
``requires_project`` opt-in.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from apothem.harnesses._shared.install_driver import (
    MaterializationResult,
    MaterializationRun,
)
from apothem.harnesses._shared.wrapper_factories import (
    make_project_scope_install,
    make_project_scope_plan,
)
from apothem.lib.harness_materializer import remove_managed_block

# Manifest harness key for this adapter.
_HARNESS_NAME: str = "zed"

# The project instruction files Zed checks after ``.rules``, in its documented
# priority order (https://zed.dev/docs/ai/instructions). Zed reads only the
# first file present.
LOWER_PRIORITY_INSTRUCTION_FILES: tuple[str, ...] = (
    ".cursorrules",
    ".windsurfrules",
    ".clinerules",
    ".github/copilot-instructions.md",
    "AGENT.md",
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
)

_install_rules = make_project_scope_install(
    _HARNESS_NAME,
    error_message="zed adapter requires --project <path>; CLI must thread it through",
)

plan = make_project_scope_plan(_HARNESS_NAME)


def _has_operator_text(path: Path) -> bool:
    """Return True when *path* is a file with text outside the Apothem block.

    A file that holds only an Apothem managed block (another adapter's anchor,
    such as the Kimi Code ``AGENTS.md``) carries no operator instructions, so
    hiding it from Zed loses nothing.
    """
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return bool(remove_managed_block(text).strip())


def _shadowing_warning(project: Path) -> MaterializationResult | None:
    """Return the warning for lower-priority instruction files ``.rules`` hides.

    Returns ``None`` when no lower-priority file in *project* holds operator
    text. The message names the file Zed read before the install (the first such
    file in Zed's list) and every other such file the list contains.
    """
    hidden = [
        name
        for name in LOWER_PRIORITY_INSTRUCTION_FILES
        if _has_operator_text(project / name)
    ]
    if not hidden:
        return None
    first = hidden[0]
    others = hidden[1:]
    also = f" ({', '.join(others)} also present)" if others else ""
    message = (
        "Zed reads only the first project instruction file it finds, and "
        f".rules comes first. Before this install Zed read {first}{also}; it now "
        f"reads the Apothem .rules instead. To keep {first} in Zed, copy its "
        "instructions into .rules outside the Apothem managed block."
    )
    return MaterializationResult(
        outcome="warning",
        operation="instruction_shadowing",
        path=str(project / ".rules"),
        message=message,
        detail={"hidden": ", ".join(hidden)},
    )


def install(
    output_path: Path,
    profile: dict[str, Any],
    *,
    project: Path | None = None,
) -> MaterializationRun:
    """Materialize ``.rules`` and warn when it hides another instruction file.

    Runs the shared project-scope install, then appends an
    ``instruction_shadowing`` warning when ``.rules`` holds only the Apothem
    managed block (before or after the write) and a lower-priority instruction
    file exists. An operator-authored ``.rules`` already outranks those files,
    so the install changes nothing about which file Zed reads and no warning is
    added. Raises ``ValueError`` when *project* is ``None``.
    """
    operator_rules = project is not None and _has_operator_text(project / ".rules")
    run = _install_rules(output_path, profile, project=project)
    if project is None or operator_rules:
        return run
    warning = _shadowing_warning(project)
    if warning is None:
        return run
    return replace(run, results=(*run.results, warning))
