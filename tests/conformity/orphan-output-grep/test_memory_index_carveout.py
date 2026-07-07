# SPDX-License-Identifier: MIT

"""Regression test for the orphan-output-grep memory-index carve-out.

The auto-memory convention defines ``MEMORY.md`` as a frontmatter-free index
(one index line per memory, no per-file frontmatter). Its producer attribution
is structural --- it is the index the memory topic files point back to ---
so requiring a ``PROVENANCE_RE`` marker from the index itself is a category
error. ``MEMORY.md`` is carved out of the provenance requirement; the memory
topic files it indexes still carry their own frontmatter and are NOT carved out.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "orphan_output_grep.py"
)

# A memory-index body with no frontmatter, no `provenance:` field, and no
# `## Bindings` section --- exactly what the auto-memory convention produces.
_MEMORY_INDEX_BODY: Final[str] = (
    "# Memory Index\n\n- [a stable fact](topic-file.md) - one-line hook\n"
)


def _load_grep() -> ModuleType:
    """Load the orphan-output-grep module from the tree under test."""
    spec = importlib.util.spec_from_file_location(
        "orphan_output_grep_under_test", _GREP_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["orphan_output_grep_under_test"] = module
    spec.loader.exec_module(module)
    return module


def test_memory_index_basename_is_provenance_exempt() -> None:
    """A frontmatter-less MEMORY.md write is NOT flagged for absent provenance."""
    grep = _load_grep()
    path = Path.home() / ".claude" / "memory" / "MEMORY.md"

    result = grep.check(_MEMORY_INDEX_BODY, path)

    assert result.passed is True
    assert result.findings == []


def test_memory_topic_file_still_requires_provenance() -> None:
    """A sibling topic file (not the index) with no provenance IS still flagged."""
    grep = _load_grep()
    path = Path.home() / ".claude" / "memory" / "some-topic.md"

    result = grep.check(_MEMORY_INDEX_BODY, path)

    assert result.passed is False
    assert any(f.issue == "provenance absent" for f in result.findings)


def test_memory_index_basename_is_in_carveout_set() -> None:
    """The carve-out set names MEMORY.md explicitly (guards an accidental rename)."""
    grep = _load_grep()
    assert "MEMORY.md" in grep.MEMORY_INDEX_BASENAMES
