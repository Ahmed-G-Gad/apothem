# SPDX-License-Identifier: MIT

# REUSE-IgnoreStart
"""Fixtures for the installers' release mode: a tagged repository, a stub gpg
and a Sigstore-style bundle whose certificate names a source commit.

Release mode checks two things before it trusts a release's SHA256SUMS: the
release tag carries the maintainer key's signature, and the certificate that
signed SHA256SUMS names the tag's commit in its source-repository-digest
extension (OID 1.3.6.1.4.1.57264.1.19). These helpers build both sides
without a key, a network or a real Sigstore certificate. The certificate is
structurally X.509 but unsigned; the installers read it only after cosign
(a stub in these tests) has accepted the bundle.

``V150_BUNDLE`` and ``V150_SUMS`` are the v1.5.0 release's own files, so a
test can read a real Fulcio certificate.
"""

from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path

from tests._shared.git_env import hermetic_git_env

MAINTAINER_FINGERPRINT = "5C8998F9F241720445D3F28B70396FED9C634163"
OTHER_FINGERPRINT = "C2CD460ED9DCEF33C51123AE984AE72EA84995CA"

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "release-v1.5.0"
V150_BUNDLE = FIXTURES / "SHA256SUMS.cosign.bundle.json"
V150_SUMS = FIXTURES / "SHA256SUMS.txt"
V150_COMMIT = "ee6a157ca5e9c5642a12e41da2d73c577d045dd6"

# Permission bits for stub programs (owner rwx, others rx).
EXECUTABLE_MODE = 0o755

_SOURCE_DIGEST_OID = bytes.fromhex("2b0601040183bf300113")  # 1.3.6.1.4.1.57264.1.19
_ISSUER_OID = bytes.fromhex("2b0601040183bf300101")  # 1.3.6.1.4.1.57264.1.1
_CN_OID = bytes.fromhex("550403")
_ECDSA_SHA256_OID = bytes.fromhex("2a8648ce3d040302")
_EC_PUBLIC_KEY_OID = bytes.fromhex("2a8648ce3d0201")
_P256_OID = bytes.fromhex("2a8648ce3d030107")


