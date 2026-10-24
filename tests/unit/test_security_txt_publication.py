# SPDX-License-Identifier: MIT

"""The published security.txt matches the root copy and reaches GitHub Pages.

RFC 9116 requires a reader to ignore an expired ``security.txt``, and the file's
``Canonical`` URL is a promise that the site serves it. Two things keep that
promise: the site copy (``site/public/.well-known/security.txt``) must stay
byte-identical to the repository copy (``.well-known/security.txt``), and the
Pages deploy must ship the hidden ``.well-known/`` directory, which
``actions/upload-pages-artifact`` leaves out unless told otherwise.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[2]
_ROOT_COPY = _ROOT / ".well-known" / "security.txt"
_SITE_COPY = _ROOT / "site" / "public" / ".well-known" / "security.txt"
_WORKFLOW = _ROOT / ".github" / "workflows" / "publish-static-site.yml"
_UPLOAD_ACTION = "actions/upload-pages-artifact@"


def test_site_copy_is_identical_to_root_copy() -> None:
    assert _ROOT_COPY.is_file(), f"missing: {_ROOT_COPY}"
    assert _SITE_COPY.is_file(), f"missing: {_SITE_COPY}"
    assert _SITE_COPY.read_bytes() == _ROOT_COPY.read_bytes(), (
        "site/public/.well-known/security.txt must match .well-known/security.txt; "
        "update both together"
    )


def test_expires_is_in_the_future() -> None:
    text = _SITE_COPY.read_text(encoding="utf-8")
    match = re.search(r"^Expires: (\S+)$", text, flags=re.MULTILINE)
    assert match, "security.txt must carry an Expires field"
    expires = datetime.fromisoformat(match.group(1).replace("Z", "+00:00"))
    assert expires > datetime.now(timezone.utc), (
        f"security.txt expired on {match.group(1)}; RFC 9116 readers must ignore it"
    )


def _build_steps() -> list[dict]:
    doc = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    return doc["jobs"]["build"]["steps"]


def test_pages_upload_includes_hidden_files() -> None:
    uploads = [
        step
        for step in _build_steps()
        if str(step.get("uses", "")).startswith(_UPLOAD_ACTION)
    ]
    assert len(uploads) == 1, "expected exactly one Pages artifact upload step"
    assert uploads[0].get("with", {}).get("include-hidden-files") is True, (
        "upload-pages-artifact skips dot-prefixed paths unless "
        "include-hidden-files is true, so /.well-known/security.txt would 404"
    )


def test_build_job_asserts_artifact_contains_security_txt() -> None:
    steps = _build_steps()
    upload_index = next(
        i
        for i, step in enumerate(steps)
        if str(step.get("uses", "")).startswith(_UPLOAD_ACTION)
    )
    before = "\n".join(str(s.get("run", "")) for s in steps[:upload_index])
    after = "\n".join(str(s.get("run", "")) for s in steps[upload_index + 1 :])
    assert "site/dist/.well-known/security.txt" in before, (
        "a step before the upload must check the built site holds security.txt"
    )
    message = "a step after the upload must check the archive contains security.txt"
    assert "artifact.tar" in after, message
    assert ".well-known/security.txt" in after, message
