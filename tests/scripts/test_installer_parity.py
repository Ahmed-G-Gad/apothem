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
    closing ``}`` at column 0 (or, for a subshell body, from ``NAME() (`` to
    the closing ``)`` at column 0), as SCRIPT carries it."""
    match = re.search(
        rf"^{name}\(\) (?:\{{\n.*?^\}}|\(\n.*?^\))$", script, re.MULTILINE | re.DOTALL
    )
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
    PATH. Like the PowerShell stub, it prints nothing unless the script runs
    it through ``ngit``: from an empty folder, with GIT_CEILING_DIRECTORIES
    set, so a repository around the current folder is never read."""
    program = (
        'git() { [ -n "${GIT_CEILING_DIRECTORIES:-}" ] && [ "$(pwd -P)" != "$START" ]'
        " && printf '%s\\n' \"$LS_REMOTE_LINES\"; }\n"
        'START="$(pwd -P)"\n'
        + _sh_function(SCRIPTS[sh_name], "ngit")
        + "\n"
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
        ("install.ps1", PS1, 'Save-Download "$ApothemReleaseBase'),
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
        "A release tag must be signed by the maintainer key",
        "that SECURITY.md publishes, and by no other key (possible tampering). "
        "Aborting before anything is checked out or " + after,
        "the keys ",
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
        "is not the work tree of its git clone (git finds no work tree there, as "
        "when its git config sets core.bare to true). Set core.bare to false, then "
        "re-run.",
        "'s own git config sets ",
        ", which an update in place does not accept in a clone's own config. "
        "Remove it from ",
        " keeps submodule repositories in ",
        ". A release tree has no submodules, and the update would run git "
        "inside them. Remove the submodules and ",
        " holds a submodule at ",
        " (its index records a git repository there). A release tree has none, "
        "and the update would run git inside it. Remove the submodule from the "
        "clone, then re-run.",
        "ls-files -s",
        "160000",
        "--get-all extensions.refstorage",
        "'s own git attributes set a filter (filter=), which the update would "
        "trust. Remove it from ",
        "Could not read the git config of ",
        "config --file ",
        "--name-only --list",
        "config.worktree",
        "info/attributes",
        "rev-parse --git-path",
        " is owned by someone else, so git refuses to work in it (git reports ",
        "dubious ownership",
        "Run this as the user who owns ",
        ", take ownership of it, or point APOTHEM_HOME at a folder you own, "
        "then re-run.",
        "git could not read the clone at ",
        "Repair it or move it aside, then re-run.",
        "rev-parse --git-dir",
        "LC_ALL",
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
    "GIT_CONFIG",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_SYSTEM",
)

#: The git variables every script leaves as the caller set them:
#: GIT_CONFIG_NOSYSTEM only makes git skip the system configuration.
KEPT_GIT_VARIABLES = ("GIT_CONFIG_NOSYSTEM",)


def _cleared_git_variables(name: str, content: str) -> set[str]:
    """The names SCRIPT's startup statement clears: install.sh and update.sh
    `unset` them (with continued lines), the .ps1 scripts loop over them."""
    if name.endswith(".sh"):
        match = re.search(
            r"^unset GIT_DIR(?:[^\n]*\\\n)*[^\n]*$", content, re.MULTILINE
        )
    else:
        match = re.search(
            r"^foreach \(\$GitVar in @\(([^)]*)\)\)", content, re.MULTILINE
        )
    assert match, f"{name} no longer clears the git variables in one statement"
    return set(re.findall(r"\bGIT_[A-Z_]+\b", match.group(0)))


@pytest.mark.parametrize("name", sorted(SCRIPTS))
def test_every_script_clears_the_git_environment_and_checks_the_repo(
    name: str,
) -> None:
    """All four scripts clear the same git variables, keep
    GIT_CONFIG_NOSYSTEM (it only narrows what git reads), turn replace refs
    off, refuse an APOTHEM_REPO that reads as an option in the same words,
    and look for the gpg program git runs in the same order."""
    content = SCRIPTS[name]
    cleared = _cleared_git_variables(name, content)
    for variable in CLEARED_GIT_VARIABLES:
        assert variable in cleared, f"{name} does not clear {variable}"
    for variable in KEPT_GIT_VARIABLES:
        assert variable not in cleared, f"{name} clears {variable}"
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
    assert "A release tag must be signed by the maintainer key" in content, (
        f"{name} lacks the other-key abort"
    )
    assert "carries a valid signature, but not from the maintainer key" not in content


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


#: Each pair beside its third member: the uninstallers take the same lock.
SCRIPT_TRIOS: tuple[tuple[str, str], ...] = (
    ("install.sh", "install.ps1"),
    ("update.sh", "update.ps1"),
    ("uninstall.sh", "uninstall.ps1"),
)


def _script(name: str) -> str:
    return (INSTALLER / name).read_text(encoding="utf-8")


def _posix_sh() -> str | None:
    """A POSIX sh to run the sh scripts' functions: Git for Windows' sh on
    Windows (found from git on PATH, never WSL's), else sh on PATH."""
    if sys.platform != "win32":
        return shutil.which("sh")
    git = shutil.which("git")
    if git is None:
        return None
    for root in Path(git).resolve().parents[:3]:
        for candidate in (root / "usr" / "bin" / "sh.exe", root / "bin" / "sh.exe"):
            if candidate.is_file():
                return str(candidate)
    return None


_SH = _posix_sh()


def _sh_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """The environment for a run of _SH: BASE (or this process's own), with
    _SH's own folder first on PATH on Windows, so the scripts' sort, tr and
    the rest are Git's and never Windows' own sort.exe (which ends lines with
    CRLF and ignores case) that a PowerShell PATH lists first."""
    env = dict(os.environ if base is None else base)
    if sys.platform == "win32" and _SH is not None:
        env["PATH"] = str(Path(_SH).parent) + os.pathsep + env.get("PATH", "")
    return env


requires_posix_sh = pytest.mark.skipif(_SH is None, reason="no POSIX sh on this host")
requires_powershell = pytest.mark.skipif(
    _PWSH is None, reason="no PowerShell on this host"
)

#: The settings a clone's own git config may hold for an update in place,
#: in the order every script lists them (the round-2 spec, section 1.1).
CLONE_CONFIG_ALLOW: tuple[str, ...] = (
    "core.repositoryformatversion",
    "core.filemode",
    "core.bare",
    "core.logallrefupdates",
    "core.symlinks",
    "core.ignorecase",
    "core.precomposeunicode",
    "core.longpaths",
    "core.partialclonefilter",
    "extensions.objectformat",
    "extensions.refstorage",
    "extensions.partialclone",
    "extensions.worktreeconfig",
    "remote.origin.url",
    "remote.origin.fetch",
    "remote.origin.tagopt",
    "remote.origin.promisor",
    "remote.origin.partialclonefilter",
    "branch.*.*",
    "user.name",
    "user.email",
    "maintenance.auto",
    "maintenance.strategy",
    "pull.rebase",
    "pull.ff",
)

ALLOW_BEGIN = "# clone-config-allow-list begin"
ALLOW_END = "# clone-config-allow-list end"


def _allow_list_block(name: str) -> str:
    """The lines between the allow-list markers in script NAME."""
    content = _script(name)
    assert content.count(ALLOW_BEGIN) == 1, f"{name}: no single allow-list start"
    assert content.count(ALLOW_END) == 1, f"{name}: no single allow-list end"
    return content.split(ALLOW_BEGIN, 1)[1].split(ALLOW_END, 1)[0]


def _allow_list(name: str) -> list[str]:
    """The entries of script NAME's allow-list, in order: its tokens made of
    lower-case letters, digits, '*', '.' and '-', once the quotes and the
    CLONE_CONFIG_ALLOW= / $CloneConfigAllow = @( / ) wrappers are gone."""
    block = _allow_list_block(name)
    block = block.replace("CLONE_CONFIG_ALLOW=", " ").replace(
        "$CloneConfigAllow = @(", " "
    )
    block = block.replace("'", " ").replace('"', " ").replace(")", " ")
    tokens = block.split()
    for token in tokens:
        assert re.fullmatch(r"[a-z0-9*.-]+", token), f"{name}: odd entry {token!r}"
    return tokens


@pytest.mark.parametrize(
    "name", ["install.sh", "update.sh", "install.ps1", "update.ps1"]
)
def test_every_script_holds_the_same_clone_config_allow_list(name: str) -> None:
    """install.sh, update.sh, install.ps1 and update.ps1 each hold the list
    of settings a clone's own config may hold, once, in the same order."""
    assert _allow_list(name) == list(CLONE_CONFIG_ALLOW)


#: Setting names as `git config --name-only --list` prints them, and
#: whether a clone's own config may hold them (True) or stops the update
#: (False). Both families must give these answers.
CONFIG_KEY_CASES: tuple[tuple[str, bool], ...] = (
    *((key, True) for key in CLONE_CONFIG_ALLOW if "*" not in key),
    ("Core.Bare", True),
    ("USER.NAME", True),
    ("branch.main.merge", True),
    ("branch.main.remote", True),
    ("branch.Main.Merge", True),
    ("branch.feature.x.remote", True),
    ("branch.a b.description", True),
    ("branch..merge", False),
    ("branch.autosetupmerge", False),
    ("branch.main.", False),
    ("user.foo.name", False),
    ("remote.Origin.url", False),
    # PowerShell's -ceq passes these as origin: a soft hyphen, a zero-width
    # space.
    ("remote.ori­gin.url", False),
    ("remote.origin​.promisor", False),
    ("branch.m­ain.merge", True),
    ("remote.upstream.url", False),
    ("remote.origin.pushurl", False),
    ("remote.origin.uploadpack", False),
    ("remote.origin.mirror", False),
    ("hook.evil.command", False),
    ("hook.evil.event", False),
    ("gc.recentobjectshook", False),
    ("gc.auto", False),
    ("pager.fetch", False),
    ("core.pager", False),
    ("core.editor", False),
    ("core.fsmonitor", False),
    ("core.hookspath", False),
    ("core.sshcommand", False),
    ("core.worktree", False),
    ("core.autocrlf", False),
    ("core.sparsecheckout", False),
    ("gpg.program", False),
    ("include.path", False),
    ("includeif.gitdir:C:/x/.path", False),
    ("filter.lfs.smudge", False),
    ("merge.evil.driver", False),
    ("diff.evil.textconv", False),
    ("url.ext::sh -c touch.insteadof", False),
    ("http.proxy", False),
    ("credential.helper", False),
    ("protocol.allow", False),
    ("submodule.active", False),
    ("commit.gpgsign", False),
    ("fetch.bundleuri", False),
    ("extensions.relativeworktrees", False),
    ("lfs.repositoryformatversion", False),
    ("nodot", False),
    (".bare", False),
    ("core.", False),
)


