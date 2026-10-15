# SPDX-License-Identifier: MIT

"""MDX variant of the authorship-header injector.

An ``.mdx`` file receives the MDX comment form ``{/* ... */}``, not the HTML
comment form. With YAML frontmatter the line goes directly after the closing
fence and is followed by one blank line; without frontmatter it is line 1.
A bare SPDX line with no blank line after it is normalized, never duplicated.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

InjectorRunner = Callable[..., subprocess.CompletedProcess[str]]

MDX_LINE: str = "{/* SPDX-License-Identifier: MIT */}"
FRONTMATTER: str = '---\ntitle: "Sample"\n---\n'
BODY: str = "# Sample\n\nBody paragraph.\n"


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_mdx_with_frontmatter_places_line_after_closing_fence(
    tmp_path: Path,
    run_injector: InjectorRunner,
) -> None:
    """Frontmatter stays first; the MDX line follows it, then one blank line."""
    target = _write(tmp_path / "page.mdx", FRONTMATTER + BODY)

    result = run_injector("--mode", "fix-in-place", str(target))

    assert result.returncode == 0, result.stderr
    assert target.read_text(encoding="utf-8") == (
        FRONTMATTER + MDX_LINE + "\n\n" + BODY
    )


def test_mdx_keeps_blank_line_between_frontmatter_and_line(
    tmp_path: Path,
    run_injector: InjectorRunner,
) -> None:
    """A blank line after the frontmatter stays above the MDX line."""
    target = _write(tmp_path / "page.mdx", FRONTMATTER + "\n" + BODY)

    result = run_injector("--mode", "fix-in-place", str(target))

    assert result.returncode == 0, result.stderr
    assert target.read_text(encoding="utf-8") == (
        FRONTMATTER + "\n" + MDX_LINE + "\n\n" + BODY
    )


def test_mdx_without_frontmatter_puts_line_at_line_one(
    tmp_path: Path,
    run_injector: InjectorRunner,
) -> None:
    """With no frontmatter the MDX line is the first line of the file."""
    target = _write(tmp_path / "plain.mdx", BODY)

    result = run_injector("--mode", "fix-in-place", str(target))

    assert result.returncode == 0, result.stderr
    assert target.read_text(encoding="utf-8") == MDX_LINE + "\n\n" + BODY


def test_mdx_fix_is_idempotent_and_passes_check(
    tmp_path: Path,
    run_injector: InjectorRunner,
) -> None:
    """A second fix run changes nothing, and check mode then exits 0."""
    target = _write(tmp_path / "page.mdx", FRONTMATTER + BODY)
    run_injector("--mode", "fix-in-place", str(target))
    once = target.read_text(encoding="utf-8")

    second = run_injector("--mode", "fix-in-place", str(target))
    check = run_injector("--mode", "check", str(target))

    assert second.returncode == 0, second.stderr
    assert target.read_text(encoding="utf-8") == once
    assert check.returncode == 0, check.stderr


def test_mdx_check_flags_a_missing_line_without_writing(
    tmp_path: Path,
    run_injector: InjectorRunner,
) -> None:
    """Check mode reports divergence with exit 1 and leaves the file alone."""
    target = _write(tmp_path / "page.mdx", FRONTMATTER + BODY)

    result = run_injector("--mode", "check", str(target))

    assert result.returncode == 1, result.stderr
    assert "divergence:" in result.stderr
    assert target.read_text(encoding="utf-8") == FRONTMATTER + BODY


def test_mdx_canonical_in_both_repo_forms_passes_check(
    tmp_path: Path,
    run_injector: InjectorRunner,
) -> None:
    """Both layouts found in the repository's MDX pages pass check mode."""
    directly_after = _write(tmp_path / "a.mdx", FRONTMATTER + MDX_LINE + "\n\n" + BODY)
    blank_then_line = _write(
        tmp_path / "b.mdx", FRONTMATTER + "\n" + MDX_LINE + "\n\n" + BODY
    )

    result = run_injector("--mode", "check", str(directly_after), str(blank_then_line))

    assert result.returncode == 0, result.stderr


def test_bare_mdx_line_without_blank_is_normalized_not_duplicated(
    tmp_path: Path,
    run_injector: InjectorRunner,
) -> None:
    """A bare MDX line followed by content gains its blank line; no copy is added."""
    generated = "{/* apothem:generated-page — generated from src/apothem/commands */}\n"
    target = _write(tmp_path / "page.mdx", FRONTMATTER + MDX_LINE + "\n" + generated)

    result = run_injector("--mode", "fix-in-place", str(target))

    assert result.returncode == 0, result.stderr
    text = target.read_text(encoding="utf-8")
    assert text.count(MDX_LINE) == 1
    assert text == FRONTMATTER + MDX_LINE + "\n\n" + generated


def test_bare_python_line_without_blank_is_normalized_not_duplicated(
    tmp_path: Path,
    run_injector: InjectorRunner,
) -> None:
    """The bare-line normalization applies to every variant, not only MDX."""
    hash_line = "# SPDX-License-Identifier: MIT"
    target = _write(tmp_path / "tool.py", hash_line + "\nprint('hi')\n")

    result = run_injector("--mode", "fix-in-place", str(target))

    assert result.returncode == 0, result.stderr
    assert target.read_text(encoding="utf-8") == hash_line + "\n\nprint('hi')\n"


def test_banner_fixture_supplies_the_mdx_line_text(
    tmp_path: Path,
    run_injector: InjectorRunner,
) -> None:
    """The MDX line is rendered from the banner fixture, not hard-coded."""
    banner = _write(tmp_path / "banner.txt", "# SPDX-License-Identifier: Apache-2.0\n")
    target = _write(tmp_path / "page.mdx", FRONTMATTER + BODY)

    result = run_injector(
        "--mode", "fix-in-place", "--banner", str(banner), str(target)
    )

    assert result.returncode == 0, result.stderr
    assert target.read_text(encoding="utf-8") == (
        FRONTMATTER + "{/* SPDX-License-Identifier: Apache-2.0 */}\n\n" + BODY
    )
