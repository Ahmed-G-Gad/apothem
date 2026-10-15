# SPDX-License-Identifier: MIT

"""Tests for scripts/release/check-release-ready.{sh,ps1}.

The check gates post-release follow-up work. It once read an SPDX file that
the release never builds, so it could not pass on a real release. These tests
run both shells against a checkout tree shaped like a release: the SBOM comes
from the real generator, run on a wheel and sdist built here, and ``gh`` and
``git`` are replaced by fakes on PATH, so nothing reaches the network or a
real repository.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Final

import pytest

from tests._shared.bash_resolver import SKIP_REASON, find_test_bash

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
RELEASE_DIR: Final[Path] = REPO_ROOT / "scripts" / "release"
GENERATOR: Final[Path] = RELEASE_DIR / "generate_sbom.py"
VENDOR_TXT: Final[Path] = REPO_ROOT / "src" / "apothem" / "_vendor" / "vendor.txt"
SCRIPTS: Final[dict[str, Path]] = {
    "sh": RELEASE_DIR / "check-release-ready.sh",
    "ps1": RELEASE_DIR / "check-release-ready.ps1",
}

VERSION: Final[str] = "9.9.9"
TAG: Final[str] = f"v{VERSION}"
COMMIT: Final[str] = "0123456789abcdef0123456789abcdef01234567"
VENDORED_FILES: Final[tuple[str, ...]] = (
    "attr/__init__.py",
    "attrs/__init__.py",
    "jsonschema/__init__.py",
    "jsonschema_specifications/__init__.py",
    "referencing/__init__.py",
    "typing_extensions.py",
    "yaml/__init__.py",
)

# One Python implementation serves every shell. The launchers forward to it:
# a shebang script for Git Bash and Linux, and .cmd files because PowerShell on
# Windows resolves only PATHEXT extensions. Output is written as bytes so no
# CRLF reaches the script, which would break the exact string comparisons.
_FAKE_GH: Final[str] = """\
import os
import sys

if sys.argv[1:3] == ["release", "view"]:
    sys.stdout.buffer.write(b"false\\tfalse\\n")
elif sys.argv[1:3] == ["run", "list"]:
    conclusion = os.environ.get("FAKE_RUN_CONCLUSION", "success")
    sys.stdout.buffer.write(conclusion.encode() + b"\\n")
else:
    sys.exit(2)
"""
_FAKE_GIT: Final[str] = f"""\
import sys

if sys.argv[1:2] == ["rev-list"]:
    sys.stdout.buffer.write(b"{COMMIT}\\n")
else:
    sys.exit(2)
"""


def _write_launchers(fake_bin: Path) -> None:
    fake_bin.mkdir(parents=True)
    python = sys.executable
    for tool, body, cmd_args in (("gh", _FAKE_GH, "%1 %2"), ("git", _FAKE_GIT, "%*")):
        impl = fake_bin / f"{tool}_fake.py"
        impl.write_text(body, encoding="utf-8", newline="\n")
        posix = fake_bin / tool
        posix.write_text(
            f'#!/bin/sh\nexec "{Path(python).as_posix()}" "{impl.as_posix()}" "$@"\n',
            encoding="utf-8",
            newline="\n",
        )
        posix.chmod(0o755)
        (fake_bin / f"{tool}.cmd").write_text(
            f'@echo off\r\n"{python}" "{impl}" {cmd_args}\r\n',
            encoding="utf-8",
            newline="",
        )


@pytest.fixture
def fake_bin(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    _write_launchers(bin_dir)
    return bin_dir


def _build_dist(tmp: Path) -> Path:
    """Write a wheel and sdist shaped like the release's distributions."""
    dist = tmp / "built"
    dist.mkdir()
    metadata = (
        "Metadata-Version: 2.4\n"
        f"Name: apothem\nVersion: {VERSION}\n"
        "License-Expression: MIT\n"
        "Requires-Dist: pyyaml>=6.0.3\n"
    )
    with zipfile.ZipFile(dist / f"apothem-{VERSION}-py3-none-any.whl", "w") as wheel:
        wheel.writestr(f"apothem-{VERSION}.dist-info/METADATA", metadata)
        for rel in VENDORED_FILES:
            wheel.writestr(f"apothem/_vendor/{rel}", "")
    with tarfile.open(dist / f"apothem-{VERSION}.tar.gz", "w:gz") as sdist:
        data = VENDOR_TXT.read_bytes()
        info = tarfile.TarInfo(f"apothem-{VERSION}/src/apothem/_vendor/vendor.txt")
        info.size = len(data)
        sdist.addfile(info, io.BytesIO(data))
    return dist


