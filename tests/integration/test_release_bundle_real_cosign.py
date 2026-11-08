# SPDX-License-Identifier: MIT

"""The v1.5.0 release bundle against a real cosign, called as the installers
call it.

Releases are signed with cosign v2 and publish cosign's own bundle layout.
The installers run whatever cosign the user has, v2 or v3, so the bundle must
verify under both with the installers' exact identity, and the identity for
another tag must not. The installers' release-mode tests use a stub cosign;
this test is the one that runs the real verifier.

It needs a cosign and network access to Sigstore's trust root, so it is
skipped when no cosign is found. ``APOTHEM_TEST_COSIGN`` names one or more
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

from tests._shared.release_fixture import V150_BUNDLE, V150_SUMS

REPO_ROOT = Path(__file__).resolve().parents[2]
ISSUER = "https://token.actions.githubusercontent.com"


def _cosigns() -> list[str]:
    named = os.environ.get("APOTHEM_TEST_COSIGN", "")
    if named:
        return [entry for entry in named.split(os.pathsep) if entry]
    found = shutil.which("cosign")
    return [found] if found else []


def _identity(tag: str) -> str:
    """The certificate identity install.sh builds for TAG, read from the
    script so this test follows any change to it."""
    script = (REPO_ROOT / "scripts" / "installer" / "install.sh").read_text(
        encoding="utf-8"
    )
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


COSIGNS = _cosigns()

pytestmark = pytest.mark.skipif(not COSIGNS, reason="no cosign to run")


def _verify(cosign: str, tag: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    # cosign caches Sigstore's trust root under HOME; keep it in tmp_path.
    env["HOME"] = str(tmp_path)
    env["USERPROFILE"] = str(tmp_path)
    return subprocess.run(
        [
            cosign,
            "verify-blob",
            "--bundle",
            str(V150_BUNDLE),
            "--certificate-identity",
            _identity(tag),
            "--certificate-oidc-issuer",
            ISSUER,
            str(V150_SUMS),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


@pytest.mark.parametrize("cosign", COSIGNS or ["cosign"])
def test_the_v150_bundle_verifies_for_its_own_tag(cosign: str, tmp_path: Path) -> None:
    result = _verify(cosign, "v1.5.0", tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Verified OK" in result.stdout + result.stderr


@pytest.mark.parametrize("cosign", COSIGNS or ["cosign"])
def test_the_v150_bundle_does_not_verify_for_another_tag(
    cosign: str, tmp_path: Path
) -> None:
    result = _verify(cosign, "v1.4.0", tmp_path)

    assert result.returncode != 0, result.stdout + result.stderr
    assert "none of the expected identities matched" in result.stdout + result.stderr
