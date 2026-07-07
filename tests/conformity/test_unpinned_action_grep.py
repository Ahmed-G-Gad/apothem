# SPDX-License-Identifier: MIT

"""Behavior contract for `src/apothem/conformity/unpinned-action-grep.py`.

Tests cover six contracts: (a) a SHA-pinned action passes; (b) a
SHA-pinned action with a trailing version-tag comment passes (the regex
tolerates `# v4.1.7` style annotations); (c) an unpinned tag-ref is
flagged; (d) the `# action-pinning-exempt: <reason>` marker honors the
exemption when a rationale is supplied; (e) the bare marker without a
rationale segment is NOT honored; (f) local in-repo action references
(`./` prefix) are out of scope.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_TOOLS_DIR = Path(__file__).resolve().parents[2] / "src" / "apothem" / "conformity"
_MODULE_PATH = _TOOLS_DIR / "unpinned_action_grep.py"

_SHA_FORTY = "b4ffde65f46336ab88eb53be808477a3936bae11"
_OTHER_SHA = "d7d6bc77b97f59683e7d70bf5b1bf5302a3b81d3"


def _load_module():
    """Load the hyphen-named matcher module via importlib spec.

    Registers the module in `sys.modules` before `exec_module` so
    dataclass introspection (Python 3.14+) can resolve `cls.__module__`
    against the live module record. Without the registration, frozen
    dataclasses inside the loaded module raise AttributeError on first
    instantiation.
    """
    spec = importlib.util.spec_from_file_location("unpinned_action_grep", _MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module spec from {_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["unpinned_action_grep"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def matcher():
    """Return the loaded unpinned-action-grep module."""
    return _load_module()


def test_sha_pinned_action_passes(matcher) -> None:
    """A 40-character lowercase-hex SHA ref is the only conformant form."""
    content = (
        "jobs:\n"
        "  build:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        f"      - uses: actions/checkout@{_SHA_FORTY}\n"
    )
    result = matcher.check(content, Path(".github/workflows/build.yml"))

    assert result.passed is True
    assert result.findings == []


def test_sha_pinned_with_trailing_version_comment_passes(matcher) -> None:
    """Trailing `# vX.Y.Z` comments on `uses:` lines are tolerated.

    The USES_LINE_RE regex admits an optional `# ...` trailing comment so
    workflow files annotating SHAs with their corresponding version tag (a
    host-discovered audit-trail convention) do not fail the matcher.
    """
    content = (
        "    steps:\n"
        f"      - uses: actions/checkout@{_SHA_FORTY}  # v4.1.7\n"
        f"      - uses: sigstore/cosign-installer@{_OTHER_SHA} # v3.5.0\n"
    )
    result = matcher.check(content, Path(".github/workflows/sign.yml"))

    assert result.passed is True
    assert result.findings == []


def test_unpinned_tag_ref_is_flagged(matcher) -> None:
    """`@v4` / `@main` / `@latest` are mutable refs and must be flagged."""
    content = (
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - uses: actions/setup-python@main\n"
    )
    result = matcher.check(content, Path(".github/workflows/build.yml"))

    assert result.passed is False
    assert len(result.findings) == 2
    flagged_refs = {f.ref for f in result.findings}
    assert flagged_refs == {"v4", "main"}


def test_exemption_marker_with_rationale_is_honoured(matcher) -> None:
    """`# action-pinning-exempt: <reason>` honors the exemption.

    SLSA reusable-workflow references where the Sigstore policy forbids
    SHA-pinning carry the inline marker; the matcher accepts the tag-ref
    when followed by the marker AND a non-whitespace rationale segment.
    """
    content = (
        "    steps:\n"
        "      - uses: slsa-framework/slsa-github-generator/.github/workflows/"
        "generator_generic_slsa3.yml@v2.0.0  "
        "# action-pinning-exempt: SLSA reusable-workflow forbids SHA pin\n"
    )
    result = matcher.check(content, Path(".github/workflows/slsa.yml"))

    assert result.passed is True
    assert result.findings == []


def test_bare_exemption_marker_without_rationale_is_NOT_honoured(matcher) -> None:
    """Audit-trail discipline: the marker requires a rationale segment.

    Bare `# action-pinning-exempt` (no colon, no reason) does not satisfy
    the EXEMPTION_RE regex `#\\s*action-pinning-exempt:\\s*\\S` and the
    tag-ref still surfaces as a finding.
    """
    content = "    steps:\n      - uses: actions/checkout@v4  # action-pinning-exempt\n"
    result = matcher.check(content, Path(".github/workflows/build.yml"))

    assert result.passed is False
    assert len(result.findings) == 1
    assert result.findings[0].action == "actions/checkout"
    assert result.findings[0].ref == "v4"


def test_exemption_marker_with_empty_rationale_segment_is_NOT_honoured(matcher) -> None:
    """`# action-pinning-exempt: ` (colon + whitespace) is non-conformant."""
    content = (
        "    steps:\n      - uses: actions/checkout@v4  # action-pinning-exempt:   \n"
    )
    result = matcher.check(content, Path(".github/workflows/build.yml"))

    assert result.passed is False
    assert len(result.findings) == 1


def test_local_in_repo_action_reference_is_exempt(matcher) -> None:
    """`./` prefix denotes a local composite action; out of scope."""
    content = "    steps:\n      - uses: ./.github/actions/setup\n"
    result = matcher.check(content, Path(".github/workflows/build.yml"))

    assert result.passed is True
    assert result.findings == []


def test_uppercase_hex_ref_is_NOT_a_valid_sha_pin(matcher) -> None:
    """COMMIT_SHA_RE requires exactly forty LOWERCASE hex characters."""
    content = f"    steps:\n      - uses: actions/checkout@{_SHA_FORTY.upper()}\n"
    result = matcher.check(content, Path(".github/workflows/build.yml"))

    assert result.passed is False
    assert len(result.findings) == 1


def test_action_subpath_with_sha_pin_passes(matcher) -> None:
    """Sub-path actions like `actions/cache/save@<sha>` honor the SHA pin."""
    content = f"    steps:\n      - uses: actions/cache/save@{_SHA_FORTY}\n"
    result = matcher.check(content, Path(".github/workflows/cache.yml"))

    assert result.passed is True
    assert result.findings == []
