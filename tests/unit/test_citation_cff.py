# SPDX-License-Identifier: MIT

"""Validate the repo-root ``CITATION.cff`` against the CFF 1.2.0 contract.

Why this test exists. ``CITATION.cff`` is the machine-readable citation
metadata GitHub surfaces on the repository page and that citation tooling
(``cffconvert``, Zenodo) consumes. A malformed or field-incomplete CFF file
is silently useless — GitHub shows no "Cite this repository" affordance and
downstream tooling errors. This test loads the file with the vendored YAML
parser and asserts the required Citation File Format 1.2.0 fields are present
and well-formed, so a structural regression is caught in the unit suite.

Scope discipline. The test asserts field PRESENCE and SHAPE only. It does
NOT assert the ``version`` or ``date-released`` values, which are
release-coupled and rolled by the release cycle — pinning them here would
couple an unrelated metadata refresh to a version bump.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import yaml

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_CITATION_PATH: Final[Path] = _REPO_ROOT / "CITATION.cff"

# The CFF 1.2.0 keys a software citation record MUST carry. ``cff-version``,
# ``message``, and ``authors`` are required by the format itself; ``title``,
# ``version``, ``date-released``, and ``license`` are the software-citation
# fields GitHub and Zenodo consume. Presence — not value — is asserted for the
# release-coupled fields (``version``, ``date-released``).
_REQUIRED_TOP_LEVEL_KEYS: Final[frozenset[str]] = frozenset(
    {
        "cff-version",
        "message",
        "title",
        "version",
        "date-released",
        "license",
        "authors",
    }
)

_REQUIRED_AUTHOR_KEYS: Final[frozenset[str]] = frozenset(
    {"family-names", "given-names"}
)


def _load_citation() -> dict[str, Any]:
    text = _CITATION_PATH.read_text(encoding="utf-8")
    loaded = yaml.safe_load(text)
    assert isinstance(loaded, dict), "CITATION.cff must deserialize to a mapping"
    return loaded


def test_citation_file_exists() -> None:
    assert _CITATION_PATH.is_file(), f"CITATION.cff absent at {_CITATION_PATH}"


def test_required_top_level_fields_present() -> None:
    data = _load_citation()
    missing = _REQUIRED_TOP_LEVEL_KEYS - data.keys()
    assert not missing, (
        f"CITATION.cff is missing required CFF fields: {sorted(missing)}"
    )


def test_cff_version_is_1_2_0() -> None:
    data = _load_citation()
    # The cff-version pins the schema the record conforms to; 1.2.0 is the
    # current stable Citation File Format. Unlike the software version, this is
    # a format identifier, not a release-coupled value.
    assert str(data["cff-version"]) == "1.2.0", (
        f"cff-version is {data['cff-version']!r}; expected '1.2.0'"
    )


def test_message_is_non_empty_string() -> None:
    data = _load_citation()
    message = data["message"]
    assert isinstance(message, str), "CFF `message` must be a string"
    assert message.strip(), "CFF `message` must be non-empty"


def test_license_is_mit() -> None:
    data = _load_citation()
    # The repository ships under MIT (root LICENSE); the citation record must
    # agree with the SPDX identifier used across the tree.
    assert data["license"] == "MIT", f"license is {data['license']!r}; expected 'MIT'"


def test_authors_is_non_empty_list_of_well_formed_entries() -> None:
    data = _load_citation()
    authors = data["authors"]
    assert isinstance(authors, list), "CFF `authors` must be a list"
    assert authors, "CFF `authors` must be non-empty"
    for index, author in enumerate(authors):
        assert isinstance(author, dict), f"author[{index}] must be a mapping"
        missing = _REQUIRED_AUTHOR_KEYS - author.keys()
        assert not missing, (
            f"author[{index}] is missing required keys: {sorted(missing)}"
        )
        for key in _REQUIRED_AUTHOR_KEYS:
            value = author[key]
            assert isinstance(value, str), f"author[{index}].{key} must be a string"
            assert value.strip(), f"author[{index}].{key} must be non-empty"


def test_version_and_date_released_are_present_and_shaped() -> None:
    data = _load_citation()
    # Presence + shape only — the concrete values are release-coupled and are
    # deliberately not pinned here (a release bump owns them).
    version = data["version"]
    assert isinstance(version, str), "CFF `version` must be a string"
    assert version.strip(), "CFF `version` must be non-empty"
    date_released = data["date-released"]
    # PyYAML may deserialize an unquoted ISO date to a datetime.date; the
    # quoted form stays a string. Accept either — both are valid CFF.
    assert str(date_released).strip(), "CFF `date-released` must be present"