def _sh_allow_program(name: str) -> str:
    """sh source that defines script NAME's allow-list and its
    unallowed_config_key."""
    return (
        _allow_list_block(name)
        + "\n"
        + _sh_function(SCRIPTS[name], "unallowed_config_key")
        + "\n"
    )


@requires_posix_sh
@pytest.mark.parametrize("sh_name", ["install.sh", "update.sh"])
def test_sh_allows_exactly_the_clone_settings_the_table_allows(sh_name: str) -> None:
    """Each sh script's own unallowed_config_key, run under sh, lets through
    exactly the settings CONFIG_KEY_CASES allows: section and key compared
    without regard to case, the name between them exactly."""
    assert _SH is not None
    keys = [key for key, _ in CONFIG_KEY_CASES]
    program = (
        _sh_allow_program(sh_name)
        + 'for key in "$@"; do\n'
        + '    if [ -n "$(printf \'%s\\n\' "$key" | unallowed_config_key)" ]; '
        + "then echo refused; else echo allowed; fi\n"
        + "done\n"
    )
    result = subprocess.run(
        [_SH, "-c", program, "sh", *keys],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=_sh_env(),
    )
    assert result.returncode == 0, result.stderr
    verdicts = dict(zip(keys, result.stdout.splitlines(), strict=True))
    wrong = {
        key: verdicts[key]
        for key, allowed in CONFIG_KEY_CASES
        if (verdicts[key] == "allowed") != allowed
    }
    assert not wrong, f"{sh_name}'s unallowed_config_key disagrees: {wrong}"


def _ps1_define(*names: str) -> tuple[str, ...]:
    """PowerShell statements that parse the script named by
    ``$env:RELEASE_TAG_SCRIPT`` and define, in this session, each of its
    functions and script variables NAMES (a name starting with '$' is a
    variable, whose assignment statement runs). Nothing else in the script
    runs."""
    statements = [
        "Set-StrictMode -Version Latest",
        "$ErrorActionPreference = 'Stop'",
        "$tokens = $null",
        "$parseErrors = $null",
        "$ast = [Management.Automation.Language.Parser]::ParseFile("
        "$env:RELEASE_TAG_SCRIPT, [ref]$tokens, [ref]$parseErrors)",
        "if ($parseErrors) { throw ($parseErrors -join ' | ') }",
    ]
    for name in names:
        if name.startswith("$"):
            find = (
                "$node -is [Management.Automation.Language.AssignmentStatementAst] "
                f"-and $node.Left.Extent.Text -eq '{name}'"
            )
        else:
            find = (
                "$node -is [Management.Automation.Language.FunctionDefinitionAst] "
                f"-and $node.Name -eq '{name}'"
            )
        statements += [
            f"$found = $ast.Find({{ param($node) {find} }}, $true)",
            f"if (-not $found) {{ throw 'no {name} in the script' }}",
            ". ([scriptblock]::Create($found.Extent.Text))",
        ]
    return tuple(statements)


@requires_powershell
@pytest.mark.parametrize("ps1_name", ["install.ps1", "update.ps1"])
def test_powershell_allows_exactly_the_clone_settings_the_table_allows(
    ps1_name: str,
) -> None:
    """Each .ps1 script's own Test-AllowedConfigKey, run under PowerShell
    with the script's own $CloneConfigAllow, lets through exactly the
    settings CONFIG_KEY_CASES allows."""
    keys = [key for key, _ in CONFIG_KEY_CASES]
    program = "; ".join(
        (
            *_ps1_define("$CloneConfigAllow", "Test-AllowedConfigKey"),
            "foreach ($key in ($env:CONFIG_KEYS | ConvertFrom-Json)) "
            "{ if (Test-AllowedConfigKey $key) { 'allowed' } else { 'refused' } }",
        )
    )
    result = _run_powershell(program, ps1_name, CONFIG_KEYS=json.dumps(keys))
    assert result.returncode == 0, result.stdout + result.stderr
    verdicts = dict(zip(keys, result.stdout.splitlines(), strict=True))
    wrong = {
        key: verdicts[key]
        for key, allowed in CONFIG_KEY_CASES
        if (verdicts[key] == "allowed") != allowed
    }
    assert not wrong, f"{ps1_name}'s Test-AllowedConfigKey disagrees: {wrong}"


#: A clone's own config file and the setting the check names in it (None
#: when the file passes): the first failing name in file order, and
#: extensions.refstorage when a value of it is not exactly files or
#: reftable (a later git reads refs from a folder such a value names).
CONFIG_FILE_CASES: tuple[tuple[str, str, str | None], ...] = (
    ("reftable", "[extensions]\n\trefstorage = reftable\n", None),
    ("files", "[extensions]\n\trefstorage = files\n", None),
    ("folder", "[extensions]\n\trefstorage = reftable://x\n", "extensions.refstorage"),
    ("case", "[extensions]\n\trefstorage = Files\n", "extensions.refstorage"),
    ("empty", "[extensions]\n\trefstorage =\n", "extensions.refstorage"),
    (
        "two-values",
        "[extensions]\n\trefstorage = files\n\trefstorage = reftable:x\n",
        "extensions.refstorage",
    ),
    (
        "line-break",
        '[extensions]\n\trefstorage = "files\\nreftable"\n',
        "extensions.refstorage",
    ),
    (
        "refstorage-first",
        "[extensions]\n\trefstorage = x://y\n[core]\n\tpager = less\n",
        "extensions.refstorage",
    ),
    (
        "pager-first",
        "[core]\n\tpager = less\n[extensions]\n\trefstorage = x://y\n",
        "core.pager",
    ),
    ("branch", '[branch "main"]\n\tremote = origin\n\tmerge = refs/heads/main\n', None),
    ("hook", '[hook "x"]\n\tcommand = touch y\n', "hook.x.command"),
)


def _clone_with_config(root: Path, text: str) -> str:
    """A folder ROOT holding .git/config with what git init writes, then
    TEXT; return its path with forward slashes, as both families get it.
    It is not a repository git would open (a value such as a reftable://
    refstorage would stop git there), so the tests give each family a
    git_path / Get-ClonePath that names ROOT/.git/<name>."""
    (root / ".git").mkdir(parents=True)
    (root / ".git" / "config").write_text(
        "[core]\n\trepositoryformatversion = 0\n\tfilemode = false\n"
        "\tbare = false\n\tlogallrefupdates = true\n" + text,
        encoding="utf-8",
        newline="\n",
    )
    return root.as_posix()


def _config_message(home: str, key: str) -> str:
    return (
        f"{home}'s own git config sets {key}, which an update in place does not "
        f"accept in a clone's own config. Remove it from {home}/.git/config, "
        "then re-run."
    )


@requires_posix_sh
@pytest.mark.parametrize("sh_name", ["install.sh", "update.sh"])
@pytest.mark.parametrize(
    ("case", "text", "named"), CONFIG_FILE_CASES, ids=[c[0] for c in CONFIG_FILE_CASES]
)
def test_sh_checks_a_clones_own_config_file(
    tmp_path: Path, sh_name: str, case: str, text: str, named: str | None
) -> None:
    """Each sh script's check_clone_config, run on a clone, names the first
    setting in file order its config may not hold, extensions.refstorage
    with a value that names a folder included, or passes the clone."""
    assert _SH is not None
    home = _clone_with_config(tmp_path / "clone", text)
    program = (
        "die() { printf '%s\\n' \"$*\"; exit 1; }\n"
        "git_path() { printf '%s\\n' \"$1/.git/$2\"; }\n"
        + _sh_function(SCRIPTS[sh_name], "cgit")
        + "\nHOOKS_OFF=\n"
        + _sh_allow_program(sh_name)
        + _sh_function(SCRIPTS[sh_name], "config_file_problem")
        + "\n"
        + _sh_function(SCRIPTS[sh_name], "check_clone_config")
        + '\ncheck_clone_config "$1"\necho passed\n'
    )
    result = subprocess.run(
        [_SH, "-c", program, "sh", home],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=_sh_env(_git_env_without_user_config()),
    )
    expected = "passed" if named is None else _config_message(home, named)
    assert result.stdout.strip() == expected, result.stdout + result.stderr


@requires_powershell
@pytest.mark.parametrize("ps1_name", ["install.ps1", "update.ps1"])
@pytest.mark.parametrize(
    ("case", "text", "named"), CONFIG_FILE_CASES, ids=[c[0] for c in CONFIG_FILE_CASES]
)
def test_powershell_checks_a_clones_own_config_file(
    tmp_path: Path, ps1_name: str, case: str, text: str, named: str | None
) -> None:
    """Each .ps1 script's Assert-CloneConfig gives the same verdict, and the
    same message, as the sh scripts' check_clone_config."""
    home = _clone_with_config(tmp_path / "clone", text)
    program = "; ".join(
        (
            *_ps1_define(
                "$GitNoProgram",
                "$CloneConfigAllow",
                "Test-AllowedConfigKey",
                "Assert-CloneConfig",
            ),
            "function Write-Fail { param([string]$Msg) throw $Msg }",
            "function Get-ClonePath { param([string]$Dir, [string]$Name) "
            '"$Dir/.git/$Name" }',
            "try { Assert-CloneConfig $env:CLONE_HOME; 'passed' } "
            "catch { $_.Exception.Message }",
        )
    )
    result = _run_powershell(program, ps1_name, CLONE_HOME=home, **_git_env_overrides())
    expected = "passed" if named is None else _config_message(home, named)
    assert result.stdout.strip() == expected, result.stdout + result.stderr


