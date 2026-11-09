# SPDX-License-Identifier: MIT

"""Only the known top-level entries are tracked at the repository root.

A scratch folder a test or a probe makes in the working directory (a
``tempfile.mkdtemp(dir=os.getcwd())`` call, say) would otherwise be committed
with whatever it holds. A new top-level entry is added to the list on purpose.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

#: Every file and folder tracked at the repository root.
EXPECTED = frozenset(
    {
        ".agents",
        ".claude-plugin",
        ".clusterfuzzlite",
        ".editorconfig",
        ".gitattributes",
        ".github",
        ".gitignore",
        ".gitleaks.toml",
        ".mailmap",
        ".markdownlint.json",
        ".npmignore",
        ".pre-commit-config.yaml",
        ".scorecard.yml",
        ".shellcheckrc",
        ".vscode",
        ".well-known",
        "AGENTS.md",
        "AUTHORS",
        "CHANGELOG.md",
        "CITATION.cff",
        "CLAUDE.md",
        "CODE_OF_CONDUCT.md",
        "CONTRIBUTING.md",
        "CONTRIBUTORS.md",
        "GEMINI.md",
        "GOVERNANCE.md",
        "LICENSE",
        "LICENSES",
        "MAINTAINERS.md",
        "Makefile",
        "PSScriptAnalyzerSettings.psd1",
        "QWEN.md",
        "README.md",
        "REUSE.toml",
        "ROADMAP.md",
        "SECURITY-INSIGHTS.yml",
        "SECURITY.md",
        "SUPPORT.md",
        "TRANSLATING.md",
        "assets",
        "bin",
        "commands",
        "evals",
        "examples",
        "gemini-extension.json",
        "package.json",
        "plugins",
        "pyproject.toml",
        "qwen-commands",
        "qwen-extension.json",
        "scripts",
        "site",
        "src",
        "tests",
        "tools",
        "vscode-extension",
    }
)


def _tracked_root_entries() -> set[str]:
    git = shutil.which("git")
    if git is None or not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    listed = subprocess.run(  # noqa: S603 - fixed arguments, resolved git
        [git, "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return {line.split("/", 1)[0] for line in listed.splitlines() if line}


def test_only_known_entries_are_tracked_at_the_root() -> None:
    unexpected = _tracked_root_entries() - EXPECTED

    assert not unexpected, (
        f"unexpected tracked entries at the repository root: {sorted(unexpected)}; "
        "remove a scratch folder, or add a deliberate entry to EXPECTED"
    )
