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
agree, and that the pairs say the same thing where it matters: the tag gate
(signature, key pin, and the signed tag object naming its release), the
cosign check of the tag's commit, the checksum-mode caveat and its gate, and
what a swap into APOTHEM_HOME does with what is there. PowerShell writes ``-``
where the POSIX scripts write an em dash, and ``-Yes`` where they write
``--yes``, so the compared phrases stop short of those. The release-tag shape,
the latest-tag filter and the tag-gate messages are guarded for both the
install and the update pair; the other checks cover the install pair. A
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
# `git ls-remote --tags` line. It is anchored on the object name and the tab
# before the ref, so a tag whose own name holds `refs/tags/v...` does not
# pass. `$` suffices at the end, since PowerShell hands over each line of a
# native command's output without its newline.
PS1_LS_REMOTE_TAG_REGEX = r"^[0-9a-f]+\trefs/tags/(v[0-9]+\.[0-9]+\.[0-9]+)(\^\{\})?$"

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
    pytest.param(
        (
            f"{_SHA}\trefs/tags/v1.1.0",
            f"{_SHA}\trefs/tags/x/refs/tags/v9.9.9",
            f"{_SHA}\trefs/tags/x/refs/tags/v9.9.9^{{}}",
        ),
        "v1.1.0",
        id="tag-name-that-holds-a-release-ref",
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
# PowerShell resolves ahead of git on PATH. The script's own
# Invoke-GitOutsideRepository is defined too, since ls-remote runs through it.
# The stub writes each element of the JSON array $env:LS_REMOTE_LINES as one
# output line and sets $LASTEXITCODE to 0, as a successful
# `git ls-remote --tags` does, but only when it runs from the empty folder
# with GIT_CEILING_DIRECTORIES set; anywhere else it fails, as no tag found.
_RESOLVE_LATEST_TAG = "; ".join(
    (
        *_ps1_load_function("Resolve-LatestTag"),
        "$outside = $ast.Find({ param($node) "
        "$node -is [Management.Automation.Language.FunctionDefinitionAst] "
        "-and $node.Name -eq 'Invoke-GitOutsideRepository' }, $true)",
        "if (-not $outside) { throw 'no Invoke-GitOutsideRepository definition' }",
        ". ([scriptblock]::Create($outside.Extent.Text))",
        "function git { "
        "if (-not $env:GIT_CEILING_DIRECTORIES -or "
        "(Split-Path -Leaf (Get-Location).Path) -notlike 'apothem-git-*') "
        "{ $global:LASTEXITCODE = 1; return }; "
        "$global:LASTEXITCODE = 0; "
        "foreach ($line in ($env:LS_REMOTE_LINES | ConvertFrom-Json)) { $line } }",
        "& $body 'https://example.invalid/apothem.git'",
    )
)


@pytest.mark.skipif(_PWSH is None, reason="no PowerShell on this host")
@pytest.mark.parametrize("ps1_name", [ps1_name for _, ps1_name in RELEASE_TAG_PAIRS])
@pytest.mark.parametrize(("lines", "expected"), LS_REMOTE_TAG_CASES)
def test_powershell_resolve_latest_tag_picks_the_expected_tag(
    ps1_name: str, lines: tuple[str, ...], expected: str | None
) -> None:
    """Each script's own ``Resolve-LatestTag``, run under PowerShell, picks
    the expected tag from each case; this half of the sh comparison runs on
    Windows too."""
    assert _ps1_resolve_latest_tag(ps1_name, lines) == expected


@pytest.mark.skipif(_PWSH is None, reason="no PowerShell on this host")
@pytest.mark.parametrize("ps1_name", [ps1_name for _, ps1_name in RELEASE_TAG_PAIRS])
def test_powershell_resolve_latest_tag_skips_a_tag_too_large_for_version(
    ps1_name: str,
) -> None:
    """A tag whose numbers do not fit ``[version]`` (each part is an Int32) is
    skipped instead of stopping the run with a cast error."""
    lines = (
        f"{_SHA}\trefs/tags/v1.2.3",
        f"{_SHA}\trefs/tags/v1.2.99999999999",
        f"{_SHA}\trefs/tags/v1.2.99999999999^{{}}",
    )
    assert _ps1_resolve_latest_tag(ps1_name, lines) == "v1.2.3"


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
    documented escape hatch for air-gapped use and releases that predate signing.
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


#: The one wording both installers (and the docs) use for checksum mode's
#: limit; the scripts print it before downloading anything.
CHECKSUM_CAVEAT = (
    "Checksum mode does not verify the release. SHA256SUMS comes from the same "
    "release as the archive, so a match only shows the download isn't damaged; "
    "anyone who can change the release's files can change both."
)


def test_checksum_mode_messages_agree() -> None:
    """Both installers refuse a digest mismatch and state the same limit.

    The checksum path verifies nothing about who published the release; each
    installer must abort on a mismatch before extracting anything, state the
    same caveat, and run the mode only with APOTHEM_ALLOW_UNVERIFIED=1.
    """
    for phrase in (
        "does not match the release's SHA256SUMS",
        "Aborting before anything is extracted.",
        CHECKSUM_CAVEAT,
        "Set APOTHEM_ALLOW_UNVERIFIED=1 as well to install this way anyway, or "
        "install gpg (and cosign) and run without APOTHEM_VERIFY=checksum.",
        "Proceeding because APOTHEM_ALLOW_UNVERIFIED=1.",
        "needs a vMAJOR.MINOR.PATCH release tag",
        "lists no",
        "does not hold an apothem source under",
        "Could not download",
        "Could not extract",
        "Could not create the parent directory of",
        "dry run, so",
    ):
        assert phrase in SH, f"install.sh lacks {phrase!r}"
        assert phrase in PS1, f"install.ps1 lacks {phrase!r}"


def test_checksum_mode_is_gated_on_allow_unverified_in_both() -> None:
    """Both installers refuse checksum mode unless APOTHEM_ALLOW_UNVERIFIED=1,
    and put the caveat ahead of the first download.

    A script that kept the old warn-after-download behaviour would still pass
    the phrase check above, so this compares where the gate and the first
    download sit in each script's source.
    """
    for name, content, download in (
        ("install.sh", SH, 'curl -fsSL $CURL_PROTO "${APOTHEM_RELEASE_BASE}'),
        ("install.ps1", PS1, "Invoke-WebRequest -UseBasicParsing"),
    ):
        gate = content.find("Set APOTHEM_ALLOW_UNVERIFIED=1 as well")
        first_download = content.find(download)
        assert gate != -1, f"{name} lacks the checksum-mode gate"
        assert first_download != -1, f"{name}: no download call found"
        assert gate < first_download, (
            f"{name} downloads before it applies the checksum-mode gate"
        )


def test_swap_messages_agree() -> None:
    """Both installers set an existing APOTHEM_HOME aside, carry its data
    over, roll a failed swap back, and refuse a linked APOTHEM_HOME in the
    same words.

    ``-Yes`` and ``--yes`` differ by platform, so the phrases stop short of
    the flag.
    """
    for phrase in (
        "is a symbolic link. Point APOTHEM_HOME at the folder it links to, "
        "then re-run.",
        "is a git clone; refusing to replace it with",
        "which would remove its history. Set APOTHEM_VERIFY=signature to update "
        "the clone, move it aside, or re-run with",
        "Replacing the git clone at",
        "the files the clone does not track (the engine's backups",
        "move into the new install, and the clone's own tree will be moved to a "
        "sibling folder named",
        "Would replace the git clone at",
        "would move into the new install, and the clone's own tree would be moved "
        "to a sibling folder named",
        "Would switch the release-archive install at",
        "other data would be kept",
        "Would update the earlier install at",
        "The earlier clone's tree is kept at",
        "; delete it once you no longer need it.",
        "is a release-archive install, not a git clone; refusing to replace it.",
        "Switching the release-archive install at",
        "Updating the earlier install at",
        "is not empty and holds no Apothem install; refusing to replace it.",
        "to have it moved aside for you.",
        "holds no Apothem install; it will be moved, unchanged, to a sibling "
        "folder named",
        "holds no Apothem install; it would be moved, unchanged, to a sibling "
        "folder named",
        "is a git clone with local work that replacing it would lose (changes, "
        "stashes, unpushed commits, or untracked files in its source tree). "
        "Commit and push that work, or move it elsewhere, then re-run.",
        "stash list",
        "log --branches --not --remotes --oneline",
        ".before-apothem-",
        "were moved, unchanged, to",
        "Could not make room beside",
        "; nothing was changed",
        "into the new install",
        "Could not move the existing",
        "Could not move the new source to",
        "Interrupted while replacing",
        "the earlier install at",
        "is back in place and unchanged",
        "and putting the earlier install back also failed: it is at",
        "(with any moved data under",
        "Move it back to",
        "the earlier folder is back in place and unchanged",
        "and moving the earlier folder back also failed: it is at",
        "Could not remove the earlier source at",
        ".apothem-source-entries",
        "Could not record the source entries in",
    ):
        assert phrase in SH, f"install.sh lacks {phrase!r}"
        assert phrase in PS1, f"install.ps1 lacks {phrase!r}"


@pytest.mark.parametrize(
    ("sh_name", "ps1_name", "after"),
    [
        ("install.sh", "install.ps1", "materialized."),
        ("update.sh", "update.ps1", "re-materialized."),
    ],
)
def test_tag_gate_messages_agree(sh_name: str, ps1_name: str, after: str) -> None:
    """Each pair checks a fetched tag before checking it out and says the
    same thing when the check or the checkout fails.

    The signed tag object must name the release it is installed as; a
    maintainer-signed tag for another release, re-pointed, is refused. The
    checkout never forces, so local changes stop it.
    """
    sh, ps1 = SCRIPTS[sh_name], SCRIPTS[ps1_name]
    for phrase in (
        "carries the maintainer key's signature, but the signed tag object is not the",
        "release tag (it names another tag, or no commit), so it was re-pointed "
        "(possible tampering). Aborting before anything is checked out or " + after,
        "is unsigned or its signature did not verify (possible tampering). "
        "Aborting before anything is checked out or " + after,
        "that SECURITY.md publishes (possible tampering). Aborting before "
        "anything is checked out or " + after,
        "cat-file tag",
        "Could not fetch from the origin of",
        "If a local tag differs from origin's, delete it with",
        "tag -d <tag>', then re-run.",
        "If it has local changes, commit or stash them, then re-run.",
        "checkout --quiet --end-of-options",
        "is not a signed release tag and cannot be verified",
        "has changes to tracked files. Commit or stash them, then re-run.",
        "diff --quiet HEAD",
        "diff --cached --quiet",
        "after the update. Aborting before re-materialization.",
        "status --porcelain --untracked-files=no",
        "checkout --quiet --detach",
        "refs/remotes/origin/",
        "is not the work tree of its git clone (core.worktree is set, or its .git "
        "points elsewhere). Remove that setting, then re-run.",
        "'s own git config sets ",
        ", which the update would trust. Remove it from ",
        "/.git/config, then re-run.",
        "config --local --name-only --get-regexp",
        "ls-files -v",
        "core.hooksPath=",
    ):
        assert phrase in sh, f"{sh_name} lacks {phrase!r}"
        assert phrase in ps1, f"{ps1_name} lacks {phrase!r}"


#: The git variables every script clears at startup: each one set in the
#: calling shell would point git at another repository, work tree, index or
#: object store, or swap objects through replace refs.
CLEARED_GIT_VARIABLES = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_NAMESPACE",
    "GIT_REPLACE_REF_BASE",
    "GIT_CEILING_DIRECTORIES",
    "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_COUNT",
    "GIT_EXEC_PATH",
    "GIT_TEMPLATE_DIR",
)