def _git_env_overrides() -> dict[str, str]:
    """Settings that keep the user's own git config out of these checks."""
    return {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def _git_env_without_user_config() -> dict[str, str]:
    return {**os.environ, **_git_env_overrides()}


#: The settings every git command on an existing clone runs with: no
#: fsmonitor program, only the file, git, http, https and ssh transports
#: (no ext:: and no other remote helper), no recursion into submodules, no
#: git status run inside a nested repository, no automatic maintenance,
#: and paths longer than Windows' usual limit written at checkout.
GIT_NO_PROGRAM_SETTINGS = (
    "core.fsmonitor=",
    "protocol.ext.allow=never",
    "protocol.allow=never",
    "protocol.file.allow=always",
    "protocol.git.allow=always",
    "protocol.http.allow=always",
    "protocol.https.allow=always",
    "protocol.ssh.allow=always",
    "submodule.recurse=false",
    "fetch.recurseSubmodules=false",
    "diff.ignoreSubmodules=all",
    "gc.auto=0",
    "maintenance.auto=false",
    "core.longpaths=true",
)


@pytest.mark.parametrize(("sh_name", "ps1_name"), RELEASE_TAG_PAIRS)
def test_git_runs_on_a_clone_with_the_same_settings_in_both(
    sh_name: str, ps1_name: str
) -> None:
    """install.sh's and update.sh's cgit and the .ps1 scripts' $GitNoProgram
    pass the same -c settings and --no-pager, and the .ps1 scripts add the
    empty hooks folder on the update's calls as cgit does."""
    cgit = _sh_function(SCRIPTS[sh_name], "cgit")
    match = re.search(
        r"^\$GitNoProgram = @\((.*)\)\r?$", SCRIPTS[ps1_name], re.MULTILINE
    )
    assert match, f"{ps1_name} no longer defines $GitNoProgram"
    assert cgit.count("git --no-pager ") == 2, f"{sh_name}'s cgit lacks --no-pager"
    assert "'--no-pager'" in match.group(1), f"{ps1_name} lacks --no-pager"
    for setting in GIT_NO_PROGRAM_SETTINGS:
        assert cgit.count(f"-c {setting}") == 2, f"{sh_name}'s cgit lacks -c {setting}"
        assert f"'-c', '{setting}'" in match.group(1), (
            f"{ps1_name}'s $GitNoProgram lacks -c {setting}"
        )
    assert '-c core.hooksPath="$HOOKS_OFF"' in cgit
    assert (
        "$GitSafe = @($GitNoProgram + @('-c', \"core.hooksPath=$NoHooksDir\"))"
        in SCRIPTS[ps1_name]
    )


def _in_order(body: str, *steps: str) -> bool:
    """Each of STEPS appears in BODY, each after the one before."""
    found = [body.find(step) for step in steps]
    return -1 not in found and found == sorted(found)


@pytest.mark.parametrize(
    ("sh_name", "ps1_name"),
    [("install.sh", "install.ps1"), ("update.sh", "update.ps1")],
)
def test_a_clone_is_checked_in_the_same_order_in_both(
    sh_name: str, ps1_name: str
) -> None:
    """git is asked first whether it works in the clone at all (another
    user's clone is refused), then the clone's own settings and attributes
    are checked, and only then does any command read its index (ls-files
    -v)."""
    sh_body = _sh_function(SCRIPTS[sh_name], "check_clone_setup")
    ps1_body = _ps1_function(SCRIPTS[ps1_name], "Assert-CleanClone")
    assert _in_order(
        sh_body,
        "clone_git_ok",
        "check_clone_config",
        "check_clone_modules",
        "is not the work tree",
        "check_clone_gitlinks",
        "ls-files -v",
    )
    assert _in_order(
        ps1_body, "Assert-CloneGit $Dir", "Assert-CloneConfig $Dir", "ls-files -v"
    )
    assert _in_order(
        ps1_body,
        "Assert-CloneConfig $Dir",
        "keeps submodule repositories in",
        "is not the work tree",
        "if ($CcStagesCode -ne 0)",
        "holds a submodule at",
        "if ($CcFlagsCode -ne 0)",
        "[char]::IsLower",
    )


def test_the_check_for_local_work_runs_git_with_the_same_settings_in_both() -> None:
    """Every git command clone_has_local_work and Test-CloneHasLocalWork run
    on a clone they may replace goes through cgit / $GitNoProgram, so git
    status there runs no fsmonitor or pager, starts no maintenance, and runs
    no git status inside a nested repository."""
    sh_body = _sh_function(SH, "clone_has_local_work")
    code = "\n".join(
        line for line in sh_body.splitlines() if not line.lstrip().startswith("#")
    )
    calls = re.findall(r"(?<![\w$.-])(c?git) -", code)
    assert calls, "clone_has_local_work runs no git command"
    assert set(calls) == {"cgit"}, calls
    assert sh_body.count("status --porcelain") == 2
    ps1_body = _ps1_function(PS1, "Test-CloneHasLocalWork")
    git_calls = re.findall(r"& git (@\w+)", ps1_body)
    assert git_calls, "Test-CloneHasLocalWork runs no git command"
    assert set(git_calls) <= {"@GitNoProgram", "@GitSafe"}, git_calls
    assert len(re.findall(r"& git ", ps1_body)) == len(git_calls)


def test_replacing_a_clone_checks_it_before_git_status_in_both() -> None:
    """With --yes / -Yes, replacing a clone with the archive asks git status
    whether it holds local work; the clone's own settings are checked first,
    so its fsmonitor program never runs."""
    sh_body = _sh_function(SH, "home_mode")
    ps1_body = _ps1_function(PS1, "Get-HomeMode")
    assert _in_order(
        sh_body,
        'clone_git_ok "$APOTHEM_HOME"',
        'check_clone_config "$APOTHEM_HOME"',
        'clone_has_local_work "$APOTHEM_HOME"',
    )
    assert _in_order(
        ps1_body,
        "Assert-CloneGit $ApothemHome",
        "Assert-CloneConfig $ApothemHome",
        "Test-CloneHasLocalWork $ApothemHome",
    )


@pytest.mark.parametrize(
    ("sh_name", "ps1_name"),
    [("install.sh", "install.ps1"), ("update.sh", "update.ps1")],
)
def test_the_tag_is_read_once_and_its_commit_checked_out_in_both(
    sh_name: str, ps1_name: str
) -> None:
    """Both families read refs/tags/<tag> once, check the tag object it
    named, and check out the commit that check recorded, by its ID: no
    checkout or HEAD comparison resolves the tag's name again."""
    sh, ps1 = SCRIPTS[sh_name], SCRIPTS[ps1_name]
    assert 'rev-parse --verify --quiet "refs/tags/' in sh
    assert 'rev-parse --verify --quiet "refs/tags/$' in ps1
    assert 'checkout --quiet --detach "$TAG_COMMIT"' in sh
    assert re.search(r"checkout --quiet --detach \$(script:)?TagCommit\b", ps1)
    for content, name in ((sh, sh_name), (ps1, ps1_name)):
        assert (
            '^{commit}"' not in content.split("checkout --quiet --detach", 1)[1][:200]
        ), name
        assert not re.search(r"checkout --quiet --detach \"refs/tags/", content), name


#: The lock messages every script prints in the same words.
LOCK_PHRASES = (
    "Another Apothem install, update or uninstall is running on ",
    ". Wait for it to finish, then re-run. If none is running, remove ",
    " exists but names no running process; an Apothem run may have left it "
    "when it was stopped. Check that no Apothem install, update or uninstall "
    "is running, remove ",
    "Could not create the lock ",
    ". Check that you can write to ",
)


@pytest.mark.parametrize(("sh_name", "ps1_name"), SCRIPT_TRIOS)
def test_every_script_takes_the_same_lock(sh_name: str, ps1_name: str) -> None:
    """install, update and uninstall in both families hold
    <APOTHEM_HOME>.lock for the whole run, taken right after the banner, and
    say the same things when another run holds it or it cannot be made.
    sh makes a folder there (with its process ID inside); PowerShell opens a
    file there with no sharing, which the system frees when the run ends."""
    sh, ps1 = _script(sh_name), _script(ps1_name)
    for phrase in LOCK_PHRASES:
        assert phrase in sh, f"{sh_name} lacks {phrase!r}"
        assert phrase in ps1, f"{ps1_name} lacks {phrase!r}"
    assert 'LOCK_DIR="${_tl_home}.lock"' in sh
    assert '$HomeLockPath = "$(Get-LockHome).lock"' in ps1
    assert "$LkParent = Split-Path -Parent $HomeLockPath" in ps1
    assert _ps1_function(ps1, "Get-LockHome") == _ps1_function(PS1, "Get-LockHome")
    assert "([System.IO.FileShare]::None)" in ps1
    banner = re.search(r'^Write-Bold "Apothem [a-z]+"\r?\n', ps1, re.MULTILINE)
    assert banner, f"{ps1_name} has no banner line"
    after = ps1[banner.end() :]
    first_statement = next(
        line for line in after.splitlines() if line.strip() and not line.startswith("#")
    )
    assert first_statement == "Lock-ApothemHome", first_statement
    assert ps1.replace("\r\n", "\n").endswith(
        "} finally {\n    Unlock-ApothemHome\n}\n"
    ), f"{ps1_name} does not let the lock go on every way out"
    assert sh.index("take_lock\n") > sh.index('bold "Apothem ')


#: The leftovers report both installers print in the same words.
LEFTOVER_PHRASES = (
    "An earlier run was stopped part-way and left these folders beside ",
    ": the earlier install that was being replaced, in ",
    ": the new source that was being installed, in ",
    ", with these entries moved into it from ",
    ": could not be read (check its owner and permissions)",
    " (made by an earlier installer that did not record which home it was "
    "for, so it may belong to any Apothem home in ",
    ": check what it holds before you move or remove it)",
    ".apothem-carried-entries",
    ": files from that run (",
    ": empty",
    ": the earlier contents of ",
    ", moved aside, in ",
    "the Apothem home it was made for",
    ": the earlier clone's tree, which that run was keeping, in ",
    ": move it to a folder of your own if you still need it",
    "Nothing was changed. If ",
    " is missing, move the earlier install back to it first. Then move every "
    "entry listed above as moved into a new source back into the home it came "
    "from, remove the folders listed above, and re-run.",
    ".apothem-old.",
    ".apothem-extract.",
    ".apothem-clone.",
)


def test_both_installers_report_leftovers_the_same_way() -> None:
    """A run stopped part-way can leave staging folders beside APOTHEM_HOME;
    both installers name each one and what it holds, change nothing, and
    check only for a fetched install (a local tree swaps nothing)."""
    for phrase in LEFTOVER_PHRASES:
        assert phrase in SH, f"install.sh lacks {phrase!r}"
        assert phrase in PS1, f"install.ps1 lacks {phrase!r}"
    assert 'if [ -z "$LOCAL_KIND" ]; then\n    check_leftovers' in SH
    assert "if (-not $LocalKind) { Assert-NoLeftover }" in PS1


def test_both_installers_make_the_aside_folder_themselves() -> None:
    """An earlier folder is moved into a new <APOTHEM_HOME>.before-apothem-
    <time> folder the run makes itself (mkdir in sh; in PowerShell a rename
    of a folder only the run knows, which fails when the name is taken),
    under its own name, never into a folder found there."""
    claim = _sh_function(SH, "claim_aside")
    assert 'mkdir "$_ca_name"' in claim
    assert 'mkdir "${_ca_name}-$$"' in claim
    aside = _ps1_function(PS1, "New-AsideFolder")
    assert "[System.IO.Directory]::Move($AfTemp" in aside
    assert '@($AfName, "$AfName-$PID")' in aside
    assert '_SW_ASIDE_ITEM="${_SW_ASIDE}/$(basename -- "$APOTHEM_HOME")"' in SH
    assert "$AsideItem = Join-Path $Aside $SwLeaf" in PS1


def test_both_installers_refuse_a_redirect_off_https_only_for_an_https_base() -> None:
    """install.sh limits curl to https (and its redirects) when the release
    base is https://; install.ps1's Save-Download refuses a download from an
    https:// address that ended anywhere else. Another base is used as
    given by both."""
    assert 'https://*) CURL_PROTO="--proto =https --proto-redir =https"' in SH
    download = _ps1_function(PS1, "Save-Download")
    assert (
        "StartsWith('https://', [System.StringComparison]::OrdinalIgnoreCase)"
        in download
    )
    assert "$Final.Scheme -ne 'https'" in download


#: What the sh scripts say when <APOTHEM_HOME>.lock is a file where a
#: PowerShell run can hold one: the lock of a PowerShell run, which Windows
#: removes when that run ends.
POWERSHELL_LOCK_PHRASES = (
    " is the lock file of an Apothem PowerShell run (install.ps1, update.ps1 "
    "or uninstall.ps1) on ",
    ", and Windows removes it when that run ends; while the run is active, "
    "Windows will not let anyone remove it. Wait for that run to finish, then "
    "re-run. If no Apothem install, update or uninstall is running, remove ",
)
#: What they say for a file there anywhere else, and for a lock folder made
#: in another environment, whose process cannot be checked from here.
OTHER_LOCK_PHRASES = (
    " is a file where the Apothem lock folder belongs. If no Apothem install, "
    "update or uninstall is running, remove ",
    " was made by an Apothem run in another environment (such as WSL, Git Bash "
    "or a container), so whether its process ",
    " still runs cannot be checked from here. Wait for that run to finish, then "
    "re-run. If no Apothem install, update or uninstall is running anywhere, "
    "remove ",
)


@pytest.mark.parametrize("sh_name", ["install.sh", "update.sh", "uninstall.sh"])
def test_the_sh_scripts_name_a_lock_file_as_a_powershell_runs(sh_name: str) -> None:
    """A lock that is a file, not a folder, is held by install.ps1, update.ps1
    or uninstall.ps1 where those can run: the sh scripts say so, before they
    look for a process ID in it, and a symbolic link there keeps the "names
    no running process" message. A lock records the environment of its run
    before its process ID, and one from another environment is reported
    before its process is looked for. A process of another user that kill -0
    may not signal counts as running, and signals wait while the lock is
    made. The three scripts hold the same helpers."""
    script = _script(sh_name)
    body = _sh_function(script, "take_lock")
    for phrase in POWERSHELL_LOCK_PHRASES + OTHER_LOCK_PHRASES:
        assert phrase in body, f"{sh_name} lacks {phrase!r}"
    assert _in_order(
        body,
        "trap '' HUP INT QUIT PIPE TERM",
        'mkdir "$LOCK_DIR"',
        "LOCK_HELD=1",
        "trap_signals_to_exit",
        'lock_env > "${LOCK_DIR}/env"',
        '> "${LOCK_DIR}/pid"',
        '[ ! -L "$LOCK_DIR" ] && [ ! -d "$LOCK_DIR" ]',
        "if powershell_may_lock; then",
        'cat "${LOCK_DIR}/pid"',
        '"$(lock_env)"',
        'process_running "$_tl_pid"',
    )
    assert '[ -L "$APOTHEM_HOME" ]' in body
    assert 'cd -P -- "$APOTHEM_HOME"' in body
    running = _sh_function(script, "process_running")
    assert 'kill -0 "$1"' in running
    assert "ot permitted" in running
    for helper in ("lock_env", "powershell_may_lock", "process_running"):
        assert _sh_function(script, helper) == _sh_function(SH, helper), helper


#: The most bytes Linux passes in one argument (MAX_ARG_STRLEN, 32 pages of
#: 4096 bytes, the ending NUL included).
ONE_ARGUMENT_LIMIT = 131072


@pytest.mark.parametrize("sh_name", ["install.sh", "update.sh", "uninstall.sh"])
def test_each_sh_script_fits_in_one_argument(sh_name: str) -> None:
    """The documented one-liner, sh -c "$(curl -fsSL .../install.sh)", hands
    the whole script to sh as one argument, and Linux refuses a longer one
    ("Argument list too long") before sh starts."""
    size = len((INSTALLER / sh_name).read_bytes())
    assert size < ONE_ARGUMENT_LIMIT, f"{sh_name} is {size} bytes"


#: uname answers (-s, -r) and whether a PowerShell run can hold the lock
#: there: Git Bash, MSYS2, Cygwin and WSL, not other Linux or macOS.
UNAME_CASES: tuple[tuple[str, str, str, bool], ...] = (
    ("git-bash", "MINGW64_NT-10.0-26100", "3.5.4-0bc1222b.x86_64", True),
    ("msys", "MSYS_NT-10.0-26100", "3.5.4-0bc1222b.x86_64", True),
    ("cygwin", "CYGWIN_NT-10.0-26100", "3.5.4-1.x86_64", True),
    ("wsl2", "Linux", "5.15.153.1-microsoft-standard-WSL2", True),
    ("wsl1", "Linux", "4.4.0-19041-Microsoft", True),
    ("linux", "Linux", "6.8.0-45-generic", False),
    ("macos", "Darwin", "24.1.0", False),
)


def _uname_stub(system: str, release: str) -> str:
    """sh that defines uname to answer -s with SYSTEM and -r with RELEASE."""
    return (
        "uname() { case \"$1\" in -s) printf '%s\\n' "
        f"'{system}' ;; -r) printf '%s\\n' '{release}' ;; "
        '*) command uname "$@" ;; esac; }\n'
    )


@requires_posix_sh
@pytest.mark.parametrize("sh_name", ["install.sh", "update.sh", "uninstall.sh"])
@pytest.mark.parametrize(
    ("case", "system", "release", "powershell"),
    UNAME_CASES,
    ids=[c[0] for c in UNAME_CASES],
)
def test_the_sh_scripts_report_a_lock_file_in_the_same_words(
    tmp_path: Path,
    sh_name: str,
    case: str,
    system: str,
    release: str,
    powershell: bool,
) -> None:
    """Each sh script's take_lock, run against a file at <home>.lock, stops
    and leaves the file there: with the PowerShell-lock message where a
    PowerShell run can hold that file, and a plain one everywhere else."""
    assert _SH is not None
    home = (tmp_path / "home").as_posix()
    lock = tmp_path / "home.lock"
    lock.write_bytes(b"")
    script = _script(sh_name)
    program = (
        "die() { printf '%s\\n' \"$*\"; exit 1; }\n"
        'exists() { [ -e "$1" ] || [ -L "$1" ]; }\n'
        "trap_signals_to_exit() { :; }\n" + _uname_stub(system, release) + "DRY_RUN=0\n"
        'APOTHEM_HOME="$1"\n'
        + "\n".join(
            _sh_function(script, name)
            for name in ("take_lock", "lock_env", "powershell_may_lock")
        )
        + "\ntake_lock\necho taken\n"
    )
    result = subprocess.run(
        [_SH, "-c", program, "sh", home],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=_sh_env(),
    )
    if powershell:
        expected = (
            f"{home}.lock is the lock file of an Apothem PowerShell run (install.ps1, "
            f"update.ps1 or uninstall.ps1) on {home}, and Windows removes it when "
            "that run ends; while the run is active, Windows will not let anyone "
            "remove it. Wait for that run to finish, then re-run. If no Apothem "
            f"install, update or uninstall is running, remove {home}.lock, then "
            "re-run."
        )
    else:
        expected = (
            f"{home}.lock is a file where the Apothem lock folder belongs. If no "
            "Apothem install, update or uninstall is running, remove "
            f"{home}.lock, then re-run."
        )
    assert result.stdout.strip() == expected, result.stdout + result.stderr
    assert lock.is_file()


def _msys_stub(system: str, root: str) -> str:
    """sh that defines uname to answer -s with SYSTEM, -o with Msys and -n
    with one host name, and cygpath to give ROOT as the runtime's root."""
    return (
        "uname() { case \"$1\" in -s) printf '%s\\n' "
        f"'{system}' ;; -o) printf 'Msys\\n' ;; -n) printf 'box\\n' ;; "
        '*) command uname "$@" ;; esac; }\n'
        f"cygpath() {{ printf '%s\\n' '{root}'; }}\n"
    )


#: Two runs' uname -s and runtime root, and whether their lock records must
#: match: one runtime under another MSYSTEM or after a Windows update is the
#: same process table; Git Bash and an MSYS2 install are two.
LOCK_ENV_CASES: tuple[tuple[str, tuple[str, str], tuple[str, str], bool], ...] = (
    (
        "other-msystem",
        ("MINGW64_NT-10.0-26100", "C:/Program Files/Git/"),
        ("MSYS_NT-10.0-26100", "C:/Program Files/Git/"),
        True,
    ),
    (
        "windows-update",
        ("MINGW64_NT-10.0-26100", "C:/Program Files/Git/"),
        ("MINGW64_NT-10.0-26200", "C:/Program Files/Git/"),
        True,
    ),
    (
        "two-runtimes",
        ("MINGW64_NT-10.0-26100", "C:/Program Files/Git/"),
        ("MINGW64_NT-10.0-26100", "C:/msys64/"),
        False,
    ),
)


@requires_posix_sh
@pytest.mark.parametrize("sh_name", ["install.sh", "update.sh", "uninstall.sh"])
@pytest.mark.parametrize(
    ("case", "first", "second", "same"),
    LOCK_ENV_CASES,
    ids=[c[0] for c in LOCK_ENV_CASES],
)
def test_the_lock_record_names_the_msys_runtime_not_its_settings(
    sh_name: str,
    case: str,
    first: tuple[str, str],
    second: tuple[str, str],
    same: bool,
) -> None:
    """lock_env records which process table a run's process ID belongs to:
    two msys runtimes (Git Bash and MSYS2) differ, while one runtime started
    under another MSYSTEM, or after a Windows update changed the build in
    uname -s, records the same."""
    assert _SH is not None
    body = _sh_function(_script(sh_name), "lock_env")

    def record(system: str, root: str) -> str:
        return subprocess.run(
            [_SH, "-c", _msys_stub(system, root) + body + "\nlock_env\n"],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
            env=_sh_env(),
        ).stdout

    assert (record(*first) == record(*second)) is same


@requires_posix_sh
@pytest.mark.parametrize("sh_name", ["install.sh", "update.sh", "uninstall.sh"])
@pytest.mark.parametrize("env", ["other", "same", "none"])
def test_the_sh_scripts_tell_a_lock_from_another_environment(
    tmp_path: Path, sh_name: str, env: str
) -> None:
    """A lock folder records the environment of the run that made it. One
    made in another environment (WSL and Git Bash on one machine, another
    container) names a process ID that means nothing here, so it is reported
    as one whose process cannot be checked, never as one whose process is
    gone. A lock from this environment, or one with no record (an earlier
    installer made it), still has its process checked."""
    assert _SH is not None
    home = (tmp_path / "home").as_posix()
    lock = tmp_path / "home.lock"
    lock.mkdir()
    script = _script(sh_name)
    helpers = "\n".join(
        _sh_function(script, name)
        for name in ("take_lock", "lock_env", "powershell_may_lock", "process_running")
    )
    prelude = (
        "die() { printf '%s\\n' \"$*\"; exit 1; }\n"
        'exists() { [ -e "$1" ] || [ -L "$1" ]; }\n'
        "trap_signals_to_exit() { :; }\n"
        "DRY_RUN=0\n"
        'APOTHEM_HOME="$1"\n' + helpers + "\n"
    )
    if env == "other":
        (lock / "env").write_text("OtherOS elsewhere pid:[1]\n", encoding="utf-8")
    elif env == "same":
        same = subprocess.run(
            [_SH, "-c", prelude + "lock_env", "sh", home],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
            env=_sh_env(),
        ).stdout
        (lock / "env").write_text(same, encoding="utf-8", newline="\n")
    (lock / "pid").write_text("999999999\n", encoding="utf-8")

    result = subprocess.run(
        [_SH, "-c", prelude + "take_lock\necho taken\n", "sh", home],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=_sh_env(),
    )

    if env == "other":
        expected = (
            f"{home}.lock was made by an Apothem run in another environment (such "
            "as WSL, Git Bash or a container), so whether its process 999999999 "
            "still runs cannot be checked from here. Wait for that run to "
            "finish, then re-run. If no Apothem install, update or uninstall is "
            f"running anywhere, remove {home}.lock, then re-run."
        )
    else:
        expected = (
            f"{home}.lock was left by an Apothem run that did not finish (process "
            "999999999 is no longer running). Check that no Apothem install, "
            f"update or uninstall is running, remove {home}.lock, then re-run."
        )
    assert result.stdout.strip() == expected, result.stdout + result.stderr
    assert (lock / "pid").is_file()


def test_both_installers_name_their_staging_folders_after_the_home() -> None:
    """Both installers name every staging folder beside APOTHEM_HOME
    .apothem-<kind>.<leaf>.<suffix>, <leaf> being APOTHEM_HOME's own folder
    name, so a later run tells this home's leftovers from another home's,
    and both write the carry list under the same name."""
    staging = _sh_function(SH, "make_staging")
    assert (
        'mktemp -d "$(dirname -- "$APOTHEM_HOME")/.apothem-$1.$(basename -- '
        '"$APOTHEM_HOME").XXXXXX"'
    ) in staging
    for kind in ("old", "extract", "clone"):
        assert f"make_staging {kind})" in SH, kind
        assert re.search(
            rf"\.apothem-{kind}\.(\$\(Split-Path -Leaf \$ApothemHome\)|\$SwLeaf)\.",
            PS1,
        ), f"install.ps1 does not name .apothem-{kind}. after the home"
    assert 'mktemp -d "$(dirname' not in SH.replace(staging, "")
    assert 'CARRY_LIST=".apothem-carried-entries"' in SH
    assert "$CarryList = '.apothem-carried-entries'" in PS1


#: A layout of leftovers beside a home named "apothem-home", relative to
#: the folder that holds it: a path ending in "/" is a folder, any other a
#: file with that text.
LEFTOVER_LAYOUT: dict[str, str] = {
    # This home's, with a carry list that names user files as well.
    ".apothem-extract.apothem-home.Ab12Cd/.apothem-carried-entries": (
        ".env\nbackups\nmy-notes\nstate\ngone\n"
    ),
    ".apothem-extract.apothem-home.Ab12Cd/apothem-v9.9.9/src/": "",
    ".apothem-extract.apothem-home.Ab12Cd/apothem-v9.9.9/backups/": "",
    ".apothem-extract.apothem-home.Ab12Cd/apothem-v9.9.9/state/": "",
    ".apothem-extract.apothem-home.Ab12Cd/apothem-v9.9.9/.env": "KEY=1\n",
    ".apothem-extract.apothem-home.Ab12Cd/apothem-v9.9.9/my-notes/": "",
    ".apothem-old.apothem-home.Ef34Gh/home/": "",
    # install.ps1's aside temp folder, which both leave out.
    f".apothem-clone.apothem-home.{'9' * 6}/aside.{'0a' * 16}/": "",
    ".apothem-clone.apothem-home.999999/apothem/src/": "",
    ".apothem-old.apothem-home.Zz99Zz/a.txt": "a\n",
    ".apothem-old.apothem-home.Zz99Zz/B.txt": "B\n",
    ".apothem-old.apothem-home.Zz99Zz/_x": "x\n",
    ".apothem-old.apothem-home.Zz99Zz/.h": "h\n",
    # Earlier names, with no home in them.
    ".apothem-extract.Qr90St/apothem-v1.5.0/.apothem-source-entries": (
        ".apothem-source-entries\nsrc\n"
    ),
    ".apothem-extract.Qr90St/apothem-v1.5.0/src/": "",
    ".apothem-extract.Qr90St/apothem-v1.5.0/plans/": "",
    ".apothem-extract.Qr90St/apothem-v1.5.0/notes.txt": "n\n",
    ".apothem-clone.Uv12Wx/apothem/state/": "",
    ".apothem-clone.Uv12Wx/apothem/memory/": "",
    ".apothem-old.Mn78Op/": "",
    # Another home's, and a home whose name has a dot: never reported.
    ".apothem-extract.other-home.Ab12Cd/apothem-v9.9.9/backups/": "",
    ".apothem-old.apothem-home.x.Cd34Ef/home/": "",
    # The folders a missing home was set aside in.
    "apothem-home.before-apothem-20261101000000/apothem-home/notes.txt": "n\n",
    "apothem-home.before-apothem-20261001120000-4242/notes.txt": "n\n",
    "apothem-home.before-apothem-notes/a.txt": "a\n",
}


def _plant_leftovers(parent: Path) -> None:
    for rel, text in LEFTOVER_LAYOUT.items():
        target = parent / rel
        if rel.endswith("/"):
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")


def _expected_leftover_lines(parent: str, sep: str) -> list[str]:
    """The report for LEFTOVER_LAYOUT under PARENT, SEP joining a folder and
    an entry in it (each family writes its own separator there)."""
    home = f"{parent}/apothem-home"
    note = (
        " (made by an earlier installer that did not record which home it was "
        f"for, so it may belong to any Apothem home in {parent}: check what it "
        "holds before you move or remove it)"
    )

    def at(name: str) -> str:
        return f"{parent}/{name}"

    clone = at(".apothem-clone.apothem-home.999999")
    extract = at(".apothem-extract.apothem-home.Ab12Cd")
    old = at(".apothem-old.apothem-home.Ef34Gh")
    other = at(".apothem-old.apothem-home.Zz99Zz")
    older_clone = at(".apothem-clone.Uv12Wx")
    older_extract = at(".apothem-extract.Qr90St")
    older_old = at(".apothem-old.Mn78Op")
    flat = at("apothem-home.before-apothem-20261001120000-4242")
    nested = at("apothem-home.before-apothem-20261101000000")
    return [
        "  x An earlier run was stopped part-way and left these folders beside "
        f"{home}:",
        f"    {clone}: the new source that was being installed, in {clone}{sep}apothem",
        f"    {extract}: the new source that was being installed, in "
        f"{extract}{sep}apothem-v9.9.9, with these entries moved into it from "
        f"{home}: .env, backups, my-notes, state",
        f"    {old}: the earlier install that was being replaced, in {old}{sep}home",
        f"    {other}: files from that run (.h, B.txt, _x, a.txt)",
        f"    {older_clone}: the new source that was being installed, in "
        f"{older_clone}{sep}apothem, with these entries moved into it from "
        f"the Apothem home it was made for: memory, state{note}",
        f"    {older_extract}: the new source that was being installed, in "
        f"{older_extract}{sep}apothem-v1.5.0, with these entries moved into it "
        f"from the Apothem home it was made for: notes.txt, plans{note}",
        f"    {older_old}: empty{note}",
        f"    {flat}: the earlier contents of {home}, moved aside, in {flat}",
        f"    {nested}: the earlier contents of {home}, moved aside, in "
        f"{nested}{sep}apothem-home",
        _closing_line(home),
    ]


def _closing_line(home: str) -> str:
    """The last line of the leftovers report, for the home HOME."""
    return (
        f"    Nothing was changed. If {home} is missing, move the earlier install "
        "back to it first. Then move every entry listed above as moved into a "
        "new source back into the home it came from, remove the folders listed "
        "above, and re-run."
    )


def _sh_leftover_program(prelude: str = "") -> str:
    """sh source that defines install.sh's check_leftovers and what it uses,
    then runs it for the home "$1" (PRELUDE, such as a uname stub, first)."""
    names = (
        "exists",
        "list_entries",
        "paint",
        "check_leftovers",
        "same_leaf",
        "is_aside_name",
        "is_aside_temp",
        "is_extract_staging",
        "join_names",
        "leftover_line",
        "leftover_carried",
    )
    return (
        prelude + "COLOR_ERR=0\n"
        'CARRY_LIST=".apothem-carried-entries"\n'
        'SOURCE_MANIFEST=".apothem-source-entries"\n'
        'APOTHEM_HOME="$1"\n'
        + "\n".join(_sh_function(SH, name) for name in names)
        + "\ncheck_leftovers\necho none\n"
    )


@requires_posix_sh
def test_install_sh_reports_leftovers_in_the_agreed_order_and_words(
    tmp_path: Path,
) -> None:
    """install.sh's check_leftovers, run on LEFTOVER_LAYOUT: this home's
    folders by name, then the earlier-name folders with their note, then
    the folders a missing home was set aside in, every list of names in
    byte order; another home's folders and a non-matching aside name are
    left out."""
    assert _SH is not None
    _plant_leftovers(tmp_path)
    parent = tmp_path.as_posix()
    result = subprocess.run(
        [_SH, "-c", _sh_leftover_program(), "sh", f"{parent}/apothem-home"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
        env=_sh_env(),
    )
    lines = result.stderr.replace("✗", "x").splitlines()
    assert result.returncode == 1, result.stdout + result.stderr
    assert lines == _expected_leftover_lines(parent, "/"), result.stderr


@requires_powershell
def test_install_ps1_reports_leftovers_in_the_same_order_and_words(
    tmp_path: Path,
) -> None:
    """install.ps1's Assert-NoLeftover, run on LEFTOVER_LAYOUT, prints the
    same lines as install.sh: one line per folder, in the same order and
    words, then the closing line (through Write-Fail)."""
    _plant_leftovers(tmp_path)
    parent = str(tmp_path)
    result = _ps1_leftovers(tmp_path / "apothem-home")
    assert result.returncode == 1, result.stdout + result.stderr
    # PowerShell joins paths with "\" on Windows; compare them with "/".
    expected = _expected_leftover_lines(parent.replace("\\", "/"), "/")
    got = [line.replace("\\", "/") for line in result.stderr.splitlines()]
    assert got == expected, result.stderr


def _ps1_leftovers(home: Path) -> subprocess.CompletedProcess[str]:
    """Run install.ps1's Assert-NoLeftover, and what it uses, for HOME."""
    program = "; ".join(
        (
            *_ps1_define(
                "$CarryList",
                "$SourceManifest",
                "$EngineDataNames",
                "Test-Entry",
                "Test-RealFolder",
                "Test-RealFolderPath",
                "Get-SortedName",
                "Test-SameLeaf",
                "ConvertTo-AsciiLower",
                "Get-LeftoverEntry",
                "Get-CarriedEntry",
                "Get-LeftoverLine",
                "Assert-NoLeftover",
            ),
            "$ApothemHome = $env:LEFTOVER_HOME",
            "function Write-Fail { param([string]$Msg) [Console]::Error.WriteLine("
            "'    ' + $Msg); exit 1 }",
            "Assert-NoLeftover",
            "'none'",
        )
    )
    return _run_powershell(program, "install.ps1", LEFTOVER_HOME=str(home))


def _sh_leftovers(home: Path, prelude: str = "") -> subprocess.CompletedProcess[str]:
    """Run install.sh's check_leftovers, and what it uses, for HOME."""
    assert _SH is not None
    return subprocess.run(
        [_SH, "-c", _sh_leftover_program(prelude), "sh", home.as_posix()],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
        env=_sh_env(),
    )


def _report_lines(home: str, *lines: str) -> list[str]:
    """The leftovers report for HOME naming LINES, with "x" for the sh
    family's mark."""
    return [
        "  x An earlier run was stopped part-way and left these folders beside "
        f"{home}:",
        *(f"    {line}" for line in lines),
        _closing_line(home),
    ]


def _got_lines(result: subprocess.CompletedProcess[str]) -> list[str]:
    return [
        line.replace("✗", "x").replace("\\", "/") for line in result.stderr.splitlines()
    ]


#: Folders made for the home "apothem-home" spelled "APOTHEM-Home", as a run
#: given that spelling names them, and the home missing. The aside has the
#: earlier layout (contents directly inside), so its line reads the same
#: whether the file system ignores case or not.
CASE_LAYOUT: dict[str, str] = {
    ".apothem-extract.APOTHEM-Home.Ab12Cd/apothem-v9.9.9/src/": "",
    "APOTHEM-Home.before-apothem-20261101000000/a.txt": "a\n",
}


def _case_lines(parent: str) -> list[str]:
    extract = f"{parent}/.apothem-extract.APOTHEM-Home.Ab12Cd"
    aside = f"{parent}/APOTHEM-Home.before-apothem-20261101000000"
    home = f"{parent}/apothem-home"
    return _report_lines(
        home,
        f"{extract}: the new source that was being installed, in "
        f"{extract}/apothem-v9.9.9",
        f"{aside}: the earlier contents of {home}, moved aside, in {aside}",
    )


def _plant(parent: Path, layout: dict[str, str]) -> None:
    for rel, text in layout.items():
        target = parent / rel
        if rel.endswith("/"):
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")


@requires_posix_sh
@pytest.mark.parametrize(
    ("system", "fold"),
    [("Linux", False), ("Darwin", True), ("MINGW64_NT-10.0-26100", True)],
    ids=["linux", "macos", "git-bash"],
)
def test_install_sh_counts_another_spelling_of_the_home_where_case_is_ignored(
    tmp_path: Path, system: str, fold: bool
) -> None:
    """On Windows and macOS, APP.HOME and app.home name one folder, so the
    staging folders and asides a run made for this home spelled with other
    capitals are this home's, and are reported. On Linux they belong to
    another home and are left alone (uname says which system it is)."""
    _plant(tmp_path, CASE_LAYOUT)
    result = _sh_leftovers(tmp_path / "apothem-home", _uname_stub(system, "1.0"))
    if fold:
        assert result.returncode == 1, result.stdout + result.stderr
        assert _got_lines(result) == _case_lines(tmp_path.as_posix()), result.stderr
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.strip() == "none", result.stdout + result.stderr


@requires_powershell
@pytest.mark.skipif(sys.platform != "win32", reason="Windows ignores case in names")
def test_install_ps1_counts_another_spelling_of_the_home_on_windows(
    tmp_path: Path,
) -> None:
    """install.ps1 reports this home's folders made under another spelling
    of it, in the same words as install.sh under Git Bash."""
    _plant(tmp_path, CASE_LAYOUT)
    result = _ps1_leftovers(tmp_path / "apothem-home")
    assert result.returncode == 1, result.stdout + result.stderr
    assert _got_lines(result) == _case_lines(str(tmp_path).replace("\\", "/"))


#: What a keep-clone swap stopped after its move-in leaves: the clone's own
#: tree, with its .git, in .apothem-old.<leaf>.*/home, beside the carry list
#: in the staging folder the new tree left, while APOTHEM_HOME holds the new
#: install.
KEPT_CLONE_LAYOUT: dict[str, str] = {
    "apothem-home/src/apothem/__init__.py": "",
    ".apothem-old.apothem-home.Kp00Kp/home/.git/HEAD": "ref: refs/heads/main\n",
    ".apothem-old.apothem-home.Kp00Kp/home/src/apothem/__init__.py": "",
    ".apothem-extract.apothem-home.Ex00Ex/.apothem-carried-entries": "state\n",
}


def _kept_clone_lines(parent: str) -> list[str]:
    old = f"{parent}/.apothem-old.apothem-home.Kp00Kp"
    extract = f"{parent}/.apothem-extract.apothem-home.Ex00Ex"
    return _report_lines(
        f"{parent}/apothem-home",
        f"{extract}: files from that run (.apothem-carried-entries)",
        f"{old}: the earlier clone's tree, which that run was keeping, in "
        f"{old}/home: move it to a folder of your own if you still need it",
    )


@requires_posix_sh
def test_install_sh_names_a_clone_tree_a_stopped_run_was_keeping(
    tmp_path: Path,
) -> None:
    """A clone's tree a keep-clone swap was keeping, with the new install
    already in place, is named as that, not as an earlier install to put
    back or remove."""
    _plant(tmp_path, KEPT_CLONE_LAYOUT)
    result = _sh_leftovers(tmp_path / "apothem-home")
    assert result.returncode == 1, result.stdout + result.stderr
    assert _got_lines(result) == _kept_clone_lines(tmp_path.as_posix())


@requires_powershell
def test_install_ps1_names_a_clone_tree_a_stopped_run_was_keeping(
    tmp_path: Path,
) -> None:
    """install.ps1 names that tree in the same words."""
    _plant(tmp_path, KEPT_CLONE_LAYOUT)
    result = _ps1_leftovers(tmp_path / "apothem-home")
    assert result.returncode == 1, result.stdout + result.stderr
    expected = _kept_clone_lines(str(tmp_path).replace("\\", "/"))
    assert _got_lines(result) == expected, result.stderr


#: What a keep swap leaves when a folder that is not Apothem's appeared at
#: .apothem-old.<leaf>.*/home just before its move of the earlier tree there:
#: the move is undone and the earlier install stays at APOTHEM_HOME, but
#: that folder is left in place for the user to check.
STRAY_OLD_HOME_LAYOUT: dict[str, str] = {
    "apothem-home/src/apothem/__init__.py": "",
    ".apothem-old.apothem-home.St00St/home/theirs.txt": "t\n",
}


def _stray_old_home_lines(parent: str) -> list[str]:
    old = f"{parent}/.apothem-old.apothem-home.St00St"
    return _report_lines(
        f"{parent}/apothem-home",
        f"{old}: a folder that holds no Apothem install, in {old}/home: check "
        "what it holds before you remove it",
    )


@requires_posix_sh
def test_install_sh_does_not_call_a_stray_folder_the_earlier_install(
    tmp_path: Path,
) -> None:
    """A home folder in .apothem-old.* that holds no Apothem source, while
    APOTHEM_HOME is in place, is not called the earlier install."""
    _plant(tmp_path, STRAY_OLD_HOME_LAYOUT)
    result = _sh_leftovers(tmp_path / "apothem-home")
    assert result.returncode == 1, result.stdout + result.stderr
    assert _got_lines(result) == _stray_old_home_lines(tmp_path.as_posix())


@requires_powershell
def test_install_ps1_does_not_call_a_stray_folder_the_earlier_install(
    tmp_path: Path,
) -> None:
    """install.ps1 names that folder in the same words."""
    _plant(tmp_path, STRAY_OLD_HOME_LAYOUT)
    result = _ps1_leftovers(tmp_path / "apothem-home")
    assert result.returncode == 1, result.stdout + result.stderr
    expected = _stray_old_home_lines(str(tmp_path).replace("\\", "/"))
    assert _got_lines(result) == expected, result.stderr


#: Names whose byte order and UTF-16 order differ: U+FF21 (EF BC A1 in
#: UTF-8) sorts before U+1F600 (F0 9F 98 80) by bytes, after it by UTF-16
#: code units (the surrogate D83D is below FF21).
SORT_NAMES: tuple[str, ...] = (
    "a\U0001f600",
    "a\uff21",
    "B",
    "_x",
    ".h",
    "a",
    "\u00e9",
    "a\ue000",
)


@requires_powershell
def test_powershell_sorts_names_in_the_byte_order_sh_uses() -> None:
    """install.ps1's Get-SortedName puts names in the order LC_ALL=C sort
    gives install.sh (their UTF-8 bytes), names outside the Basic
    Multilingual Plane included, where an ordinal .NET sort differs."""
    by_bytes = sorted(SORT_NAMES, key=lambda name: name.encode("utf-8"))
    by_utf16 = sorted(SORT_NAMES, key=lambda name: name.encode("utf-16-be"))
    assert by_bytes != by_utf16
    program = "; ".join(
        (
            *_ps1_define("Get-SortedName"),
            "$names = [string[]]($env:SORT_NAMES | ConvertFrom-Json)",
            "foreach ($name in (Get-SortedName $names)) { "
            "[BitConverter]::ToString([Text.Encoding]::UTF8.GetBytes($name)) }",
        )
    )
    result = _run_powershell(
        program, "install.ps1", SORT_NAMES=json.dumps(list(SORT_NAMES))
    )
    assert result.returncode == 0, result.stdout + result.stderr
    got = [
        bytes.fromhex(line.replace("-", "")).decode("utf-8")
        for line in result.stdout.splitlines()
    ]
    assert got == by_bytes, result.stdout


@requires_posix_sh
def test_sh_sorts_names_by_their_bytes(tmp_path: Path) -> None:
    """install.sh sorts with LC_ALL=C sort: by the names' UTF-8 bytes."""
    assert _SH is not None
    names = tmp_path / "names"
    names.write_bytes(b"".join(name.encode("utf-8") + b"\n" for name in SORT_NAMES))
    result = subprocess.run(
        [_SH, "-c", 'LC_ALL=C sort < "$1"', "sh", names.as_posix()],
        capture_output=True,
        timeout=60,
        check=False,
        env=_sh_env(),
    )
    got = result.stdout.decode("utf-8").splitlines()
    assert got == sorted(SORT_NAMES, key=lambda name: name.encode("utf-8"))
    assert "LC_ALL=C sort" in _sh_function(SH, "check_leftovers")


#: .git/info/attributes contents and whether both families refuse them: a
#: filter= line counts unless the line is a comment, with lines ended by LF
#: only (as git reads them), NUL bytes dropped, and a UTF-16 byte-order mark
#: read as the bytes it is, so it hides nothing git sees.
ATTRIBUTE_CASES: tuple[tuple[str, bytes, bool], ...] = (
    ("plain", b"# mine\n*.toml filter=lfs\n", True),
    ("nul-byte", b"#\0\n*.toml filter=lfs\n", True),
    ("utf16-le-bom", b"\xff\xfe\n* filter=lfs\n", True),
    ("utf16-be-bom", b"\xfe\xff\n* filter=lfs\n", True),
    ("utf8-bom", b"\xef\xbb\xbf* filter=lfs\n", True),
    ("crlf", b"*.toml filter=lfs\r\n", True),
    ("comment", b"  # was: * filter=evil\n*.txt text\n", False),
    ("comment-with-cr", b"#c\r* filter=evil\n", False),
    ("comment-after-tab-and-cr", b"\t\r# filter=evil\n", False),
    # git skips only spaces, tabs and CR before a comment's #: after a VT
    # or FF the line is a pattern, and git applies it.
    ("vt-before-hash", b"\x0b#x filter=evil\n", True),
    ("ff-before-hash", b"\x0c# filter=evil\n", True),
    ("no-filter", b"*.txt -text\n", False),
)


def _attributes_home(root: Path, content: bytes) -> str:
    home = _clone_with_config(root, "")
    (root / ".git" / "info").mkdir()
    (root / ".git" / "info" / "attributes").write_bytes(content)
    return home


def _attributes_message(home: str) -> str:
    return (
        f"{home}'s own git attributes set a filter (filter=), which the update "
        f"would trust. Remove it from {home}/.git/info/attributes, then re-run."
    )


@requires_posix_sh
@pytest.mark.parametrize("sh_name", ["install.sh", "update.sh"])
@pytest.mark.parametrize(
    ("case", "content", "refused"), ATTRIBUTE_CASES, ids=[c[0] for c in ATTRIBUTE_CASES]
)
def test_sh_reads_a_clones_attributes_as_git_does(
    tmp_path: Path, sh_name: str, case: str, content: bytes, refused: bool
) -> None:
    """Each sh script's check_clone_config refuses exactly the attribute
    files ATTRIBUTE_CASES marks."""
    assert _SH is not None
    home = _attributes_home(tmp_path / "clone", content)
    program = (
        "die() { printf '%s\\n' \"$*\"; exit 1; }\n"
        "git_path() { printf '%s\\n' \"$1/.git/$2\"; }\n"
        + _sh_function(SCRIPTS[sh_name], "cgit")
        + "\nHOOKS_OFF=\n"
        + _sh_allow_program(sh_name)
        + _sh_function(SCRIPTS[sh_name], "config_file_problem")
        + "\n"
        + _sh_function(SCRIPTS[sh_name], "check_clone_config")
        + '\ncheck_clone_config "$1"\necho passed\n'
    )
    result = subprocess.run(
        [_SH, "-c", program, "sh", home],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=_sh_env(_git_env_without_user_config()),
    )
    expected = _attributes_message(home) if refused else "passed"
    assert result.stdout.strip() == expected, result.stdout + result.stderr


@requires_powershell
@pytest.mark.parametrize("ps1_name", ["install.ps1", "update.ps1"])
@pytest.mark.parametrize(
    ("case", "content", "refused"), ATTRIBUTE_CASES, ids=[c[0] for c in ATTRIBUTE_CASES]
)
def test_powershell_reads_a_clones_attributes_as_sh_does(
    tmp_path: Path, ps1_name: str, case: str, content: bytes, refused: bool
) -> None:
    """Each .ps1 script's Assert-CloneConfig gives the same verdict, and the
    same message, as the sh scripts on every ATTRIBUTE_CASES file."""
    home = _attributes_home(tmp_path / "clone", content)
    program = "; ".join(
        (
            *_ps1_define(
                "$GitNoProgram",
                "$CloneConfigAllow",
                "Test-AllowedConfigKey",
                "Assert-CloneConfig",
            ),
            "function Write-Fail { param([string]$Msg) throw $Msg }",
            "function Get-ClonePath { param([string]$Dir, [string]$Name) "
            '"$Dir/.git/$Name" }',
            "try { Assert-CloneConfig $env:CLONE_HOME; 'passed' } "
            "catch { $_.Exception.Message }",
        )
    )
    result = _run_powershell(program, ps1_name, CLONE_HOME=home, **_git_env_overrides())
    expected = _attributes_message(home) if refused else "passed"
    assert result.stdout.strip() == expected, result.stdout + result.stderr


def _git(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        env=_git_env_without_user_config(),
    )


def _upstream_and_clone(tmp_path: Path) -> tuple[Path, Path]:
    """A repository with one commit, and a clone of it."""
    upstream = tmp_path / "upstream"
    _git("init", "--quiet", str(upstream))
    (upstream / "README").write_text("x\n", encoding="utf-8")
    _git("add", "README", cwd=upstream)
    _git("commit", "--quiet", "-m", "x", cwd=upstream)
    home = tmp_path / "home"
    _git("clone", "--quiet", str(upstream), str(home))
    return upstream, home


#: The git command each family runs on a clone, then a fetch from origin.
_FETCH_PROGRAMS = ("install.sh", "update.sh", "install.ps1", "update.ps1")


def _fetch_origin(name: str, home: Path, path_entry: str) -> str:
    """Run `fetch --tags origin` on HOME through script NAME's cgit or
    $GitNoProgram, with PATH_ENTRY put first on PATH; return the output."""
    env = {
        **_git_env_overrides(),
        "PATH": path_entry + os.pathsep + os.environ.get("PATH", ""),
        "CLONE_HOME": home.as_posix(),
    }
    if name.endswith(".sh"):
        assert _SH is not None
        program = (
            _sh_function(SCRIPTS[name], "cgit")
            + "\nHOOKS_OFF=\n"
            + 'cgit -C "$CLONE_HOME" fetch --tags origin 2>&1\necho "rc=$?"\n'
        )
        result = subprocess.run(
            [_SH, "-c", program],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env=_sh_env({**os.environ, **env}),
        )
    else:
        program = "; ".join(
            (
                *_ps1_define("$GitNoProgram"),
                "$ErrorActionPreference = 'Continue'",
                "$out = & git @GitNoProgram -C $env:CLONE_HOME fetch --tags origin 2>&1",
                "$out | ForEach-Object { [string]$_ }",
                '"rc=$LASTEXITCODE"',
            )
        )
        result = _run_powershell(program, name, **env)
    return result.stdout + result.stderr


@pytest.mark.parametrize("name", _FETCH_PROGRAMS)
def test_git_on_a_clone_runs_no_helper_program_its_address_names(
    tmp_path: Path, name: str
) -> None:
    """A clone's remote.origin.url of the form <name>::<address> makes git
    look up git-remote-<name> on PATH, after git -C has moved into the
    clone; with a '.' entry on PATH that is a program planted in the
    clone. cgit and $GitNoProgram allow only the file, git, http, https and
    ssh transports, so git refuses the address and runs nothing, while a
    plain path address still fetches."""
    if name.endswith(".sh") and _SH is None:
        pytest.skip("no POSIX sh on this host")
    if name.endswith(".ps1") and _PWSH is None:
        pytest.skip("no PowerShell on this host")
    upstream, home = _upstream_and_clone(tmp_path)
    marker = tmp_path / "helper-ran"
    helper = home / "git-remote-evil"
    helper.write_text(
        f"#!/bin/sh\necho ran > '{marker.as_posix()}'\nexit 1\n", encoding="utf-8"
    )
    helper.chmod(0o755)
    _git("-C", str(home), "config", "remote.origin.url", f"evil::{upstream.as_posix()}")

    out = _fetch_origin(name, home, ".")

    assert not marker.exists(), out
    assert "transport 'evil' not allowed" in out, out

    _git("-C", str(home), "config", "remote.origin.url", upstream.as_posix())
    out = _fetch_origin(name, home, ".")
    assert "rc=0" in out, out


@pytest.mark.parametrize(("sh_name", "ps1_name"), RELEASE_TAG_PAIRS)
def test_a_clone_whose_index_git_cannot_read_is_refused_in_both(
    tmp_path: Path, sh_name: str, ps1_name: str
) -> None:
    """When git cannot read the clone's index, ls-files fails; both families
    stop with the same message before anything is fetched, so a .ps1 dry run
    fails where the real run would, as the sh scripts do."""
    _, home_path = _upstream_and_clone(tmp_path)
    (home_path / ".git" / "index").write_bytes(b"DIRCgarbage")
    home = home_path.as_posix()
    expected = (
        f"{home} has changes to tracked files. Commit or stash them, then re-run."
    )
    if _SH is not None:
        sh = SCRIPTS[sh_name]
        program = (
            "die() { printf '%s\\n' \"$*\"; exit 1; }\n"
            + _sh_function(sh, "cgit")
            + "\nHOOKS_OFF=\n"
            + _sh_allow_program(sh_name)
            + "".join(
                _sh_function(sh, function) + "\n"
                for function in (
                    "git_path",
                    "config_file_problem",
                    "check_clone_config",
                    "clone_git_ok",
                    "check_clone_modules",
                    "check_clone_gitlinks",
                    "check_clone_setup",
                )
            )
            + 'check_clone_setup "$1"\necho passed\n'
        )
        result = subprocess.run(
            [_SH, "-c", program, "sh", home],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env=_sh_env(_git_env_without_user_config()),
        )
        assert result.stdout.strip() == expected, result.stdout + result.stderr
    if _PWSH is not None:
        program = "; ".join(
            (
                *_ps1_define(
                    "$GitNoProgram",
                    "$CloneConfigAllow",
                    "Test-AllowedConfigKey",
                    "Get-ClonePath",
                    "Assert-CloneConfig",
                    "Assert-CloneGit",
                    "Assert-CleanClone",
                ),
                "function Write-Fail { param([string]$Msg) throw $Msg }",
                "try { Assert-CleanClone $env:CLONE_HOME; 'passed' } "
                "catch { $_.Exception.Message }",
            )
        )
        result = _run_powershell(
            program, ps1_name, CLONE_HOME=home, **_git_env_overrides()
        )
        assert result.stdout.strip() == expected, result.stdout + result.stderr


@pytest.mark.skipif(sys.platform != "win32", reason="Windows' path limit")
@pytest.mark.parametrize("name", _FETCH_PROGRAMS)
def test_a_checkout_on_a_clone_writes_a_path_past_the_windows_limit(
    tmp_path: Path, name: str
) -> None:
    """Git for Windows leaves out a file whose full path passes 259
    characters unless core.longpaths is on, and its checkout still exits 0.
    The staging folders beside APOTHEM_HOME carry the home's name, so a
    long profile folder can push the release tree's deepest test fixtures
    past it; cgit and $GitNoProgram turn core.longpaths on."""
    if name.endswith(".sh") and _SH is None:
        pytest.skip("no POSIX sh on this host")
    if name.endswith(".ps1") and _PWSH is None:
        pytest.skip("no PowerShell on this host")
    upstream = tmp_path / "upstream"
    _git("init", "--quiet", "--bare", str(upstream))
    deep = "/".join(["d" * 60] * 4) + "/file.txt"
    blob = subprocess.run(
        ["git", "-C", str(upstream), "hash-object", "-w", "--stdin"],
        input="x\n",
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    index = {**_git_env_without_user_config(), "GIT_INDEX_FILE": str(tmp_path / "ix")}
    subprocess.run(
        [
            "git",
            "-C",
            str(upstream),
            "update-index",
            "--add",
            "--cacheinfo",
            f"100644,{blob},{deep}",
        ],
        check=True,
        env=index,
    )
    tree = subprocess.run(
        ["git", "-C", str(upstream), "write-tree"],
        capture_output=True,
        text=True,
        check=True,
        env=index,
    ).stdout.strip()
    commit = subprocess.run(
        [
            "git",
            "-C",
            str(upstream),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.invalid",
            "commit-tree",
            tree,
            "-m",
            "x",
        ],
        capture_output=True,
        text=True,
        check=True,
        env=_git_env_without_user_config(),
    ).stdout.strip()
    home = tmp_path / "home"
    _git("clone", "--quiet", "--no-checkout", str(upstream), str(home))
    target = home / deep
    assert len(str(target)) > 260, len(str(target))
    env = {**_git_env_overrides(), "CLONE_HOME": home.as_posix(), "COMMIT": commit}
    if name.endswith(".sh"):
        assert _SH is not None
        program = (
            _sh_function(SCRIPTS[name], "cgit")
            + "\nHOOKS_OFF=\n"
            + 'cgit -C "$CLONE_HOME" checkout --quiet --detach "$COMMIT"\n'
        )
        result = subprocess.run(
            [_SH, "-c", program],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env=_sh_env({**os.environ, **env}),
        )
    else:
        program = "; ".join(
            (
                *_ps1_define("$GitNoProgram"),
                "$ErrorActionPreference = 'Continue'",
                "& git @GitNoProgram -C $env:CLONE_HOME checkout --quiet --detach "
                "$env:COMMIT 2>&1 | ForEach-Object { [string]$_ }",
            )
        )
        result = _run_powershell(program, name, **env)
    assert Path("\\\\?\\" + str(target)).exists(), result.stdout + result.stderr


#: The git options install.sh and install.ps1 pass to the fresh clone and to
#: the fetch of the tag into a scratch repository.
_FRESH_CLONE_OPTIONS = {
    "install.sh": (
        r'ngit ((?:-c \S+ )*)clone --quiet --no-checkout "\$APOTHEM_REPO"',
        r'git ((?:-c \S+ )*)-C "\$\{_ck_tmp\}/tag\.git" fetch ',
    ),
    "install.ps1": (
        r"& git ((?:-c \S+ )*)clone --quiet --no-checkout \$ApothemRepo ",
        r"& git ((?:-c \S+ )*)-C \$CkTagGit fetch ",
    ),
}


@pytest.mark.skipif(sys.platform != "win32", reason="Windows' path limit")
@pytest.mark.parametrize("name", sorted(_FRESH_CLONE_OPTIONS))
def test_a_fresh_clone_writes_its_pack_under_a_long_staging_folder(
    tmp_path: Path, name: str
) -> None:
    """The fresh clone goes into a staging folder named after APOTHEM_HOME,
    so with a long profile folder the pack files it writes pass Windows'
    usual path limit, and Git for Windows stops with "Filename too long"
    unless core.longpaths is on. The clone runs here with the options the
    script passes, into a folder whose pack paths pass that limit. The
    scratch tag fetch passes the same setting."""
    clone_pattern, fetch_pattern = _FRESH_CLONE_OPTIONS[name]
    clone = re.search(clone_pattern, SCRIPTS[name])
    fetch = re.search(fetch_pattern, SCRIPTS[name])
    assert clone is not None, clone_pattern
    assert fetch is not None, fetch_pattern
    upstream = tmp_path / "upstream"
    _git("init", "--quiet", str(upstream))
    _git("commit", "--quiet", "--allow-empty", "-m", "x", cwd=upstream)
    parent = tmp_path / ("p" * max(1, 200 - len(str(tmp_path)) - 1))
    parent.mkdir()
    tree = parent / "apothem"
    assert len(str(tree / ".git" / "objects" / "pack" / ("p" * 50))) > 260

    result = subprocess.run(
        [
            "git",
            *clone.group(1).split(),
            "clone",
            "--quiet",
            "--no-checkout",
            upstream.as_uri(),
            str(tree),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env=_git_env_without_user_config(),
    )

    assert result.returncode == 0, result.stderr
    assert "core.longpaths=true" in fetch.group(1).split(), fetch.group(0)
