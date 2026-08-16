# SPDX-License-Identifier: MIT

"""Schemas, fixtures, and reference data packaged as Python resources.

This package ships JSON schemas, YAML configuration fixtures, and text
fixtures (banner, exceptions list) as importable package resources so
runtime consumers resolve them via ``importlib.resources`` rather than
filesystem-walks anchored against ``__file__``. The latter break in
installed-package contexts where the relative layout differs from the
source tree.

Each public accessor returns a ``pathlib.Path`` pointing at the
on-disk-materialized resource (sufficient for ``Path.read_text``,
``Path.is_file``, and equality comparisons), or — for callers that need
the abstract ``Traversable`` form — a direct ``.files()`` traversal is
also exported.

Example:
    >>> from apothem.schemas import banner_path
    >>> text = banner_path().read_text(encoding="utf-8")
"""

from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path
from typing import Final

_PACKAGE: Final[str] = __name__

_BANNER_NAME: Final[str] = "authorship-header.txt"
_HEADER_EXCEPTIONS_NAME: Final[str] = "header-exceptions.txt"
_HEADER_VISIBILITY_NAME: Final[str] = "header-visibility.yaml"
_COMPATIBILITY_MATRIX_NAME: Final[str] = "compatibility-matrix.yaml"
_HANDOFF_MANIFEST_NAME: Final[str] = "handoff-manifest.yaml"
_PROFILE_EXAMPLE_NAME: Final[str] = "profile.example.yaml"
_PROFILE_MINIMAL_NAME: Final[str] = "profile.minimal.yaml"

_AGENT_SCHEMA_NAME: Final[str] = "agent.schema.json"
_COMMAND_SCHEMA_NAME: Final[str] = "command.schema.json"
_SKILL_SCHEMA_NAME: Final[str] = "skill.schema.json"
_PLAN_SCHEMA_NAME: Final[str] = "plan.schema.json"
_OUTPUT_STYLE_SCHEMA_NAME: Final[str] = "output-style.schema.json"
_PROFILE_SCHEMA_NAME: Final[str] = "profile.schema.json"
_ADVISORY_FINDING_SCHEMA_NAME: Final[str] = "advisory-finding.schema.json"
_MEMORY_RECORD_SCHEMA_NAME: Final[str] = "memory-record.schema.json"
_CONTEXT_FRAGMENT_SCHEMA_NAME: Final[str] = "context-fragment.schema.json"
_LEARNING_SIGNAL_SCHEMA_NAME: Final[str] = "learning-signal.schema.json"


def resource_path(name: str) -> Path:
    """Return the on-disk path of a schema resource by filename.

    Args:
        name: The schema fixture's filename (e.g.,
            ``"authorship-header.txt"``).

    Returns:
        A ``pathlib.Path`` to the resource. When the package is
        installed from a wheel into a zipfile-based loader, the path
        points at a materialized on-disk copy.

    Raises:
        FileNotFoundError: When the named resource is not bundled in
            the installed package.
    """
    traversable = files(_PACKAGE) / name
    with as_file(traversable) as concrete:
        return Path(concrete)


def banner_path() -> Path:
    """Path to the canonical authorship-header fixture."""
    return resource_path(_BANNER_NAME)


def header_exceptions_path() -> Path:
    """Path to the header-exceptions glob fixture."""
    return resource_path(_HEADER_EXCEPTIONS_NAME)


def header_visibility_path() -> Path:
    """Path to the per-class header-visibility fixture."""
    return resource_path(_HEADER_VISIBILITY_NAME)


def compatibility_matrix_path() -> Path:
    """Path to the harness compatibility matrix."""
    return resource_path(_COMPATIBILITY_MATRIX_NAME)


def handoff_manifest_schema_path() -> Path:
    """Path to the plan-pipeline handoff-manifest schema."""
    return resource_path(_HANDOFF_MANIFEST_NAME)


def profile_example_path() -> Path:
    """Path to the example user-profile fixture."""
    return resource_path(_PROFILE_EXAMPLE_NAME)


def profile_minimal_path() -> Path:
    """Path to the minimal user-profile fixture."""
    return resource_path(_PROFILE_MINIMAL_NAME)


def agent_schema_path() -> Path:
    """Path to the agent JSON schema."""
    return resource_path(_AGENT_SCHEMA_NAME)


def command_schema_path() -> Path:
    """Path to the command JSON schema."""
    return resource_path(_COMMAND_SCHEMA_NAME)


def skill_schema_path() -> Path:
    """Path to the skill JSON schema."""
    return resource_path(_SKILL_SCHEMA_NAME)


def plan_schema_path() -> Path:
    """Path to the plan JSON schema."""
    return resource_path(_PLAN_SCHEMA_NAME)


def output_style_schema_path() -> Path:
    """Path to the output-style JSON schema."""
    return resource_path(_OUTPUT_STYLE_SCHEMA_NAME)


def profile_schema_path() -> Path:
    """Path to the user-profile JSON schema."""
    return resource_path(_PROFILE_SCHEMA_NAME)


def advisory_finding_schema_path() -> Path:
    """Path to the advisory-mode auditor findings JSON schema."""
    return resource_path(_ADVISORY_FINDING_SCHEMA_NAME)


def memory_record_schema_path() -> Path:
    """Path to the agnostic memory-record JSON schema."""
    return resource_path(_MEMORY_RECORD_SCHEMA_NAME)


def context_fragment_schema_path() -> Path:
    """Path to the injectable context-fragment JSON schema."""
    return resource_path(_CONTEXT_FRAGMENT_SCHEMA_NAME)


def learning_signal_schema_path() -> Path:
    """Path to the continuous-learning signal JSON schema."""
    return resource_path(_LEARNING_SIGNAL_SCHEMA_NAME)


__all__ = [
    "advisory_finding_schema_path",
    "agent_schema_path",
    "banner_path",
    "command_schema_path",
    "compatibility_matrix_path",
    "context_fragment_schema_path",
    "handoff_manifest_schema_path",
    "header_exceptions_path",
    "header_visibility_path",
    "learning_signal_schema_path",
    "memory_record_schema_path",
    "output_style_schema_path",
    "plan_schema_path",
    "profile_example_path",
    "profile_minimal_path",
    "profile_schema_path",
    "resource_path",
    "skill_schema_path",
]