@pytest.mark.parametrize("name", sorted(SCRIPTS))
def test_every_script_clears_the_git_environment_and_checks_the_repo(
    name: str,
) -> None:
    """All four scripts clear the same git variables, turn replace refs off,
    refuse an APOTHEM_REPO that reads as an option in the same words, and
    look for the gpg program git runs in the same order."""
    content = SCRIPTS[name]
    for variable in CLEARED_GIT_VARIABLES:
        assert variable in content, f"{name} does not clear {variable}"
    for phrase in (
        "GIT_NO_REPLACE_OBJECTS",
        "APOTHEM_REPO must be a repository URL or path, not an option: ",
        "gpg.openpgp.program",
        "gpg.program",
    ):
        assert phrase in content, f"{name} lacks {phrase!r}"
    assert content.find("gpg.openpgp.program") < content.rfind("--get gpg.program"), (
        f"{name} reads gpg.program before gpg.openpgp.program"
    )


@pytest.mark.parametrize("name", sorted(SCRIPTS))
def test_no_script_forces_a_checkout_or_skips_gpg_for_ssh(name: str) -> None:
    """A forced checkout would throw away local changes in a clone, and an
    SSH ``gpg.format`` says nothing about how a release tag is signed (its
    signature is OpenPGP either way), so no script does either."""
    content = SCRIPTS[name]
    assert "checkout --quiet --force" not in content, f"{name} forces a checkout"
    assert "--get gpg.format" not in content, (
        f"{name} still reads gpg.format to skip the gpg check"
    )


