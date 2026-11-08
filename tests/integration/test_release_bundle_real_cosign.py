# SPDX-License-Identifier: MIT

"""The v1.5.0 release bundle against a real cosign, called as the installers
call it.

Releases are signed with cosign v2 and publish cosign's own bundle layout.
The installers run whatever cosign the user has, v2 or v3, and leave every
check of the certificate to it: the exact identity of the release workflow
at the tag, the issuer, and, through ``--certificate-github-workflow-sha``,
the GitHub workflow SHA in the certificate cosign verified, which must be the
signed tag's commit. So the bundle must verify under both cosign lines with
the installers' arguments for v1.5.0 and its commit, and must not verify for
another tag or another commit. The installers' release-mode tests use a stub
cosign; this test is the one that runs the real verifier. The arguments are
read from ``install.sh`` so this test follows any change to them.

Hostile fixtures: ``crafted-A-casekey.json``, ``crafted-B-dupcase.json`` and
``crafted-C-pemprefix.json`` under ``tests/fixtures/release-v1.5.0/`` are
bundles a security reviewer crafted against the installers' former
certificate parsers. Each carries the genuine v1.5.0 certificate and
signature together with a decoy, unsigned certificate that names the commit
``DECOY_COMMIT``, placed where a parser other than cosign's might read it
first: under a ``Cert`` key whose case differs from cosign's (A), as a
duplicate key in another case (B), and as a PEM block that does not start a
line, ahead of the genuine one (C). They are attack inputs, not releases. The
tests show that cosign never accepts them for a commit other than v1.5.0's,
the decoy's included: a decoy cannot make cosign enforce a commit it did not
verify.

The cosign runs need a cosign and network access to Sigstore's trust root,
so they are skipped when no cosign is found. ``APOTHEM_TEST_COSIGN`` names one or more
cosign binaries (separated by the platform's path separator) to run instead
of the ``cosign`` on PATH, so one run can cover cosign v2 and v3.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._shared.release_fixture import (
    FIXTURES,
    V150_BUNDLE,
    V150_COMMIT,
    V150_SUMS,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SH = REPO_ROOT / "scripts" / "installer" / "install.sh"

# The commit the crafted bundles' decoy certificates name.
DECOY_COMMIT = "deadbeef" * 5
# A commit no certificate here names.
OTHER_COMMIT = "0" * 40
CRAFTED_BUNDLES = [
    FIXTURES / "crafted-A-casekey.json",
    FIXTURES / "crafted-B-dupcase.json",
    FIXTURES / "crafted-C-pemprefix.json",
]
WORKFLOW_SHA_REFUSED = "expected GitHub Workflow SHA not found in certificate"
IDENTITY_REFUSED = "none of the expected identities matched"


def _cosigns() -> list[str]:
    named = os.environ.get("APOTHEM_TEST_COSIGN", "")
    if named:
        return [entry for entry in named.split(os.pathsep) if entry]
    found = shutil.which("cosign")
    return [found] if found else []


def _install_sh() -> str:
    return INSTALL_SH.read_text(encoding="utf-8")


def _identity(tag: str) -> str:
    """The certificate identity install.sh builds for TAG."""
    script = _install_sh()
    repo = re.search(r'^COSIGN_IDENTITY_REPO="([^"]+)"$', script, re.M)
    assert repo, "install.sh no longer sets COSIGN_IDENTITY_REPO"
    template = (
        '_ck_identity="https://github.com/${COSIGN_IDENTITY_REPO}'
        '/.github/workflows/release.yml@refs/tags/${APOTHEM_REF}"'
    )
    assert template in script, "install.sh builds the cosign identity differently"
    return (
        f"https://github.com/{repo.group(1)}/.github/workflows/release.yml"
        f"@refs/tags/{tag}"
    )


def _issuer() -> str:
    """The OIDC issuer install.sh pins."""
    issuer = re.search(r'^COSIGN_OIDC_ISSUER="([^"]+)"$', _install_sh(), re.M)
    assert issuer, "install.sh no longer sets COSIGN_OIDC_ISSUER"
    return issuer.group(1)


def _commit_flag() -> str:
    """The cosign flag install.sh passes the signed tag's commit with."""
    flag = re.search(
        r'^\s*(--certificate-github-workflow-sha) "\$_ck_tag_commit" \\$',
        _install_sh(),
        re.M,
    )
    assert flag, "install.sh no longer passes the tag's commit to cosign verify-blob"
    return flag.group(1)


