# SPDX-License-Identifier: MIT

"""Frontmatter preservation test.

A Markdown file with YAML frontmatter keeps the frontmatter byte-first
and receives the canonical html-block banner immediately below it, so
static-site generators can still parse collection metadata.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

InjectorRunner = Callable[..., subprocess.CompletedProcess[str]]


SOURCE_WITH_FRONTMATTER: str = (
    "---\n"
    "title: Sample Document\n"
    "tags: [test, fixture]\n"
    "---\n"
    "\n"
    "# Sample Document\n"
    "\n"
    "Body paragraph.\n"
)


def test_frontmatter_preserved_below_banner(
    tmp_path: Path,
    run_injector: InjectorRunner,
) -> None:
    """Frontmatter stays first; banner and H1 are preserved below."""
    target = tmp_path / "doc.md"
    target.write_text(SOURCE_WITH_FRONTMATTER, encoding="utf-8")

    result = run_injector("--mode", "fix-in-place", str(target))
    assert result.returncode == 0, f"fix-in-place failed: {result.stderr}"

    text = target.read_text(encoding="utf-8")
    assert text.startswith(SOURCE_WITH_FRONTMATTER.split("\n\n", 1)[0]), (
        "expected YAML frontmatter to remain byte-first"
    )
    assert "<!-- SPDX-License-Identifier: MIT -->" in text, (
        "expected html-form SPDX header below the frontmatter"
    )
    # Body content preserved.
    assert "# Sample Document" in text, "expected H1 preserved"
    assert "Body paragraph." in text, "expected body content preserved"
    lines = text.splitlines()
    assert lines[0] == "---", "frontmatter must remain line 1"
