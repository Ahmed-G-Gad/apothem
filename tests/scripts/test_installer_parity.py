# SPDX-License-Identifier: MIT

"""Mechanical parity guard for the paired POSIX / PowerShell installers.

``scripts/installer/install.sh`` and ``update.sh`` (POSIX) and their
``install.ps1`` / ``update.ps1`` siblings (PowerShell) are hand-duplicated:
each independently reimplements the same trust model — release-tag
recognition, the verification-bypass opt-out, and the source-precedence
order. The pairs drifted already: the POSIX ``is_release_tag`` accepted
pre-release and malformed tags that the anchored PowerShell
``Test-ReleaseTag`` regex rejected, taking a pinned pre-release down the wrong
verify branch, and once install.sh was fixed, update.sh kept the loose copy.

Full unification of the scripts is out of scope. These tests are a drift
guard over the extractable decision-table constants: they read the scripts and
assert that the SemVer recognition shape, the verification-bypass environment
variable name, and the source-precedence order agree. The release-tag shape is
guarded for both the install and the update pair; the other checks cover the
install pair. A future edit to one script that does not mirror its sibling
trips a finding here instead of shipping a silent divergence.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
INSTALLER: Path = REPO_ROOT / "scripts" / "installer"

SCRIPTS: dict[str, str] = {
    name: (INSTALLER / name).read_text(encoding="utf-8")
    for name in ("install.sh", "install.ps1", "update.sh", "update.ps1")
}
SH: str = SCRIPTS["install.sh"]
PS1: str = SCRIPTS["install.ps1"]

# Each POSIX script beside the PowerShell sibling whose Test-ReleaseTag its
# is_release_tag mirrors.
RELEASE_TAG_PAIRS: tuple[tuple[str, str], ...] = (
    ("install.sh", "install.ps1"),
    ("update.sh", "update.ps1"),
)

# The anchored regex both PowerShell scripts' Test-ReleaseTag match against.
PS1_RELEASE_TAG_REGEX = r"^v[0-9]+\.[0-9]+\.[0-9]+$"

VALID_TAGS: tuple[str, ...] = ("v1.2.3", "v10.20.30", "v0.0.1")
NON_RELEASE_REFS: tuple[str, ...] = (
    "v1.2.3-rc1",
    "v1x.2.3",
    "main",
    "abc123",
    "v1.2",
    # Refs of only `v`, digits, and dots, which the first reject gate passes.
    "v1.2.3.4",
    "v1..2.3",
    "v1.2.3.",
    "v1.2.3v",
    "vv1.2.3",
    "v.1.2.3",
    "",
)


@pytest.mark.parametrize(("sh_name", "ps1_name"), RELEASE_TAG_PAIRS)
def test_release_tag_recognition_is_strict_semver_in_both(
    sh_name: str, ps1_name: str
) -> None:
    """Each pair recognises a release tag as strict, anchored SemVer.

    The ``.ps1`` ``Test-ReleaseTag`` uses the anchored regex
    ``^v[0-9]+\\.[0-9]+\\.[0-9]+$``. The ``.sh`` ``is_release_tag`` cannot use
    a regex (POSIX ``case`` globs have no anchors or ``+`` quantifier), so it
    pairs the ``v[0-9]*.[0-9]*.[0-9]*`` shape glob with two reject gates: a
    ``*[!v0-9.]*`` gate that drops any tag carrying a character outside the
    strict ``v``/digit/dot set, and a ``?*v* | *.*.*.*`` gate that drops a
    ``v`` after the first character or a third dot. All three must be present
    so neither script silently loosens back to matching pre-release
    (``v1.2.3-rc1``) or malformed (``v1x.2.3``, ``v1.2.3.4``) tags.
    """
    sh, ps1 = SCRIPTS[sh_name], SCRIPTS[ps1_name]
    # PowerShell: the anchored strict-SemVer regex.
    assert PS1_RELEASE_TAG_REGEX in ps1, (
        f"{ps1_name} no longer anchors Test-ReleaseTag to strict SemVer"
    )
    # POSIX: the reject gate that rejects any non-[v0-9.] character, plus the
    # digit-anchored component shape. Together they mirror the ps1 regex.
    assert "*[!v0-9.]*)" in sh, (
        f"{sh_name} lost the non-SemVer-character reject gate in is_release_tag; "
        "without it the case glob matches v1.2.3-rc1 and v1x.2.3"
    )
    assert "?*v* | *.*.*.*)" in sh, (
        f"{sh_name} lost the extra-v / third-dot reject gate in is_release_tag; "
        "without it the case glob matches v1.2.3.4 and v1.2.3v"
    )
    assert "v[0-9]*.[0-9]*.[0-9]*)" in sh, (
        f"{sh_name} lost the three-component SemVer shape glob in is_release_tag"
    )


def test_install_and_update_define_the_same_is_release_tag() -> None:
    """update.sh carries install.sh's ``is_release_tag`` unchanged.

    update.sh says its tag helpers mirror install.sh's. It kept the loose
    single-glob copy after install.sh gained the reject gate, and so sent
    ``v1.2.3-rc1`` to ``git verify-tag`` where update.ps1 refused it.
    """
    assert _sh_function(SCRIPTS["update.sh"], "is_release_tag") == (
        _sh_function(SH, "is_release_tag")
    ), "update.sh's is_release_tag has drifted from install.sh's"


@pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("sh") is None,
    reason="runs the POSIX is_release_tag under sh",
)
@pytest.mark.parametrize(("sh_name", "ps1_name"), RELEASE_TAG_PAIRS)
def test_posix_is_release_tag_agrees_with_the_ps1_regex(
    sh_name: str, ps1_name: str
) -> None:
    """Each script's own ``is_release_tag``, run under sh, agrees with the
    ``.ps1`` regex on every ref.

    The substring checks and the Python model in :func:`_sh_is_release_tag`
    can pass while the shell function behaves differently, for example with
    its gates reordered. This runs the definition the script ships.
    """
    refs = (*VALID_TAGS, *NON_RELEASE_REFS)
    program = (
        _sh_function(SCRIPTS[sh_name], "is_release_tag")
        + '\nfor ref in "$@"; do\n'
        + '    if is_release_tag "$ref"; then echo release; else echo other; fi\n'
        + "done\n"
    )
    result = subprocess.run(
        ["sh", "-c", program, "sh", *refs],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    verdicts = dict(zip(refs, result.stdout.splitlines(), strict=True))
    disagreements = {
        ref: verdict
        for ref, verdict in verdicts.items()
        if (verdict == "release") != bool(re.search(PS1_RELEASE_TAG_REGEX, ref))
    }
    assert not disagreements, (
        f"{sh_name}'s is_release_tag disagrees with {ps1_name}'s Test-ReleaseTag "
        f"(ref: {sh_name} verdict): {disagreements}"
    )


def _sh_function(script: str, name: str) -> str:
    """Return the definition of shell function NAME, from ``NAME() {`` to the
    closing ``}`` at column 0, as SCRIPT carries it."""
    match = re.search(rf"^{name}\(\) \{{\n.*?^\}}$", script, re.MULTILINE | re.DOTALL)
    assert match, f"no {name}() definition found"
    return match.group(0)


@pytest.mark.parametrize("tag", VALID_TAGS)
def test_strict_semver_tags_are_accepted_by_both_shapes(tag: str) -> None:
    """A well-formed release tag is accepted by both recognition shapes."""
    # POSIX acceptance: no non-[v0-9.] character present AND the shape matches.
    assert _sh_is_release_tag(tag), f"install.sh shape rejects valid tag {tag}"
    # PowerShell acceptance: the anchored regex matches.
    assert re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag), (
        f"install.ps1 regex rejects valid tag {tag}"
    )


@pytest.mark.parametrize("tag", NON_RELEASE_REFS)
def test_non_release_refs_are_rejected_by_both_shapes(tag: str) -> None:
    """Pre-release, malformed, branch, and SHA refs are rejected by both.

    This is the exact class the original POSIX glob mis-accepted; the reject
    gates now make install.sh agree with install.ps1's anchored regex.
    """
    assert not _sh_is_release_tag(tag), f"install.sh shape wrongly accepts {tag}"
    assert not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag), (
        f"install.ps1 regex wrongly accepts {tag}"
    )


def _sh_is_release_tag(ref: str) -> bool:
    """Model install.sh's ``is_release_tag`` three-gate logic in Python.

    Mirrors the shell function: (1) reject any ref containing a character
    outside the ``v``/digit/dot set; (2) reject a ``v`` after the first
    character or a third dot; (3) require the three-component
    ``v<digits>.<digits>.<digits>`` shape. Kept in lockstep with the shell
    source by the presence assertions in
    :func:`test_release_tag_recognition_is_strict_semver_in_both`, and checked
    against the real function by
    :func:`test_posix_is_release_tag_agrees_with_the_ps1_regex`.
    """
    import fnmatch

    # Gate 1: reject a character outside [v0-9.] (POSIX `case *[!v0-9.]* `).
    if fnmatch.fnmatchcase(ref, "*[!v0-9.]*"):
        return False
    # Gate 2: reject a later `v` or a third dot (POSIX `?*v* | *.*.*.*`).
    if fnmatch.fnmatchcase(ref, "?*v*") or fnmatch.fnmatchcase(ref, "*.*.*.*"):
        return False
    # Gate 3: the three-component shape (POSIX `v[0-9]*.[0-9]*.[0-9]*`).
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
        "APOTHEM_VERIFY",
        "APOTHEM_RELEASE_BASE",
    )
    for var in trust_env_vars:
        assert var in SH, f"install.sh dropped trust env var {var}"
        assert var in PS1, f"install.ps1 dropped trust env var {var}"


def test_checksum_mode_messages_agree() -> None:
    """Both installers refuse a digest mismatch and state the same limit.

    The checksum path is weaker than signature verification; each installer
    must abort on a mismatch before extracting anything and must tell the user
    that a matching digest does not prove who published the archive.
    """
    for phrase in (
        "does not match the release's SHA256SUMS",
        "Aborting before anything is extracted.",
        "it does not prove who published it",
        "needs a vMAJOR.MINOR.PATCH release tag",
        "lists no",
        "does not hold an apothem source under",
        "Could not download",
        "Could not extract",
        "Could not create the parent directory of",
        "Could not remove the existing",
        "Could not move the extracted source to",
    ):
        assert phrase in SH, f"install.sh lacks {phrase!r}"
        assert phrase in PS1, f"install.ps1 lacks {phrase!r}"
