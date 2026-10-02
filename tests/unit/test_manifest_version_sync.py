# SPDX-License-Identifier: MIT

"""Every version-bearing distribution manifest tracks ``apothem.__version__``.

The project version single-sources from ``pyproject`` into
``apothem.__version__``. Each published distribution manifest — the Claude Code
marketplace manifest, the Gemini and Qwen extension manifests, the Codex plugin
manifest, the Antigravity plugin template, the npm package and VS Code
extension manifests, and the citation file — carries its own hand-maintained
version field. (The Claude Code plugin manifest under ``plugins/claude-code``
is generated from ``pyproject`` and drift-gated by ``test_plugin_tree.py``.) Without a cross-manifest check a
release bump can update the engine version and leave one of these manifests
behind, shipping a stale version to that install channel.

This suite asserts every such manifest equals the current
``apothem.__version__`` so a forgotten bump fails loudly here rather than
surfacing as a stale version on a public install surface.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apothem import __version__

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _json_version(path: Path, *keys: str) -> str:
    """Return the ``version`` field reached by walking *keys* into the JSON."""
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in keys:
        data = data[key]
    version = data["version"]
    assert isinstance(version, str)
    return version


# (relative-path, *key-path-into-the-object) for every JSON manifest whose
# ``version`` field must equal ``apothem.__version__``. An empty key path reads
# the top-level ``version``.
_JSON_MANIFESTS: list[tuple[str, tuple[str, ...]]] = [
    (".claude-plugin/marketplace.json", ()),
    # The marketplace manifest carries the number twice: once at the top level
    # and again under `metadata`. Only the first was gated, so the second could
    # drift to a version no longer shipping with nothing to catch it.
    (".claude-plugin/marketplace.json", ("metadata",)),
    ("gemini-extension.json", ()),
    ("qwen-extension.json", ()),
    ("plugins/apothem/.codex-plugin/plugin.json", ()),
    ("src/apothem/harnesses/antigravity/templates/plugin.json", ()),
    ("package.json", ()),
    ("vscode-extension/package.json", ()),
]


@pytest.mark.parametrize(
    ("relpath", "keys"),
    _JSON_MANIFESTS,
    ids=lambda arg: arg if isinstance(arg, str) else "",
)
def test_json_manifest_version_matches_engine(
    relpath: str, keys: tuple[str, ...]
) -> None:
    path = _REPO_ROOT / relpath
    assert path.is_file(), f"expected manifest is missing: {relpath}"
    assert _json_version(path, *keys) == __version__, (
        f"{relpath} version drifted from apothem.__version__ ({__version__})"
    )


def test_marketplace_nested_plugin_version_matches_engine() -> None:
    """A plugins entry that pins a version must pin the engine's.

    Entries are not obliged to carry one, and today none does — the shipping
    numbers are the manifest's top-level ``version`` and its
    ``metadata.version``, both gated by the table above. This guards the case
    where an entry gains one later, which would otherwise be a third copy of
    the number with nothing holding it to the others.

    The skip is deliberate: filtering first means the report says "not
    exercised" rather than passing while asserting nothing.
    """
    path = _REPO_ROOT / ".claude-plugin" / "marketplace.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    versioned = [entry for entry in data.get("plugins", []) if "version" in entry]
    if not versioned:
        pytest.skip("no marketplace plugins entry pins a version")
    for entry in versioned:
        assert entry["version"] == __version__, (
            f"marketplace nested plugin version drifted from "
            f"apothem.__version__ ({__version__})"
        )


def test_citation_versions_match_engine() -> None:
    """CITATION.cff pins the version in the top-level and preferred-citation blocks."""
    path = _REPO_ROOT / "CITATION.cff"
    assert path.is_file(), "CITATION.cff is missing"
    versions = [
        line.split(":", 1)[1].strip().strip('"').strip("'")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("version:")
    ]
    assert versions, "CITATION.cff carries no version field"
    for version in versions:
        assert version == __version__, (
            f"CITATION.cff version {version!r} drifted from "
            f"apothem.__version__ ({__version__})"
        )
