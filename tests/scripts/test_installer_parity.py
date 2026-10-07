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
In the other direction, ``Test-ReleaseTag`` applied its regex with ``-match``,
which ignores case, so ``V1.2.3`` passed it and failed ``is_release_tag``. Its
``$`` anchor also matched before a final newline, so ``v1.2.3`` with a
trailing newline passed it and failed ``is_release_tag`` too. With no ref
pinned, ``Resolve-LatestTag`` also filtered ``git ls-remote`` output with
``-match``, so it resolved a ``V9.9.9`` tag that ``resolve_latest_tag`` skips.

Full unification of the scripts is out of scope. These tests are a drift
guard over the extractable decision-table constants: they read the scripts and
assert that the SemVer recognition shape, the latest-tag filter, the
verification-bypass environment variable name, and the source-precedence order
agree. The release-tag shape and the latest-tag filter are guarded for both
the install and the update pair; the other checks cover the install pair. A
future edit to one script that does not mirror its sibling trips a finding
here instead of shipping a silent divergence.
"""

from __future__ import annotations

import json
import os
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

# Python's model of Test-ReleaseTag. Python's `$`, like .NET's, also matches
# before a final newline, and Python's `re` has no `\z` before 3.14, so the
# model takes a full match of the unanchored pattern instead.
PS1_RELEASE_TAG_MODEL = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+")
# The anchored .NET regex both PowerShell scripts' Test-ReleaseTag match
# against. `\z` matches only at the end of the string.
PS1_RELEASE_TAG_REGEX = "^" + PS1_RELEASE_TAG_MODEL.pattern + r"\z"
# The .NET regex both PowerShell scripts' Resolve-LatestTag match against each
# `git ls-remote --tags` line. `$` suffices here, since PowerShell hands over
# each line of a native command's output without its newline.
PS1_LS_REMOTE_TAG_REGEX = r"refs/tags/(v[0-9]+\.[0-9]+\.[0-9]+)(\^\{\})?$"

VALID_TAGS: tuple[str, ...] = ("v1.2.3", "v10.20.30", "v0.0.1")
NON_RELEASE_REFS: tuple[str, ...] = (
    "v1.2.3-rc1",
    "v1x.2.3",
    "main",
    "abc123",
    "v1.2",
    # An upper-case `V`. Both checks are case-sensitive: the `case` glob in
    # is_release_tag, and Test-ReleaseTag's -cmatch.
    "V1.2.3",
    # A trailing newline, as `Get-Content -Raw` keeps from a file. The first
    # reject gate in is_release_tag drops it, and Test-ReleaseTag's `\z` does
    # too, where `$` would match before the newline.
    "v1.2.3\n",
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
    ``^v[0-9]+\\.[0-9]+\\.[0-9]+\\z``. The ``.sh`` ``is_release_tag`` cannot use
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
    its gates reordered. This runs the definition the script ships. The
    ``.ps1`` side is :data:`PS1_RELEASE_TAG_MODEL`, since Python cannot run
    the ``\\z`` in :data:`PS1_RELEASE_TAG_REGEX` on every supported version.
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
        if (verdict == "release") != bool(PS1_RELEASE_TAG_MODEL.fullmatch(ref))
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


@pytest.mark.parametrize("ps1_name", [ps1_name for _, ps1_name in RELEASE_TAG_PAIRS])
def test_ps1_test_release_tag_matches_case_sensitively(ps1_name: str) -> None:
    """Each ``.ps1`` ``Test-ReleaseTag`` applies the ``\\z``-anchored regex
    with ``-cmatch``.

    PowerShell's ``-match`` and ``-imatch`` ignore case, so with either one the
    ``.ps1`` took ``V1.2.3`` for a release tag while the POSIX ``case`` glob in
    ``is_release_tag`` rejected it. PowerShell reads operator names without
    case, so ``-CMatch`` passes too. A ``$`` anchor in place of ``\\z`` also
    matches before a final newline, so the ``.ps1`` took ``v1.2.3`` with a
    trailing newline for a release tag.
    """
    function = _ps1_function(SCRIPTS[ps1_name], "Test-ReleaseTag")
    pattern = r"(?i:-cmatch)\s+'" + re.escape(PS1_RELEASE_TAG_REGEX) + "'"
    assert re.search(pattern, function), (
        f"{ps1_name}'s Test-ReleaseTag no longer applies the release-tag regex "
        "with the case-sensitive -cmatch and the \\z end anchor; -match "
        "accepts V1.2.3 and $ accepts a trailing newline, which "
        "is_release_tag rejects"
    )


_PWSH = shutil.which("pwsh") or shutil.which("powershell")


def _ps1_load_function(name: str) -> tuple[str, ...]:
    """Return PowerShell statements that parse the script named by
    ``$env:RELEASE_TAG_SCRIPT`` and store the body of its function NAME, as a
    script block, in ``$body``.

    The script is parsed, not run, so none of its top-level code executes.
    The statements set the strict mode and error preference both installer
    scripts set, so the function runs as it does inside them.
    """
    return (
        "Set-StrictMode -Version Latest",
        "$ErrorActionPreference = 'Stop'",
        "$tokens = $null",
        "$parseErrors = $null",
        "$ast = [Management.Automation.Language.Parser]::ParseFile("
        "$env:RELEASE_TAG_SCRIPT, [ref]$tokens, [ref]$parseErrors)",
        "if ($parseErrors) { throw ($parseErrors -join ' | ') }",
        "$definition = $ast.Find({ param($node) "
        "$node -is [Management.Automation.Language.FunctionDefinitionAst] "
        f"-and $node.Name -eq '{name}' }}, $true)",
        f"if (-not $definition) {{ throw 'no {name} definition' }}",
        "$body = $definition.Body.GetScriptBlock()",
    )


def _run_powershell(
    command: str, ps1_name: str, **env: str
) -> subprocess.CompletedProcess[str]:
    """Run COMMAND under PowerShell, with ``$env:RELEASE_TAG_SCRIPT`` naming
    the installer script PS1_NAME and ENV added to the environment.

    The inputs arrive through the environment, so no value is quoted into
    PowerShell source.
    """
    assert _PWSH is not None
    return subprocess.run(
        [
            _PWSH,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        env={
            **os.environ,
            **env,
            "RELEASE_TAG_SCRIPT": str(INSTALLER / ps1_name),
            "NO_COLOR": "1",
            "POWERSHELL_TELEMETRY_OPTOUT": "1",
        },
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


# Print "release" or "other" for each ref in the JSON array
# $env:RELEASE_TAG_REFS, as the script's Test-ReleaseTag classifies it.
_CLASSIFY_REFS = "; ".join(
    (
        *_ps1_load_function("Test-ReleaseTag"),
        "foreach ($candidate in ($env:RELEASE_TAG_REFS | ConvertFrom-Json)) "
        "{ if (& $body $candidate) { 'release' } else { 'other' } }",
    )
)


@pytest.mark.skipif(_PWSH is None, reason="no PowerShell on this host")
@pytest.mark.parametrize("ps1_name", [ps1_name for _, ps1_name in RELEASE_TAG_PAIRS])
def test_powershell_test_release_tag_accepts_only_release_tags(ps1_name: str) -> None:
    """Each script's own ``Test-ReleaseTag``, run under PowerShell, accepts
    every valid tag and rejects every other ref, ``V1.2.3`` and ``v1.2.3``
    with a trailing newline included.

    :func:`test_ps1_test_release_tag_matches_case_sensitively` reads the source,
    and :data:`PS1_RELEASE_TAG_MODEL` models ``-cmatch`` and ``\\z`` in
    Python. Both can pass while the shipped function behaves differently, so
    this runs it. The refs travel as JSON, so the newline arrives intact.
    """
    refs = (*VALID_TAGS, *NON_RELEASE_REFS)
    result = _run_powershell(
        _CLASSIFY_REFS, ps1_name, RELEASE_TAG_REFS=json.dumps(refs)
    )
    assert result.returncode == 0, result.stdout + result.stderr
    verdicts = dict(zip(refs, result.stdout.splitlines(), strict=True))
    wrong = {
        ref: verdict
        for ref, verdict in verdicts.items()
        if (verdict == "release") != (ref in VALID_TAGS)
    }
    assert not wrong, (
        f"{ps1_name}'s Test-ReleaseTag misclassifies (ref: verdict): {wrong}"
    )


def _ps1_function(script: str, name: str) -> str:
    """Return the definition of PowerShell function NAME, from
    ``function NAME {`` to the closing ``}`` at column 0, as SCRIPT carries it.
    """
    match = re.search(
        rf"^function {re.escape(name)} \{{\n.*?^\}}$",
        script,
        re.MULTILINE | re.DOTALL,
    )
    assert match, f"no function {name} definition found"
    return match.group(0)


@pytest.mark.parametrize("ps1_name", [ps1_name for _, ps1_name in RELEASE_TAG_PAIRS])
def test_ps1_resolve_latest_tag_filters_case_sensitively(ps1_name: str) -> None:
    """Each ``.ps1`` ``Resolve-LatestTag`` filters ``git ls-remote`` lines with
    ``-cmatch``.

    With ``-match``, which ignores case, it took a ``V9.9.9`` tag above the
    newest release for the latest release tag, while the ``sed`` filter in the
    POSIX ``resolve_latest_tag`` respects case and skipped it.
    """
    function = _ps1_function(SCRIPTS[ps1_name], "Resolve-LatestTag")
    pattern = r"(?i:-cmatch)\s+'" + re.escape(PS1_LS_REMOTE_TAG_REGEX) + "'"
    assert re.search(pattern, function), (
        f"{ps1_name}'s Resolve-LatestTag no longer filters git ls-remote lines "
        "with the case-sensitive -cmatch; -match resolves V9.9.9, which "
        "resolve_latest_tag skips"
    )


# `git ls-remote --tags` output, one "<sha>\trefs/tags/<tag>" line per tag plus
# a "<tag>^{}" peel line per annotated tag, beside the tag both resolvers must
# pick from it, or None for none. Neither script's release-tag check accepts a
# `V` tag, so neither resolver may pick one, whatever its number. `v1.10.0`
# outranks `v1.2.3` by number, not by text. A remote with one release tag
# resolves to that tag, not to its last character.
_SHA = "0123456789abcdef0123456789abcdef01234567"
LS_REMOTE_TAG_CASES = (
    pytest.param(
        (
            f"{_SHA}\trefs/tags/V9.9.9",
            f"{_SHA}\trefs/tags/V9.9.9^{{}}",
            f"{_SHA}\trefs/tags/v1.2.3",
            f"{_SHA}\trefs/tags/v1.2.3^{{}}",
            f"{_SHA}\trefs/tags/v1.10.0",
            f"{_SHA}\trefs/tags/v2.0.0-rc1",
        ),
        "v1.10.0",
        id="upper-case-tag-above-the-releases",
    ),
    pytest.param(
        (f"{_SHA}\trefs/tags/V1.0.0", f"{_SHA}\trefs/tags/V1.0.0^{{}}"),
        None,
        id="upper-case-tag-only",
    ),
    pytest.param(
        (f"{_SHA}\trefs/tags/v1.1.0", f"{_SHA}\trefs/tags/v1.1.0^{{}}"),
        "v1.1.0",
        id="one-release-tag",
    ),
)


@pytest.mark.skipif(
    _PWSH is None or sys.platform == "win32" or shutil.which("sh") is None,
    reason="runs Resolve-LatestTag under PowerShell and resolve_latest_tag under sh",
)
@pytest.mark.parametrize(("sh_name", "ps1_name"), RELEASE_TAG_PAIRS)
@pytest.mark.parametrize(("lines", "expected"), LS_REMOTE_TAG_CASES)
def test_resolve_latest_tag_picks_the_same_tag_in_both(
    sh_name: str, ps1_name: str, lines: tuple[str, ...], expected: str | None
) -> None:
    """Each script's own ``Resolve-LatestTag``, run under PowerShell, picks
    the same tag as its POSIX sibling's ``resolve_latest_tag``, run under sh,
    from the same ``git ls-remote --tags`` lines.

    :func:`test_ps1_resolve_latest_tag_filters_case_sensitively` reads the
    source, which can pass while the shipped function behaves differently, so
    this runs both functions. Each one calls a stub ``git`` that prints LINES,
    so no repository or network is involved.
    """
    resolved = {
        ps1_name: _ps1_resolve_latest_tag(ps1_name, lines),
        sh_name: _sh_resolve_latest_tag(sh_name, lines),
    }
    assert resolved == {ps1_name: expected, sh_name: expected}, (
        f"{ps1_name}'s Resolve-LatestTag and {sh_name}'s resolve_latest_tag "
        f"should both resolve {expected!r} (script: tag): {resolved}"
    )


# Run the script's Resolve-LatestTag with `git` shadowed by a function, which
# PowerShell resolves ahead of git on PATH. The stub writes each element of
# the JSON array $env:LS_REMOTE_LINES as one output line and sets
# $LASTEXITCODE to 0, as a successful `git ls-remote --tags` does.
_RESOLVE_LATEST_TAG = "; ".join(
    (
        *_ps1_load_function("Resolve-LatestTag"),
        "function git { $global:LASTEXITCODE = 0; "
        "foreach ($line in ($env:LS_REMOTE_LINES | ConvertFrom-Json)) { $line } }",
        "& $body 'https://example.invalid/apothem.git'",
    )
)


def _ps1_resolve_latest_tag(ps1_name: str, lines: tuple[str, ...]) -> str | None:
    """Return the tag PS1_NAME's own ``Resolve-LatestTag`` picks from the
    ``git ls-remote --tags`` output LINES, or None when it returns ``$null``."""
    result = _run_powershell(
        _RESOLVE_LATEST_TAG, ps1_name, LS_REMOTE_LINES=json.dumps(lines)
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return _only_line(result.stdout)


def _sh_resolve_latest_tag(sh_name: str, lines: tuple[str, ...]) -> str | None:
    """Return the tag SH_NAME's own ``resolve_latest_tag``, run under sh,
    picks from the ``git ls-remote --tags`` output LINES, or None when it
    prints nothing. A shell function named ``git`` takes the place of git on
    PATH."""
    program = (
        "git() { printf '%s\\n' \"$LS_REMOTE_LINES\"; }\n"
        + _sh_function(SCRIPTS[sh_name], "resolve_latest_tag")
        + "\nresolve_latest_tag https://example.invalid/apothem.git\n"
    )
    result = subprocess.run(
        ["sh", "-c", program],
        env={**os.environ, "LS_REMOTE_LINES": "\n".join(lines)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return _only_line(result.stdout)


def _only_line(output: str) -> str | None:
    """Return the one line of OUTPUT, or None when OUTPUT is empty."""
    lines = output.splitlines()
    assert len(lines) <= 1, f"expected one tag at most, got {lines}"
    return lines[0] if lines else None


@pytest.mark.parametrize("tag", VALID_TAGS)
def test_strict_semver_tags_are_accepted_by_both_shapes(tag: str) -> None:
    """A well-formed release tag is accepted by both recognition shapes."""
    # POSIX acceptance: no non-[v0-9.] character present AND the shape matches.
    assert _sh_is_release_tag(tag), f"install.sh shape rejects valid tag {tag}"
    # PowerShell acceptance: the anchored regex matches.
    assert PS1_RELEASE_TAG_MODEL.fullmatch(tag), (
        f"install.ps1 regex rejects valid tag {tag}"
    )


@pytest.mark.parametrize("tag", NON_RELEASE_REFS)
def test_non_release_refs_are_rejected_by_both_shapes(tag: str) -> None:
    """Pre-release, malformed, branch, and SHA refs are rejected by both.

    This is the exact class the original POSIX glob mis-accepted; the reject
    gates now make install.sh agree with install.ps1's anchored regex.
    """
    assert not _sh_is_release_tag(tag), f"install.sh shape wrongly accepts {tag}"
    assert not PS1_RELEASE_TAG_MODEL.fullmatch(tag), (
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