COSIGNS = _cosigns()

requires_cosign = pytest.mark.skipif(not COSIGNS, reason="no cosign to run")


def _verify(
    cosign: str,
    tag: str,
    commit: str,
    tmp_path: Path,
    bundle: Path = V150_BUNDLE,
) -> subprocess.CompletedProcess[str]:
    """Run cosign verify-blob on SHA256SUMS the way install.sh runs it."""
    env = dict(os.environ)
    # cosign caches Sigstore's trust root under HOME; keep it in tmp_path.
    env["HOME"] = str(tmp_path)
    env["USERPROFILE"] = str(tmp_path)
    return subprocess.run(
        [
            cosign,
            "verify-blob",
            "--bundle",
            str(bundle),
            "--certificate-identity",
            _identity(tag),
            "--certificate-oidc-issuer",
            _issuer(),
            _commit_flag(),
            commit,
            str(V150_SUMS),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def test_install_sh_has_cosign_check_the_identity_issuer_and_commit() -> None:
    """The arguments these tests pass are the ones install.sh passes: an
    exact identity (no pattern), the pinned issuer, and the tag's commit."""
    script = _install_sh()
    assert "--certificate-identity-regexp" not in script
    assert "--certificate-oidc-issuer-regexp" not in script
    assert _issuer() == "https://token.actions.githubusercontent.com"
    assert _commit_flag() == "--certificate-github-workflow-sha"


@requires_cosign
@pytest.mark.parametrize("cosign", COSIGNS or ["cosign"])
def test_the_v150_bundle_verifies_for_its_own_tag_and_commit(
    cosign: str, tmp_path: Path
) -> None:
    result = _verify(cosign, "v1.5.0", V150_COMMIT, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Verified OK" in result.stdout + result.stderr


@requires_cosign
@pytest.mark.parametrize("cosign", COSIGNS or ["cosign"])
def test_the_v150_bundle_does_not_verify_for_another_tag(
    cosign: str, tmp_path: Path
) -> None:
    result = _verify(cosign, "v1.4.0", V150_COMMIT, tmp_path)

    assert result.returncode != 0, result.stdout + result.stderr
    assert IDENTITY_REFUSED in result.stdout + result.stderr


@pytest.mark.parametrize("commit", [OTHER_COMMIT, DECOY_COMMIT])
@requires_cosign
@pytest.mark.parametrize("cosign", COSIGNS or ["cosign"])
def test_the_v150_bundle_does_not_verify_for_another_commit(
    cosign: str, commit: str, tmp_path: Path
) -> None:
    """cosign checks the commit against the certificate it verified: the
    v1.5.0 certificate names V150_COMMIT, so any other commit is refused."""
    result = _verify(cosign, "v1.5.0", commit, tmp_path)

    assert result.returncode != 0, result.stdout + result.stderr
    assert WORKFLOW_SHA_REFUSED in result.stdout + result.stderr
    assert "Verified OK" not in result.stdout + result.stderr


@pytest.mark.parametrize("commit", [DECOY_COMMIT, OTHER_COMMIT])
@pytest.mark.parametrize("bundle", CRAFTED_BUNDLES, ids=lambda path: path.stem)
@requires_cosign
@pytest.mark.parametrize("cosign", COSIGNS or ["cosign"])
def test_a_crafted_bundle_never_verifies_for_a_commit_v150_was_not_signed_on(
    cosign: str, bundle: Path, commit: str, tmp_path: Path
) -> None:
    """A decoy certificate in the bundle cannot make cosign enforce the
    decoy's commit, or any commit but the one its verified certificate
    names."""
    assert bundle.is_file(), f"hostile fixture missing: {bundle}"

    result = _verify(cosign, "v1.5.0", commit, tmp_path, bundle=bundle)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "Verified OK" not in combined, combined
