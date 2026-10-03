# SPDX-License-Identifier: MIT

"""Tests for scripts/release/verify-provenance.{sh,ps1} and the documented
verification identity.

The documented verification failed on genuine v1.1.0 assets: the identity used
the lowercase owner while Sigstore certificates carry ``Ahmed-G-Gad``, the
documented regexp was unanchored, and the script looked for ``.sig``/``.crt``
pairs and per-artifact provenance files the release never ships. These tests
run the POSIX script against fake ``cosign`` and ``slsa-verifier`` binaries
that record their arguments, and check every documented identity pattern
against a forged certificate subject.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path
from typing import Final

import pytest

from tests._shared.bash_resolver import SKIP_REASON, find_test_bash

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
SH_SCRIPT: Final[Path] = REPO_ROOT / "scripts" / "release" / "verify-provenance.sh"
PS1_SCRIPT: Final[Path] = REPO_ROOT / "scripts" / "release" / "verify-provenance.ps1"

VERSION = "9.9.9"
TAG = f"v{VERSION}"
IDENTITY = (
    "https://github.com/Ahmed-G-Gad/apothem/.github/workflows/release.yml"
    f"@refs/tags/{TAG}"
)
GENUINE_SAN = IDENTITY
FORGED_SAN = (
    "https://github.com/evil/x/.github/workflows/y.yml@refs/heads/"
    "github.com/Ahmed-G-Gad/apothem/.github/workflows/release.yml@refs/tags/v1.1.0"
)

_FAKE_TOOL = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "{log}"
exit "${{FAKE_{name}_EXIT:-0}}"
"""


def _fake_bin(tmp_path: Path) -> tuple[Path, Path]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "calls.log"
    for tool, name in (("cosign", "COSIGN"), ("slsa-verifier", "SLSA")):
        path = fake_bin / tool
        path.write_text(
            _FAKE_TOOL.format(log=log, name=name), encoding="utf-8", newline="\n"
        )
        path.chmod(0o755)
    return fake_bin, log


def _release_dir(tmp_path: Path, *, legacy_archive_sigs: bool = True) -> Path:
    """Lay out a release asset set shaped like the published one."""
    assets = tmp_path / "assets"
    assets.mkdir()
    wheel = f"apothem-{VERSION}-py3-none-any.whl"
    sdist = f"apothem-{VERSION}.tar.gz"
    archives = [f"apothem-{TAG}-linux.tar.gz", f"apothem-{TAG}-windows.zip"]
    for name in (wheel, sdist, *archives):
        (assets / name).write_bytes(name.encode())
    for name in (wheel, sdist):
        (assets / f"{name}.cosign.bundle").write_text("{}", encoding="utf-8")
    suffix = ".sig" if legacy_archive_sigs else ".cosign.bundle"
    sums = "".join(
        f"{hashlib.sha256(name.encode()).hexdigest()}  {name}\n" for name in archives
    )
    (assets / "SHA256SUMS").write_text(sums, encoding="utf-8", newline="\n")
    for name in (*archives, "SHA256SUMS"):
        (assets / f"{name}{suffix}").write_text("{}", encoding="utf-8")
    (assets / "provenance.intoto.jsonl").write_text("{}\n", encoding="utf-8")
    return assets


