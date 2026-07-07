# SPDX-License-Identifier: MIT

"""Mechanical parity guard for the paired install.sh / install.ps1 installers.

``scripts/installer/install.sh`` (POSIX) and ``install.ps1`` (PowerShell) are
hand-duplicated: each independently reimplements the same trust model — release-
tag recognition, the verification-bypass opt-out, and the source-precedence
order. The two drifted once already (the POSIX ``is_release_tag`` accepted
pre-release and malformed tags that the anchored PowerShell ``Test-ReleaseTag``
regex rejected), taking a pinned pre-release down the wrong verify branch.

Full unification of the two scripts is out of scope. These tests are a drift
guard over the extractable decision-table constants: they read both scripts and
assert that the SemVer recognition shape, the verification-bypass environment
variable name, and the source-precedence order agree. A future edit to one
script that does not mirror the other trips a finding here instead of shipping
a silent divergence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
INSTALLER: Path = REPO_ROOT / "scripts" / "installer"

SH: str = (INSTALLER / "install.sh").read_text(encoding="utf-8")
PS1: str = (INSTALLER / "install.ps1").read_text(encoding="utf-8")


def test_release_tag_recognition_is_strict_semver_in_both() -> None:
    """Both installers recognise a release tag as strict, anchored SemVer.

    install.ps1's ``Test-ReleaseTag`` uses the anchored regex
    ``^v[0-9]+\\.[0-9]+\\.[0-9]+$``. install.sh's ``is_release_tag`` cannot use
    a regex (POSIX ``case`` globs have no anchors or ``+`` quantifier), so it
    pairs the ``v[0-9]*.[0-9]*.[0-9]*`` shape glob with a ``*[!v0-9.]*`` reject
    gate that drops any tag carrying a character outside the strict ``v``/digit/
    dot set — the same acceptance set as the PowerShell regex. Both surfaces
    must be present so neither script silently loosens back to matching
    pre-release (``v1.2.3-rc1``) or malformed (``v1x.2.3``) tags.
    """
    # PowerShell: the anchored strict-SemVer regex.
    assert r"^v[0-9]+\.[0-9]+\.[0-9]+$" in PS1, (
        "install.ps1 no longer anchors Test-ReleaseTag to strict SemVer"
    )
    # POSIX: the reject gate that rejects any non-[v0-9.] character, plus the
    # digit-anchored component shape. Together they mirror the ps1 regex.
    assert "*[!v0-9.]*)" in SH, (
        "install.sh lost the non-SemVer-character reject gate in is_release_tag; "
        "without it the case glob matches v1.2.3-rc1 and v1x.2.3"
    )
    assert "v[0-9]*.[0-9]*.[0-9]*)" in SH, (
        "install.sh lost the three-component SemVer shape glob in is_release_tag"
    )


@pytest.mark.parametrize("tag", ["v1.2.3", "v10.20.30", "v0.0.1"])
def test_strict_semver_tags_are_accepted_by_both_shapes(tag: str) -> None:
    """A well-formed release tag is accepted by both recognition shapes."""
    # POSIX acceptance: no non-[v0-9.] character present AND the shape matches.
    assert _sh_is_release_tag(tag), f"install.sh shape rejects valid tag {tag}"
    # PowerShell acceptance: the anchored regex matches.
    import re

    assert re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag), (
        f"install.ps1 regex rejects valid tag {tag}"
    )


@pytest.mark.parametrize("tag", ["v1.2.3-rc1", "v1x.2.3", "main", "abc123", "v1.2"])
def test_non_release_refs_are_rejected_by_both_shapes(tag: str) -> None:
    """Pre-release, malformed, branch, and SHA refs are rejected by both.

    This is the exact class the original POSIX glob mis-accepted; the reject
    gate now makes install.sh agree with install.ps1's anchored regex.
    """
    import re

    assert not _sh_is_release_tag(tag), f"install.sh shape wrongly accepts {tag}"
    assert not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag), (
        f"install.ps1 regex wrongly accepts {tag}"
    )


def _sh_is_release_tag(ref: str) -> bool:
    """Model install.sh's ``is_release_tag`` two-gate logic in Python.

    Mirrors the shell function exactly: (1) reject any ref containing a
    character outside the ``v``/digit/dot set; (2) require the three-component
    ``v<digits>.<digits>.<digits>`` shape. Kept in lockstep with the shell
    source by the presence assertions in
    :func:`test_release_tag_recognition_is_strict_semver_in_both`.
    """
    import fnmatch

    # Gate 1: reject a character outside [v0-9.] (POSIX `case *[!v0-9.]* `).
    if fnmatch.fnmatchcase(ref, "*[!v0-9.]*"):
        return False
    # Gate 2: the three-component shape (POSIX `v[0-9]*.[0-9]*.[0-9]*`).
    return fnmatch.fnmatchcase(ref, "v[0-9]*.[0-9]*.[0-9]*")


def test_verification_bypass_env_var_name_agrees() -> None:
    """Both installers gate the verification opt-out on the same env var name.

    A rename in only one script would leave one platform unable to honour the
    documented air-gapped / pre-signed-release escape hatch.
    """
    var = "APOTHEM_ALLOW_UNVERIFIED"
    assert var in SH, f"install.sh does not reference {var}"
    assert var in PS1, f"install.ps1 does not reference {var}"
    # And no divergent spelling of the same intent leaked into either script.
    assert "ALLOW_UNVERIFIED" not in SH.replace(var, ""), (
        "install.sh carries a second ALLOW_UNVERIFIED spelling"
    )
    assert "ALLOW_UNVERIFIED" not in PS1.replace(var, ""), (
        "install.ps1 carries a second ALLOW_UNVERIFIED spelling"
    )


def test_source_precedence_order_agrees() -> None:
    """Both installers resolve the source in the same three-tier precedence.

    Tier 1 APOTHEM_SOURCE (explicit local tree), tier 2 a surrounding local
    checkout, tier 3 a git clone of APOTHEM_REPO. The order is load-bearing: it
    decides whether signature verification runs (only tier 3 fetches). Assert
    the ordering by the first-appearance index of each tier's marker token in
    both scripts.
    """
    for name, content in (("install.sh", SH), ("install.ps1", PS1)):
        i_source = content.find("APOTHEM_SOURCE")
        i_clone = content.find("APOTHEM_REPO")
        assert i_source != -1, f"{name} does not reference APOTHEM_SOURCE"
        assert i_clone != -1, f"{name} does not reference APOTHEM_REPO"
        # The explicit-source tier is documented and handled before the clone
        # tier in both scripts.
        assert i_source < i_clone, (
            f"{name} references the clone remote before the explicit-source "
            f"override — source precedence has drifted"
        )


def test_both_installers_share_the_bypass_and_source_env_surface() -> None:
    """The env-var trust surface is identical across the pair.

    Guards against one script gaining or losing a trust-relevant environment
    override without its sibling. The set is small and load-bearing; a
    divergence is a parity finding.
    """
    trust_env_vars = (
        "APOTHEM_REF",
        "APOTHEM_ALLOW_UNVERIFIED",
        "APOTHEM_SOURCE",
        "APOTHEM_REPO",
        "APOTHEM_HOME",
    )
    for var in trust_env_vars:
        assert var in SH, f"install.sh dropped trust env var {var}"
        assert var in PS1, f"install.ps1 dropped trust env var {var}"
