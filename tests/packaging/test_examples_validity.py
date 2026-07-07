# SPDX-License-Identifier: MIT

"""Gate every artifact under ``examples/`` for parse / render / syntax validity.

The ``examples/`` tree ships copy-ready demonstration artifacts (harness config
JSON, cohort Markdown with YAML frontmatter, and a POSIX hook script). Example
rot — a malformed JSON file, a frontmatter-bearing cohort file missing its
required keys, or a shell script that no longer parses — is a real defect that
this module catches with a failing test.

Files are discovered dynamically by globbing ``examples/**/*`` so newly added
examples are covered automatically; no hardcoded file list is maintained here.

Coverage categories:

- ``json``           — every ``*.json`` parses via :func:`json.loads`.
- ``md-frontmatter`` — every ``*.md`` whose first line is ``---`` has parseable
  YAML frontmatter; cohort files (agent / skill / command) additionally carry
  their required keys. Plain Markdown (no frontmatter) must be non-empty UTF-8.
- ``sh-syntax``      — every ``*.sh`` passes ``bash -n`` when a usable bash is
  available (on Windows a git-bash; the WSL launcher is rejected), and degrades
  gracefully (skip with reason) on hosts without one so the gate runs unchanged
  on bare Windows runners.
- ``parity``         — cross-OS disposition for executable examples: a shell
  example either ships a ``.ps1`` sibling or carries a recorded, reasoned
  no-parity exception.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Final

import pytest
import yaml

from tests._shared.bash_resolver import SKIP_REASON, find_test_bash

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
EXAMPLES_ROOT: Final[Path] = REPO_ROOT / "examples"

# Required YAML-frontmatter keys per cohort file kind, keyed by filename. Read
# from the live examples (sample-agent.md / SKILL.md / sample-command.md): each
# carries exactly ``name`` + ``description``.
COHORT_REQUIRED_KEYS: Final[dict[str, frozenset[str]]] = {
    "sample-agent.md": frozenset({"name", "description"}),
    "SKILL.md": frozenset({"name", "description"}),
    "sample-command.md": frozenset({"name", "description"}),
}

# Executable examples whose Windows counterpart is documented rather than
# shipped as a sibling script. Each entry records the concrete reason the
# no-parity exception is the encoded reality, audited against the example's
# own README. Removing an entry forces the parity test to demand a sibling.
NO_PARITY_EXCEPTIONS: Final[dict[str, str]] = {
    "examples/minimal-hook/sample-hook.sh": (
        "The minimal-hook example demonstrates the POSIX hook shape (the README "
        '"What it demonstrates" section frames it as a POSIX-shell hook with '
        "set -euo pipefail). The Windows hook surface is reached through the "
        "harness adapter, which materializes the hook into each harness's native "
        "settings location; the README documents that wiring rather than shipping "
        "a parallel .ps1 example. No .ps1 sibling is required."
    ),
}


def _relpath(path: Path) -> str:
    """POSIX-style path relative to the repo root, for stable test IDs."""
    return path.relative_to(REPO_ROOT).as_posix()


def _discover(suffix: str) -> list[Path]:
    return sorted(p for p in EXAMPLES_ROOT.rglob(f"*{suffix}") if p.is_file())


JSON_FILES: Final[list[Path]] = _discover(".json")
MD_FILES: Final[list[Path]] = _discover(".md")
SH_FILES: Final[list[Path]] = _discover(".sh")


def test_examples_root_exists() -> None:
    """The examples tree exists and is non-empty (guards against silent miss)."""
    assert EXAMPLES_ROOT.is_dir(), f"missing examples tree at {EXAMPLES_ROOT}"
    assert any(EXAMPLES_ROOT.rglob("*")), "examples tree is empty"


def test_discovery_found_each_category() -> None:
    """Each asserted category discovered at least one file (glob sanity)."""
    assert JSON_FILES, "no *.json examples discovered"
    assert MD_FILES, "no *.md examples discovered"
    assert SH_FILES, "no *.sh examples discovered"


@pytest.mark.parametrize("json_file", JSON_FILES, ids=_relpath)
def test_json_example_parses(json_file: Path) -> None:
    """Every JSON example parses as valid JSON."""
    text = json_file.read_text(encoding="utf-8")
    try:
        json.loads(text)
    except json.JSONDecodeError as exc:  # pragma: no cover - failure path
        pytest.fail(f"{_relpath(json_file)} is not valid JSON: {exc}")


@pytest.mark.parametrize("md_file", MD_FILES, ids=_relpath)
def test_markdown_example_valid(md_file: Path) -> None:
    """Markdown examples are readable UTF-8; frontmatter parses with required keys."""
    text = md_file.read_text(encoding="utf-8")
    assert text.strip(), f"{_relpath(md_file)} is empty"

    if not text.startswith("---"):
        # Plain Markdown (README / CLAUDE.md): readable and non-empty suffices.
        return

    # Frontmatter-bearing: extract the block between the first two `---` fences.
    parts = text.split("---", 2)
    assert len(parts) >= 3, (
        f"{_relpath(md_file)} opens with '---' but has no closing frontmatter fence"
    )
    front_raw = parts[1]
    try:
        front = yaml.safe_load(front_raw)
    except yaml.YAMLError as exc:  # pragma: no cover - failure path
        pytest.fail(f"{_relpath(md_file)} has unparseable YAML frontmatter: {exc}")

    assert isinstance(front, dict), (
        f"{_relpath(md_file)} frontmatter is not a mapping (got {type(front).__name__})"
    )

    required = COHORT_REQUIRED_KEYS.get(md_file.name)
    if required is not None:
        missing = required - front.keys()
        assert not missing, (
            f"{_relpath(md_file)} cohort frontmatter missing required keys: "
            f"{sorted(missing)}"
        )
        for key in required:
            value = front[key]
            assert isinstance(value, str), (
                f"{_relpath(md_file)} frontmatter key '{key}' must be a string"
            )
            assert value.strip(), (
                f"{_relpath(md_file)} frontmatter key '{key}' must be non-empty"
            )


@pytest.mark.parametrize("sh_file", SH_FILES, ids=_relpath)
def test_shell_example_syntax(sh_file: Path) -> None:
    """Every shell example passes ``bash -n``; skips with reason without usable bash."""
    bash = find_test_bash()
    if bash is None:
        pytest.skip(SKIP_REASON)
    result = subprocess.run(
        [bash, "-n", str(sh_file)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"{_relpath(sh_file)} failed `bash -n`: {result.stderr.strip()}"
    )


@pytest.mark.parametrize("sh_file", SH_FILES, ids=_relpath)
def test_shell_example_cross_os_parity(sh_file: Path) -> None:
    """Shell examples ship a .ps1 sibling OR carry a recorded no-parity exception."""
    sibling = sh_file.with_suffix(".ps1")
    if sibling.is_file():
        return
    reason = NO_PARITY_EXCEPTIONS.get(_relpath(sh_file))
    no_sibling_msg = (
        f"{_relpath(sh_file)} has no .ps1 sibling and no recorded no-parity "
        "exception; either add a Windows sibling or record an evidence-backed "
        "exception in NO_PARITY_EXCEPTIONS with a concrete reason"
    )
    assert reason is not None, no_sibling_msg
    assert reason.strip(), no_sibling_msg