def _run(
    assets: Path, fake_bin: Path, *args: str, **env_extra: str
) -> subprocess.CompletedProcess[str]:
    bash = find_test_bash()
    if bash is None:
        pytest.skip(SKIP_REASON)
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
    for key in ("APOTHEM_RELEASE_TAG", "APOTHEM_GITHUB_REPO"):
        env.pop(key, None)
    env.update(env_extra)
    return subprocess.run(
        [bash, str(SH_SCRIPT), *args, str(assets)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _calls(log: Path, tool_marker: str) -> list[str]:
    if not log.exists():
        return []
    return [
        line for line in log.read_text().splitlines() if line.startswith(tool_marker)
    ]


def test_verifies_every_signed_asset_with_the_exact_identity(tmp_path: Path) -> None:
    fake_bin, log = _fake_bin(tmp_path)
    assets = _release_dir(tmp_path)
    result = _run(assets, fake_bin)
    assert result.returncode == 0, result.stderr
    cosign = _calls(log, "verify-blob")
    assert len(cosign) == 5, cosign  # wheel, sdist, 2 archives, SHA256SUMS
    for call in cosign:
        assert "--bundle" in call
        assert f"--certificate-identity {IDENTITY}" in call
        assert (
            "--certificate-oidc-issuer https://token.actions.githubusercontent.com"
            in call
        )
        assert "identity-regexp" not in call
    signed = {call.rsplit(" ", 1)[1] for call in cosign}
    assert "SHA256SUMS" in signed
    assert f"apothem-{TAG}-linux.tar.gz" in signed


def test_slsa_layer_uses_the_single_provenance_and_mixed_case_source(
    tmp_path: Path,
) -> None:
    fake_bin, log = _fake_bin(tmp_path)
    assets = _release_dir(tmp_path)
    assert _run(assets, fake_bin).returncode == 0
    slsa = _calls(log, "verify-artifact")
    assert len(slsa) == 1, slsa
    call = slsa[0]
    assert "--provenance-path provenance.intoto.jsonl" in call
    assert "--source-uri github.com/Ahmed-G-Gad/apothem" in call
    assert f"--source-tag {TAG}" in call
    assert f"apothem-{VERSION}-py3-none-any.whl" in call
    assert f"apothem-{VERSION}.tar.gz" in call
    assert "linux.tar.gz" not in call, "platform archives are not provenance subjects"


def test_accepts_new_style_archive_bundles(tmp_path: Path) -> None:
    fake_bin, log = _fake_bin(tmp_path)
    assets = _release_dir(tmp_path, legacy_archive_sigs=False)
    assert _run(assets, fake_bin).returncode == 0
    assert len(_calls(log, "verify-blob")) == 5


def test_signed_sbom_is_verified_and_a_provenance_subject(tmp_path: Path) -> None:
    """New releases build, sign and hash the SBOM with the distributions."""
    fake_bin, log = _fake_bin(tmp_path)
    assets = _release_dir(tmp_path, legacy_archive_sigs=False)
    (assets / "sbom.cdx.json").write_text("{}", encoding="utf-8")
    (assets / "sbom.cdx.json.cosign.bundle").write_text("{}", encoding="utf-8")
    assert _run(assets, fake_bin).returncode == 0
    assert any(c.endswith(" sbom.cdx.json") for c in _calls(log, "verify-blob"))
    (slsa,) = _calls(log, "verify-artifact")
    assert "sbom.cdx.json" in slsa


def test_unsigned_legacy_sbom_is_skipped(tmp_path: Path) -> None:
    """Releases up to v1.1.0 shipped an unsigned SBOM outside the provenance."""
    fake_bin, log = _fake_bin(tmp_path)
    assets = _release_dir(tmp_path)
    (assets / "sbom.cdx.json").write_text("{}", encoding="utf-8")
    assert _run(assets, fake_bin).returncode == 0
    assert not any("sbom" in c for c in _calls(log, "verify-blob"))
    (slsa,) = _calls(log, "verify-artifact")
    assert "sbom.cdx.json" not in slsa


def test_explicit_tag_overrides_the_derived_one(tmp_path: Path) -> None:
    fake_bin, log = _fake_bin(tmp_path)
    assets = _release_dir(tmp_path)
    assert _run(assets, fake_bin, "--tag", "v9.9.8").returncode == 0
    assert all("refs/tags/v9.9.8" in c for c in _calls(log, "verify-blob"))


def test_unsigned_release_asset_fails(tmp_path: Path) -> None:
    fake_bin, _ = _fake_bin(tmp_path)
    assets = _release_dir(tmp_path)
    (assets / f"apothem-{VERSION}.tar.gz.cosign.bundle").unlink()
    result = _run(assets, fake_bin)
    assert result.returncode == 1
    assert "no signature bundle" in result.stderr


def test_cosign_failure_fails_the_chain(tmp_path: Path) -> None:
    fake_bin, _ = _fake_bin(tmp_path)
    assets = _release_dir(tmp_path)
    assert _run(assets, fake_bin, FAKE_COSIGN_EXIT="1").returncode == 1


def test_slsa_failure_fails_the_chain(tmp_path: Path) -> None:
    fake_bin, _ = _fake_bin(tmp_path)
    assets = _release_dir(tmp_path)
    assert _run(assets, fake_bin, FAKE_SLSA_EXIT="1").returncode == 1


def test_checksum_mismatch_fails(tmp_path: Path) -> None:
    fake_bin, _ = _fake_bin(tmp_path)
    assets = _release_dir(tmp_path)
    (assets / f"apothem-{TAG}-linux.tar.gz").write_bytes(b"tampered")
    assert _run(assets, fake_bin).returncode == 1


def test_no_tag_derivable_fails(tmp_path: Path) -> None:
    fake_bin, _ = _fake_bin(tmp_path)
    assets = _release_dir(tmp_path)
    (assets / f"apothem-{VERSION}-py3-none-any.whl").unlink()
    (assets / f"apothem-{VERSION}-py3-none-any.whl.cosign.bundle").unlink()
    result = _run(assets, fake_bin)
    assert result.returncode == 1
    assert "--tag" in result.stderr


# --- documented identity patterns --------------------------------------------

_DOCS = (
    REPO_ROOT / "site" / "content" / "docs" / "runbooks" / "release-cycle.mdx",
    REPO_ROOT / "site" / "content" / "docs" / "security" / "index.mdx",
    REPO_ROOT / "SECURITY.md",
    SH_SCRIPT,
    PS1_SCRIPT,
)
_REGEXP_ARG = re.compile(r"--certificate-identity-regexp\s+['\"]([^'\"]+)['\"]")


def _documented_regexps() -> list[str]:
    found: list[str] = []
    for path in _DOCS:
        found.extend(_REGEXP_ARG.findall(path.read_text(encoding="utf-8")))
    return found


def test_documented_regexps_are_anchored_and_reject_a_forged_subject() -> None:
    patterns = _documented_regexps()
    assert patterns, "the security page documents an anchored regexp for any tag"
    for pattern in patterns:
        assert pattern.startswith("^"), f"{pattern} is not anchored at the start"
        assert pattern.endswith("$"), f"{pattern} is not anchored at the end"
        assert re.search(pattern, GENUINE_SAN), f"{pattern} rejects the genuine SAN"
        assert re.search(pattern, FORGED_SAN) is None, f"{pattern} accepts a forgery"


_LOWERCASE_IDENTITY = re.compile(
    r"--(?:certificate-identity(?:-regexp)?|source-uri)[ =]+['\"]?[^\s'\"]*"
    r"ahmed-g-gad/apothem"
)


def test_docs_use_the_certificate_owner_casing() -> None:
    """Identity checks are case-sensitive; certificates say Ahmed-G-Gad."""
    for path in _DOCS:
        text = path.read_text(encoding="utf-8")
        assert _LOWERCASE_IDENTITY.search(text) is None, path


def test_ps1_sibling_matches_the_posix_contract() -> None:
    text = PS1_SCRIPT.read_text(encoding="utf-8")
    assert "Ahmed-G-Gad/apothem" in text
    assert "--bundle" in text
    assert "--certificate-identity" in text
    assert "--certificate-identity-regexp" not in text
    assert "provenance.intoto.jsonl" in text
    assert "--source-tag" in text
