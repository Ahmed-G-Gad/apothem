# SPDX-License-Identifier: MIT

"""Rendered agent frontmatter must be valid, round-tripping YAML.

Regression guard for the converter family in ``install_driver_converters``:
every YAML-frontmatter-emitting agent converter (Gemini CLI, Qwen Code,
OpenCode) MUST quote the ``name`` / ``description`` scalars so a description
containing a colon renders parseable YAML. A prior unquoted
``description: {value}`` interpolation in the Gemini converter shipped invalid
frontmatter that ``yaml.safe_load`` rejected with "mapping values are not
allowed here"; the byte-snapshot behavior-diff fixtures passed because they
embedded the broken output. This test asserts the rendered frontmatter parses
and the description round-trips, closing that test-invisible class so a future
converter cannot regress it silently.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import pytest
import yaml

from apothem.harnesses._shared import install_driver_converters as conv

_AGENT_DIR = Path(str(resources.files("apothem") / "agents"))
_AGENT_SOURCES = sorted(_AGENT_DIR.glob("*.md"))

# Every converter that emits a YAML frontmatter block from an agent source.
# (Codex emits TOML, not YAML, and is covered by its own converter tests.)
_YAML_AGENT_CONVERTERS = {
    "gemini": conv._gemini_agent_text,
    "opencode": conv._opencode_agent_text,
    "qwen": conv._qwen_agent_text,
}


def test_agent_sources_present() -> None:
    """Guard against a silent empty parametrization (a vacuous pass)."""
    assert _AGENT_SOURCES, f"no agent sources discovered under {_AGENT_DIR}"


@pytest.mark.parametrize("converter", sorted(_YAML_AGENT_CONVERTERS))
@pytest.mark.parametrize("source", _AGENT_SOURCES, ids=lambda p: p.stem)
def test_rendered_agent_frontmatter_is_valid_yaml(converter: str, source: Path) -> None:
    """Rendered frontmatter parses as a mapping and round-trips the description."""
    rendered = _YAML_AGENT_CONVERTERS[converter](source)
    parts = rendered.split("---", 2)
    assert len(parts) == 3, f"{converter}/{source.stem}: no frontmatter fence"
    parsed = yaml.safe_load(parts[1])
    assert isinstance(parsed, dict), (
        f"{converter}/{source.stem}: frontmatter is not a YAML mapping"
    )
    assert parsed["description"] == conv._agent_description(source), (
        f"{converter}/{source.stem}: description was dropped or mangled"
    )