def git(args: list[str], cwd: Path) -> str:
    """Run git in CWD without host configuration; return stdout or fail."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env=hermetic_git_env(),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, f"git {args} failed:\n{result.stderr}"
    return result.stdout


def make_tagged_repo(root: Path, tag: str) -> tuple[Path, str]:
    """Create an apothem-shaped repository whose TAG is a tag object with an
    OpenPGP signature block, and return (repository, tagged commit).

    The block is never checked: the installer's git hands it to the stub gpg,
    which replays a canned GnuPG result.
    """
    repo = root / "fixture-repo"
    (repo / "src" / "apothem").mkdir(parents=True)
    (repo / "src" / "apothem" / "__init__.py").write_text(
        "# SPDX-License-Identifier: MIT\n", encoding="utf-8"
    )
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "0.0.0"\n', encoding="utf-8"
    )
    git(["init", "--quiet", "--initial-branch", "main"], repo)
    git(["config", "user.name", "Fixture"], repo)
    git(["config", "user.email", "fixture@example.invalid"], repo)
    git(["config", "commit.gpgsign", "false"], repo)
    git(["add", "-A"], repo)
    git(["commit", "--quiet", "-m", "fixture source"], repo)
    commit = git(["rev-parse", "HEAD"], repo).strip()
    tag_file = root / f"{tag}.tag"
    tag_file.write_text(
        f"object {commit}\n"
        "type commit\n"
        f"tag {tag}\n"
        "tagger Fixture <fixture@example.invalid> 1700000000 +0000\n"
        "\n"
        "signed release\n"
        "-----BEGIN PGP SIGNATURE-----\n"
        "\n"
        "c3R1Yg==\n"
        "-----END PGP SIGNATURE-----\n",
        encoding="utf-8",
        newline="\n",
    )
    tag_sha = git(["hash-object", "-t", "tag", "-w", str(tag_file)], repo).strip()
    git(["update-ref", f"refs/tags/{tag}", tag_sha], repo)
    return repo, commit


def good_signature_status(primary: str) -> str:
    """GnuPG's status lines for a good signature whose primary key is PRIMARY,
    laid out as ``git verify-tag --raw`` prints them for a real release tag."""
    return (
        "[GNUPG:] NEWSIG\n"
        f"[GNUPG:] KEY_CONSIDERED {primary} 0\n"
        f"[GNUPG:] GOODSIG {primary[-16:]} Release Signer <signer@example.invalid>\n"
        f"[GNUPG:] VALIDSIG {primary} 2026-10-28 1793213927 0 4 0 22 10 00 {primary}\n"
        "[GNUPG:] TRUST_ULTIMATE 0 pgp\n"
    )


def write_stub_gpg(stub_dir: Path, status: str, exit_code: int = 0) -> Path:
    """Write a POSIX sh stub gpg that drains stdin, prints STATUS on stdout
    (git's --status-fd=1) and exits EXIT_CODE; return a git config file that
    names it as gpg.program, for GIT_CONFIG_GLOBAL.

    Git for Windows runs the stub through its own sh, so it serves the
    PowerShell installer too.
    """
    stub_dir.mkdir(parents=True, exist_ok=True)
    status_file = stub_dir / "status.txt"
    status_file.write_text(status, encoding="utf-8", newline="\n")
    stub = stub_dir / "gpg"
    stub.write_text(
        "#!/bin/sh\n"
        "cat >/dev/null\n"
        f"cat '{status_file.as_posix()}'\n"
        f"exit {exit_code}\n",
        encoding="utf-8",
        newline="\n",
    )
    stub.chmod(EXECUTABLE_MODE)
    gitconfig = stub_dir / "gitconfig"
    gitconfig.write_text(
        f"[gpg]\n\tprogram = {stub.as_posix()}\n", encoding="utf-8", newline="\n"
    )
    return gitconfig


def _der(tag: int, body: bytes) -> bytes:
    size = len(body)
    if size < 0x80:
        return bytes([tag, size]) + body
    length = size.to_bytes((size.bit_length() + 7) // 8, "big")
    return bytes([tag, 0x80 | len(length)]) + length + body


def _seq(*items: bytes) -> bytes:
    return _der(0x30, b"".join(items))


def _name(common_name: str) -> bytes:
    return _seq(_der(0x31, _seq(_der(0x06, _CN_OID), _der(0x0C, common_name.encode()))))


def fake_certificate(source_commit: str | None) -> bytes:
    """An unsigned X.509 certificate (DER) laid out like a Fulcio one, whose
    source-repository-digest extension names SOURCE_COMMIT; with None, the
    certificate carries other Fulcio extensions but not that one."""
    extensions = [
        _seq(
            _der(0x06, _ISSUER_OID),
            _der(0x04, b"https://token.actions.githubusercontent.com"),
        )
    ]
    if source_commit is not None:
        extensions.append(
            _seq(
                _der(0x06, _SOURCE_DIGEST_OID),
                _der(0x04, _der(0x0C, source_commit.encode("ascii"))),
            )
        )
    algorithm = _seq(_der(0x06, _ECDSA_SHA256_OID))
    tbs = _seq(
        _der(0xA0, _der(0x02, b"\x02")),
        _der(0x02, b"\x01\x23"),
        algorithm,
        _name("sigstore-intermediate"),
        _seq(_der(0x17, b"261028000000Z"), _der(0x17, b"261028001000Z")),
        _seq(),
        _seq(
            _seq(_der(0x06, _EC_PUBLIC_KEY_OID), _der(0x06, _P256_OID)),
            _der(0x03, b"\x00\x04" + b"\x11" * 64),
        ),
        _der(0xA3, _seq(*extensions)),
    )
    return _seq(tbs, algorithm, _der(0x03, b"\x00" + b"\x22" * 70))


def fake_bundle(source_commit: str | None, *, sigstore_format: bool = False) -> str:
    """A bundle around ``fake_certificate(SOURCE_COMMIT)``: cosign's own
    layout (``cert``, a base64 PEM) by default, or the Sigstore bundle
    layout (``verificationMaterial``) with SIGSTORE_FORMAT."""
    der = fake_certificate(source_commit)
    if sigstore_format:
        return json.dumps(
            {
                "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json",
                "verificationMaterial": {
                    "certificate": {"rawBytes": base64.b64encode(der).decode("ascii")}
                },
            }
        )
    body = base64.encodebytes(der).decode("ascii")
    pem = f"-----BEGIN CERTIFICATE-----\n{body}-----END CERTIFICATE-----\n"
    return json.dumps(
        {
            "base64Signature": "c3R1Yg==",
            "cert": base64.b64encode(pem.encode("ascii")).decode("ascii"),
        }
    )


# REUSE-IgnoreEnd