@pytest.mark.parametrize("name", ["install.sh", "install.ps1"])
def test_installers_clone_without_checking_out_before_the_gate(name: str) -> None:
    """A fresh clone is made with --no-checkout, so nothing from an unchecked
    ref lands on disk before the tag gate passes."""
    assert "clone --quiet --no-checkout" in SCRIPTS[name]


#: The primary-key fingerprint SECURITY.md publishes for release tags.
MAINTAINER_FINGERPRINT = "5C8998F9F241720445D3F28B70396FED9C634163"


@pytest.mark.parametrize("name", sorted(SCRIPTS))
def test_every_script_pins_the_maintainer_key(name: str) -> None:
    """All four scripts require the tag signature to come from one key.

    ``git verify-tag`` accepts a valid signature from any key the local
    keyring holds. Each script compares GnuPG's VALIDSIG primary-key
    fingerprint with the one SECURITY.md publishes; a script that dropped the
    constant, or carried another value, would accept a tag signed by any key.
    """
    content = SCRIPTS[name]
    assert MAINTAINER_FINGERPRINT in content, (
        f"{name} does not pin {MAINTAINER_FINGERPRINT}"
    )
    assert "VALIDSIG" in content, f"{name} does not read GnuPG's VALIDSIG status"
    assert "carries a valid signature, but not from the maintainer key" in content, (
        f"{name} lacks the other-key abort"
    )


