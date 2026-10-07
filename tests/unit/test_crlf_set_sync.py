# SPDX-License-Identifier: MIT

"""Drift guard: three repo-root files name the same CRLF extension set.

``.gitattributes`` decides which files Git checks out with CRLF
(``text eol=crlf``). ``.editorconfig`` tells editors to save those files with
CRLF, and the ``mixed-line-ending --fix=lf`` hook in ``.pre-commit-config.yaml``
must exclude them, or it rewrites every CRLF checkout to LF. The three sets
drifted once: ``.editorconfig`` added ``*.psd1`` and ``*.psm1`` while the other
two did not, so an editor saved ``PSScriptAnalyzerSettings.psd1`` as CRLF and
the hook reverted it. This guard fails when any one of the three changes alone.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final

import yaml

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

# ``*.ext  text eol=crlf`` in .gitattributes.
_GITATTRIBUTES_CRLF_RE: Final[re.Pattern[str]] = re.compile(
    r"^\*\.(\w+)\s+.*\beol=crlf\b", re.MULTILINE
)
# ``*.ext`` patterns anywhere in .gitattributes, used to probe the exclude regex.
_GITATTRIBUTES_EXT_RE: Final[re.Pattern[str]] = re.compile(
    r"^\*\.(\w+)\s", re.MULTILINE
)
# ``[*.ext]`` or ``[*.{a,b}]`` editorconfig section headers.
_EDITORCONFIG_SECTION_RE: Final[re.Pattern[str]] = re.compile(
    r"^\[\*\.(?:\{([\w,]+)\}|(\w+))\]$"
)


def _gitattributes_crlf() -> set[str]:
    text = (_REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    return set(_GITATTRIBUTES_CRLF_RE.findall(text))


def _editorconfig_crlf() -> set[str]:
    crlf: set[str] = set()
    section: list[str] = []
    for raw in (_REPO_ROOT / ".editorconfig").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("["):
            match = _EDITORCONFIG_SECTION_RE.match(line)
            section = (match.group(1) or match.group(2)).split(",") if match else []
        elif line.replace(" ", "") == "end_of_line=crlf":
            crlf.update(section)
    return crlf


def _mixed_line_ending_hook() -> dict[str, Any]:
    config = yaml.safe_load(
        (_REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    )
    for repo in config["repos"]:
        for hook in repo["hooks"]:
            if hook["id"] == "mixed-line-ending":
                return dict(hook)
    raise AssertionError("no mixed-line-ending hook in .pre-commit-config.yaml")


def test_editorconfig_crlf_set_matches_gitattributes() -> None:
    """Editors save with CRLF exactly the files Git checks out with CRLF."""
    gitattributes = _gitattributes_crlf()
    editorconfig = _editorconfig_crlf()
    assert gitattributes, ".gitattributes pins no extension to eol=crlf"
    assert editorconfig == gitattributes, (
        f"CRLF sets differ: .gitattributes={sorted(gitattributes)}, "
        f".editorconfig={sorted(editorconfig)}"
    )


def test_mixed_line_ending_hook_excludes_exactly_the_crlf_set() -> None:
    """The LF fixer skips every CRLF extension and nothing else."""
    hook = _mixed_line_ending_hook()
    assert "--fix=lf" in hook.get("args", [])
    exclude = re.compile(hook.get("exclude", "^$"))
    crlf = _gitattributes_crlf()
    text = (_REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    probes = (
        set(_GITATTRIBUTES_EXT_RE.findall(text))
        | _editorconfig_crlf()
        | {"psd1", "psm1"}
    )
    excluded = {ext for ext in probes if exclude.search(f"dir/file.{ext}")}
    assert excluded == crlf, (
        f"mixed-line-ending exclude {hook.get('exclude')!r} skips {sorted(excluded)}; "
        f".gitattributes CRLF set is {sorted(crlf)}"
    )