def _sbom_path(root: Path) -> Path:
    return root / "dist" / "release-assets" / "sbom.cdx.json"


def _checkout(tmp: Path, *, with_sbom: bool = True) -> Path:
    """Lay out a checkout with both scripts and the release's SBOM."""
    root = tmp / "checkout"
    for path in SCRIPTS.values():
        target = root / "scripts" / "release" / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    if with_sbom:
        sbom = _sbom_path(root)
        sbom.parent.mkdir(parents=True)
        completed = subprocess.run(
            [
                sys.executable,
                str(GENERATOR),
                "--dist",
                str(_build_dist(tmp)),
                "--output",
                str(sbom),
            ],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "SOURCE_DATE_EPOCH": "1700000000"},
        )
        assert completed.returncode == 0, completed.stderr
    return root


def _bash_path(path: Path) -> str:
    """Spell a path the way Git Bash reads it (``C:/x`` becomes ``/c/x``)."""
    posix = path.as_posix()
    if len(posix) > 1 and posix[1] == ":":
        return f"/{posix[0].lower()}{posix[2:]}"
    return posix


def _run(
    shell: str,
    root: Path,
    fake_bin: Path,
    *,
    env: dict[str, str | None] | None = None,
) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    run_env["PATH"] = f"{fake_bin}{os.pathsep}{run_env.get('PATH', '')}"
    # A placeholder: the fake gh ignores it, and the script only checks it is set.
    run_env["GH_TOKEN"] = "placeholder"  # noqa: S105
    for key, value in (env or {}).items():
        if value is None:
            run_env.pop(key, None)
        else:
            run_env[key] = value
    script = root / "scripts" / "release" / SCRIPTS[shell].name
    if shell == "sh":
        bash = find_test_bash()
        if bash is None:
            pytest.skip(SKIP_REASON)
        # Git Bash rebuilds PATH at startup and puts its own directories ahead
        # of the inherited entries, so the fakes must be placed on PATH inside
        # the shell. The script is sourced so the shell is the one that owns
        # the fakes; it exits with the script's status.
        argv = [
            bash,
            "-c",
            'export PATH="$2:$PATH"; script="$1"; set -- "$3"; . "$script"',
            "check-release-ready",
            str(script),
            _bash_path(fake_bin),
            TAG,
        ]
    else:
        pwsh = shutil.which("pwsh")
        if pwsh is None:
            pytest.skip("pwsh is not on PATH")
        argv = [pwsh, "-NoProfile", "-NonInteractive", "-File", str(script), TAG]
    return subprocess.run(
        argv,
        cwd=root,
        env=run_env,
        capture_output=True,
        text=True,
        check=False,
    )


def _output(result: subprocess.CompletedProcess[str]) -> str:
    """Combined output with whitespace collapsed, so console wrapping is harmless."""
    return " ".join((result.stdout + result.stderr).split())


def _edit_sbom(root: Path, edit: object) -> None:
    path = _sbom_path(root)
    sbom = json.loads(path.read_text(encoding="utf-8"))
    edit(sbom)  # type: ignore[operator]
    path.write_text(json.dumps(sbom), encoding="utf-8")


SHELLS = pytest.mark.parametrize("shell", ["sh", "ps1"], ids=["bash", "pwsh"])


@SHELLS
def test_passes_on_a_release_shaped_checkout(
    shell: str, tmp_path: Path, fake_bin: Path
) -> None:
    root = _checkout(tmp_path)
    result = _run(shell, root, fake_bin)
    assert result.returncode == 0, _output(result)
    assert "release checks are green" in _output(result)


