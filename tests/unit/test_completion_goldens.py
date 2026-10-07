# SPDX-License-Identifier: MIT

"""Shell-completion goldens stay byte-identical to ``apothem completion``.

``scripts/dev/regenerate-completions.{sh,ps1}`` writes each golden under
``src/apothem/cli/completions/`` as the SPDX header followed by the output of
``apothem completion <shell>``. ``completion`` once echoed each source template
with an extra newline, which left a trailing blank line in ``apothem.ps1`` that
the end-of-file-fixer hook rewrote on every run. These tests pin the newline
count and the golden parity for every supported shell.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main

_COMPLETIONS = (
    Path(__file__).resolve().parents[2] / "src" / "apothem" / "cli" / "completions"
)
_HEADER = "# SPDX-License-Identifier: MIT\n\n"
_GOLDENS = {
    "bash": "apothem.bash",
    "zsh": "apothem.zsh",
    "fish": "apothem.fish",
    "powershell": "apothem.ps1",
}


def _emit(shell: str) -> str:
    result = CliRunner().invoke(main, ["completion", shell])
    assert result.exit_code == 0, result.output
    return result.output


@pytest.mark.parametrize("shell", sorted(_GOLDENS))
def test_completion_ends_with_one_newline(shell: str) -> None:
    """The emitted script ends in exactly one newline, never a blank line."""
    output = _emit(shell)
    assert output.endswith("\n")
    assert not output.endswith("\n\n")


@pytest.mark.parametrize("shell", sorted(_GOLDENS))
def test_committed_golden_matches_completion_output(shell: str) -> None:
    """Each committed golden is the SPDX header plus ``completion <shell>``."""
    committed = (_COMPLETIONS / _GOLDENS[shell]).read_text(encoding="utf-8")
    assert committed == _HEADER + _emit(shell)