def test_security_md_publishes_the_pinned_fingerprint() -> None:
    """The pinned value is the one SECURITY.md shows readers, spaces aside."""
    security = (REPO_ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert MAINTAINER_FINGERPRINT in re.sub(r"\s+", "", security)


def test_release_mode_trust_roots_and_messages_agree() -> None:
    """Both installers check the same cosign identity and say the same things.

    The release mode trusts SHA256SUMS only when cosign shows the release
    workflow at the installed tag signed it. A different repository casing,
    workflow path or OIDC issuer in one script would make that platform accept
    a bundle the other refuses, or refuse every real one.
    """
    for phrase in (
        "Ahmed-G-Gad/apothem",
        "https://token.actions.githubusercontent.com",
        "/.github/workflows/release.yml@refs/tags/",
        "SHA256SUMS.cosign.bundle",
        "verify-blob",
        "--certificate-identity",
        "--certificate-oidc-issuer",
        "'auto', 'release', 'signature' or 'checksum'",
        "needs cosign on PATH",
        "--certificate-github-workflow-sha",
        "cosign could not confirm that the",
        "signed SHA256SUMS in a run on the signed tag's commit",
        "(possible tampering). Aborting before anything is extracted.",
        "cosign: SHA256SUMS is signed by the",
        "release workflow, in a run on the tag's commit",
        "holds no Apothem install; refusing to replace it.",
        "or SHA256SUMS.sig as early releases name it",
        "Set APOTHEM_VERIFY=signature to check the release tag alone.",
        "Verifying the ",
        "fetch --quiet --depth=1 --no-tags",
        "gpg not found",
        "release tag's signature against the maintainer key",
    ):
        assert phrase in SH, f"install.sh lacks {phrase!r}"
        assert phrase in PS1, f"install.ps1 lacks {phrase!r}"


@pytest.mark.parametrize("name", sorted(SCRIPTS))
def test_no_script_reads_the_signing_certificate_itself(name: str) -> None:
    """cosign checks the tag's commit against the certificate it verified
    (``--certificate-github-workflow-sha``); no script parses the bundle or
    cites Fulcio's Build Config Digest extension (OID 1.3.6.1.4.1.57264.1.19)
    as a source commit, which is what the removed hand-written parsers did."""
    content = SCRIPTS[name]
    for removed in (
        "57264.1.19",
        "names no source commit",
        "cert_source_commit",
        "Get-CertSourceCommit",
        "Read-DerItem",
        "BEGIN CERTIFICATE",
    ):
        assert removed not in content, f"{name} still carries {removed!r}"


def test_both_installers_default_to_auto() -> None:
    """``auto`` is the default in both: an unset APOTHEM_VERIFY means the
    cosign path when cosign is present and the key-pinned tag check otherwise."""
    assert 'APOTHEM_VERIFY="${APOTHEM_VERIFY:-auto}"' in SH
    assert "else { 'auto' }" in PS1


@pytest.mark.parametrize(
    ("name", "installer"), [("update.sh", "install.sh"), ("update.ps1", "install.ps1")]
)
def test_updaters_point_archive_installs_at_the_installer(
    name: str, installer: str
) -> None:
    """An archive install has no clone, so each updater sends it back to the
    installer instead of claiming no source was found."""
    assert (
        f"Re-run {installer} with cosign and gpg on PATH to update it" in SCRIPTS[name]
    )


#: The -c program text every script runs before the engine, the shims and the
#: dependency probes: it drops a leading '' (the current folder) from
#: sys.path, which Python 3.10 adds even with PYTHONSAFEPATH=1 set.
DROP_CWD_FROM_PATH = (
    "import sys; sys.path[:1] = [] if sys.path[:1] == [''] else sys.path[:1]"
)
RUN_ENGINE = (
    "; import runpy; runpy.run_module('apothem', run_name='__main__', alter_sys=True)"
)


@pytest.mark.parametrize("name", sorted(SCRIPTS))
def test_every_script_keeps_the_current_folder_off_sys_path(name: str) -> None:
    """No Python start that imports click, rich or apothem has the current
    folder on sys.path: each script sets PYTHONSAFEPATH=1 and runs the same
    -c program, and no engine start or probe uses ``-m apothem`` or a bare
    ``-c "import ..."`` (both put the current folder first)."""
    content = SCRIPTS[name]
    assert DROP_CWD_FROM_PATH in content, f"{name} lacks the sys.path guard"
    assert RUN_ENGINE in content, f"{name} does not run the engine through runpy"
    safe_path = "PYTHONSAFEPATH=1" if name.endswith(".sh") else "PYTHONSAFEPATH = '1'"
    assert safe_path in content, f"{name} does not set PYTHONSAFEPATH"
    for unsafe in (
        r'"\$PY" -m apothem',
        r"& \$PY -m apothem",
        r'exec "%s" -m apothem',
        r" -m apothem %\*",
        r'-c "import \$\{?_?[dD]ep\}?"',
        r'-c "import \$Module"',
    ):
        assert not re.search(unsafe, content), f"{name} still runs {unsafe!r}"


@pytest.mark.parametrize("name", ["uninstall.sh", "uninstall.ps1"])
def test_the_uninstallers_keep_the_current_folder_off_sys_path(name: str) -> None:
    """The uninstallers start the engine the way the installers do: with
    PYTHONSAFEPATH=1 and the same -c program, never ``-m apothem``."""
    content = (INSTALLER / name).read_text(encoding="utf-8")
    assert DROP_CWD_FROM_PATH in content, f"{name} lacks the sys.path guard"
    assert RUN_ENGINE in content, f"{name} does not run the engine through runpy"
    safe_path = "PYTHONSAFEPATH=1" if name.endswith(".sh") else "PYTHONSAFEPATH = '1'"
    assert safe_path in content, f"{name} does not set PYTHONSAFEPATH"
    for unsafe in (r'"\$PY" -m apothem', r"& \$PY -m apothem"):
        assert not re.search(unsafe, content), f"{name} still runs {unsafe!r}"


@pytest.mark.parametrize("name", ["install.ps1", "update.ps1", "uninstall.ps1"])
def test_the_powershell_scripts_drop_empty_and_relative_pythonpath_entries(
    name: str,
) -> None:
    """Each PowerShell engine start builds PYTHONPATH with Get-SafePythonPath,
    which keeps only the caller's full-path entries; none prepends the engine
    paths to the caller's raw value."""
    content = (INSTALLER / name).read_text(encoding="utf-8")
    assert "Get-SafePythonPath $EnginePyPath $PriorPyPath" in content
    assert "$EnginePyPath$([System.IO.Path]::PathSeparator)$PriorPyPath" not in content


def _powershell_shim_body() -> str:
    """The apothem.cmd text install.ps1 writes, before its variables expand."""
    match = re.search(r'\$ShimBody = @"\r?\n(.*?)\r?\n"@', PS1, re.DOTALL)
    assert match, "install.ps1 no longer builds $ShimBody from a here-string"
    return match.group(1).replace("\r\n", "\n")


#: The program the apothem.cmd shim runs: the sys.path guard, then the
#: caller's full-path PYTHONPATH entries (handed over in
#: APOTHEM_USER_PYTHONPATH, kept by the one full-path rule) inserted right
#: after the engine paths on sys.path and in PYTHONPATH, then the engine.
SHIM_PROGRAM = (
    DROP_CWD_FROM_PATH + "; import os, re; e = os.environ.get('PYTHONPATH', '');"
    " n = len(e.split(os.pathsep)) if e else 0;"
    " k = [p for p in dict.fromkeys(os.environ.pop('APOTHEM_USER_PYTHONPATH',"
    " '').split(os.pathsep)) if re.match('([A-Za-z]:[\\\\\\\\/]|[\\\\\\\\/]{2})', p)"
    " and p not in sys.path[:n]]; sys.path[n:n] = k;"
    " os.environ['PYTHONPATH'] = os.pathsep.join(([e] if e else []) + k)" + RUN_ENGINE
)


def _powershell_shim_program() -> str:
    """The $ShimProgram install.ps1 defines, with $DropCwdFromPath expanded."""
    match = re.search(r'^\$ShimProgram = "(.*)"\r?$', PS1, re.MULTILINE)
    assert match, "install.ps1 no longer defines $ShimProgram"
    return match.group(1).replace("$DropCwdFromPath", DROP_CWD_FROM_PATH)


def test_the_powershell_shim_keeps_the_current_folder_off_sys_path() -> None:
    """The apothem.cmd shim install.ps1 writes sets PYTHONSAFEPATH=1, sets
    PYTHONPATH to the engine paths only (a batch file cannot drop the
    caller's empty and relative entries, which Python reads as the current
    folder), and hands the caller's value to a program that keeps only its
    full-path entries. The program holds no double quote or percent sign,
    which the batch line would read."""
    body = _powershell_shim_body()
    assert 'set "PYTHONSAFEPATH=1"' in body
    assert 'set "APOTHEM_USER_PYTHONPATH=%PYTHONPATH%"' in body
    assert 'set "PYTHONPATH=$EnginePyPath"\n' in body + "\n"
    assert '"$PY" -c "$ShimProgram" %*' in body
    assert body.index("APOTHEM_USER_PYTHONPATH=") < body.index('"PYTHONPATH=')
    assert body.count("%PYTHONPATH%") == 1, "the shim passes PYTHONPATH on raw"
    program = _powershell_shim_program()
    assert program == SHIM_PROGRAM
    assert '"' not in program
    assert "%" not in program
    # Delayed expansion is off, so a `!` is never read as a variable.
    assert body.startswith("@echo off\nsetlocal DisableDelayedExpansion\n")


@pytest.mark.parametrize("name", ["install.ps1", "update.ps1", "uninstall.ps1"])
def test_the_powershell_scripts_make_a_relative_apothem_home_a_full_path(
    name: str,
) -> None:
    """A relative APOTHEM_HOME is resolved right after it is read, so the
    engine paths built from it (in PYTHONPATH and in the shim) are full
    paths, never ones Python would read against the folder it starts in."""
    content = (INSTALLER / name).read_text(encoding="utf-8")
    read = (
        "$ApothemHome = if ($env:APOTHEM_HOME) { $env:APOTHEM_HOME } "
        "else { Join-Path $HOME '.apothem' }"
    )
    resolve = (
        "$ApothemHome = $ExecutionContext.SessionState.Path"
        ".GetUnresolvedProviderPathFromPSPath($ApothemHomeValue, "
        "[ref]$HomeProvider, [ref]$HomeDrive)"
    )
    assert read in content
    assert resolve in content
    between = content[content.index(read) : content.index(resolve)]
    assert "$ApothemHome" not in between[len(read) :].replace(
        "$ApothemHomeValue = $ApothemHome", ""
    ).replace("$ApothemHomeValue", ""), f"{name} uses APOTHEM_HOME before resolving it"
    # Relative values are read against the file-system location, and a
    # value that names no folder path stops the run.
    assert (
        "Push-Location -LiteralPath (Get-Location -PSProvider FileSystem).ProviderPath"
        in between
    )
    after = content[content.index(resolve) :]
    assert "$HomeProvider.Name -ne 'FileSystem'" in after
    assert "APOTHEM_HOME is not a usable folder path: $ApothemHomeValue" in after


def test_the_installers_next_step_banners_do_not_suggest_dash_m_apothem() -> None:
    """With no apothem command on PATH, both banners point at the shim by its
    full path, or else at the guarded -c form, with the same wording; neither
    suggests ``-m apothem``, which puts the current folder first."""
    for phrase in (
        "Until then, run the apothem command by its full path:",
        "the current folder is kept off sys.path):",
        "then run the guided setup: apothem quickstart",
    ):
        assert phrase in SH, f"install.sh lacks {phrase!r}"
        assert phrase in PS1, f"install.ps1 lacks {phrase!r}"
    for started in ("-m apothem <command>", "-m apothem quickstart"):
        assert started not in PS1, f"install.ps1 suggests {started!r}"
    # A one-shot block that puts PYTHONPATH and PYTHONSAFEPATH back when the
    # command ends, so the session keeps its own values.
    assert (
        "& { `$PriorPath = `$env:PYTHONPATH; `$PriorSafe = `$env:PYTHONSAFEPATH; "
        "`$env:PYTHONSAFEPATH = '1'; "
        "`$env:PYTHONPATH = $(ConvertTo-PsLiteral $EnginePyPath); "
        'try { & $(ConvertTo-PsLiteral $PY) -c `"$EngineProgram`" @args } finally { '
        "`$env:PYTHONPATH = `$PriorPath; `$env:PYTHONSAFEPATH = `$PriorSafe } }"
    ) in PS1
    # Every path the PowerShell banner prints is a quoted literal, its own
    # quotes doubled, so a path holding a quote still pastes as a command.
    assert '$RunCmd = "& $(ConvertTo-PsLiteral $Shim)"' in PS1
    assert '$(ConvertTo-PsLiteral "$BinDir;") + `$env:Path' in PS1
    assert "'$BinDir" not in PS1
    assert "'$Shim'" not in PS1


#: The shim releases 1.0.1 to 1.5.0 wrote; uninstall.ps1 still removes it.
OLD_POWERSHELL_SHIM = (
    "@echo off\nsetlocal\n"
    'set "PYTHONPATH=C:\\h\\src\\apothem\\_vendor;C:\\h\\src;%PYTHONPATH%"\n'
    '"C:\\Python\\python.exe" -m apothem %*\n'
)
OPERATOR_SHIM = "@echo off\nrem apothem launcher\nC:\\tools\\apothem.exe %*\n"


@pytest.mark.parametrize("newline", ["\r\n", "\n"], ids=["crlf", "lf"])
def test_the_uninstaller_recognises_the_shims_install_ps1_writes(newline: str) -> None:
    """uninstall.ps1 removes apothem.cmd only when it is Apothem's: its
    patterns match the shim install.ps1 writes now and the one older releases
    wrote, and not an operator's own apothem.cmd."""
    uninstall = (INSTALLER / "uninstall.ps1").read_text(encoding="utf-8")
    block = re.search(
        r"\$ShimIsOurs = (.*?)\r?\n    if \(\$ShimIsOurs\)", uninstall, re.DOTALL
    )
    assert block, "uninstall.ps1 no longer decides through $ShimIsOurs"
    patterns = re.findall(r"-match '([^']*)'", block.group(1))
    assert len(patterns) == 2, patterns
    current = (
        _powershell_shim_body()
        .replace("$EnginePyPath", "C:\\h\\src\\apothem\\_vendor;C:\\h\\src")
        .replace("$PY", "C:\\Python\\python.exe")
        .replace("$ShimProgram", SHIM_PROGRAM)
    )
    assert "$" not in current, current

    def ours(text: str) -> bool:
        text = text.replace("\n", newline)
        return any(re.search(pattern, text) for pattern in patterns)

    assert ours(current), "uninstall.ps1 would leave the shim install.ps1 writes"
    assert ours(OLD_POWERSHELL_SHIM), "uninstall.ps1 would leave a 1.5.0 shim"
    assert not ours(OPERATOR_SHIM), "uninstall.ps1 would remove an operator's command"


def test_both_installers_find_a_local_tree_only_by_their_own_path() -> None:
    """A local tree is APOTHEM_SOURCE or the checkout the script file sits in
    (scripts/installer); neither installer falls back to the current folder
    or walks its parents, and both say the same thing when they use one."""
    for phrase in (
        "Using explicit source: ",
        "Using local checkout: ",
        "skipping tag resolution and signature verification",
    ):
        assert phrase in SH, f"install.sh lacks {phrase!r}"
        assert phrase in PS1, f"install.ps1 lacks {phrase!r}"
    assert "_walk" not in SH, "install.sh still walks parent folders"
    assert 'dirname "$0"' not in SH, "install.sh still derives a folder from $0"
    assert "*/scripts/installer)" in SH
    assert "$Walk" not in PS1, "install.ps1 still walks parent folders"
    assert "PSScriptRoot" not in PS1, "install.ps1 still falls back to the cwd"
    assert "$PSCommandPath" in PS1
    assert "-ne 'installer'" in PS1