@SHELLS
def test_fails_when_the_sbom_is_missing(
    shell: str, tmp_path: Path, fake_bin: Path
) -> None:
    root = _checkout(tmp_path, with_sbom=False)
    result = _run(shell, root, fake_bin)
    assert result.returncode == 1
    assert "SBOM not found" in _output(result)


@SHELLS
def test_fails_when_a_vendored_package_is_missing(
    shell: str, tmp_path: Path, fake_bin: Path
) -> None:
    root = _checkout(tmp_path)
    _edit_sbom(
        root,
        lambda sbom: sbom.update(
            components=[c for c in sbom["components"] if c.get("name") != "pyyaml"]
        ),
    )
    result = _run(shell, root, fake_bin)
    assert result.returncode == 1
    assert "vendored packages missing from SBOM: pyyaml" in _output(result)


@SHELLS
def test_fails_for_an_sbom_of_another_version(
    shell: str, tmp_path: Path, fake_bin: Path
) -> None:
    root = _checkout(tmp_path)

    def stale(sbom: dict[str, object]) -> None:
        component = sbom["metadata"]["component"]  # type: ignore[index]
        component["version"] = "9.9.8"  # type: ignore[index]
        component["purl"] = "pkg:pypi/apothem@9.9.8"  # type: ignore[index]

    _edit_sbom(root, stale)
    result = _run(shell, root, fake_bin)
    assert result.returncode == 1
    assert "not apothem 9.9.9" in _output(result)


@SHELLS
def test_fails_when_a_required_workflow_is_not_green(
    shell: str, tmp_path: Path, fake_bin: Path
) -> None:
    root = _checkout(tmp_path)
    result = _run(shell, root, fake_bin, env={"FAKE_RUN_CONCLUSION": "failure"})
    assert result.returncode == 1
    assert "ci.yml is not green" in _output(result)


@SHELLS
def test_requires_gh_token(shell: str, tmp_path: Path, fake_bin: Path) -> None:
    root = _checkout(tmp_path)
    result = _run(shell, root, fake_bin, env={"GH_TOKEN": None})
    assert result.returncode == 1
    assert "GH_TOKEN is required" in _output(result)


def test_both_shells_check_the_same_workflows_and_vendored_packages() -> None:
    texts = {shell: path.read_text(encoding="utf-8") for shell, path in SCRIPTS.items()}
    sh_block = re.search(r"required_workflows=\((.*?)\n\)", texts["sh"], re.S)
    ps_block = re.search(r"\$requiredWorkflows = @\((.*?)\n\)", texts["ps1"], re.S)
    assert sh_block is not None
    assert ps_block is not None
    sh_workflows = re.findall(r"[\w.-]+\.yml", sh_block[1])
    assert sh_workflows == re.findall(r"'([\w.-]+\.yml)'", ps_block[1])

    pattern = re.compile(r"required = \(([^)]*)\)")
    sh_required = pattern.search(texts["sh"])
    ps_required = pattern.search(texts["ps1"])
    assert sh_required is not None
    assert ps_required is not None
    sh_names = re.findall(r'"([^"]+)"', sh_required[1])
    assert sh_names == re.findall(r'"([^"]+)"', ps_required[1])

    sys.path.insert(0, str(RELEASE_DIR))
    try:
        import generate_sbom
    finally:
        sys.path.remove(str(RELEASE_DIR))
    shipped = {name for name, entry in generate_sbom.VENDORED.items() if entry}
    assert set(sh_names) <= shipped, "the check names a package the SBOM never lists"


def test_both_shells_read_the_cyclonedx_sbom_the_release_publishes() -> None:
    for shell, path in SCRIPTS.items():
        text = path.read_text(encoding="utf-8")
        assert "sbom.cdx.json" in text, shell
        assert "release-assets" in text, shell
        assert "CycloneDX" in text, shell
        assert ".spdx.json" not in text, shell
