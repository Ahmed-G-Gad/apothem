# SPDX-License-Identifier: MIT

"""Tests for scripts/release/generate_sbom.py.

The release SBOM used to describe the repository checkout: npm packages of the
docs site and the build toolchain, but none of the third-party code the wheel
ships under ``apothem/_vendor``, and no apothem root component. The generator
now reads the built distributions. These tests build a small wheel and sdist
shaped like the real ones and pin what the SBOM must say.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "release"))

import generate_sbom  # noqa: E402

VERSION = "9.9.9"
VENDOR_TXT = """\
# comment
attrs==26.1.0
jsonschema==4.26.0
jsonschema-specifications==2025.9.1
referencing==0.37.0
typing_extensions==4.15.0
PyYAML==6.0.3
rpds-py==0.30.0  # upstream API anchor for the apothem-authored rpds shim
"""
VENDORED_PATHS = (
    "attr/__init__.py",
    "attrs/__init__.py",
    "jsonschema/__init__.py",
    "jsonschema_specifications/__init__.py",
    "referencing/__init__.py",
    "typing_extensions.py",
    "yaml/__init__.py",
    "rpds/__init__.py",
)
METADATA = f"""\
Metadata-Version: 2.4
Name: apothem
Version: {VERSION}
License-Expression: MIT AND PSF-2.0
Requires-Dist: click==8.4.2
Requires-Dist: rich>=15.0.0
Requires-Dist: pyyaml>=6.0.3
Requires-Dist: jsonschema>=4.26.0
Requires-Dist: pytest>=9; extra == "dev"
"""


def _dist(tmp_path: Path, *, vendored: tuple[str, ...] = VENDORED_PATHS) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    with zipfile.ZipFile(dist / f"apothem-{VERSION}-py3-none-any.whl", "w") as wheel:
        wheel.writestr(f"apothem-{VERSION}.dist-info/METADATA", METADATA)
        wheel.writestr("apothem/__init__.py", "")
        for rel in vendored:
            wheel.writestr(f"apothem/_vendor/{rel}", "")
    with tarfile.open(dist / f"apothem-{VERSION}.tar.gz", "w:gz") as sdist:
        data = VENDOR_TXT.encode()
        info = tarfile.TarInfo(f"apothem-{VERSION}/src/apothem/_vendor/vendor.txt")
        info.size = len(data)
        sdist.addfile(info, io.BytesIO(data))
    return dist


def _generate(dist: Path, tmp_path: Path, *extra: str) -> dict[str, Any]:
    out = tmp_path / "sbom.cdx.json"
    assert generate_sbom.main(["--dist", str(dist), "--output", str(out), *extra]) == 0
    return json.loads(out.read_text(encoding="utf-8"))


def _purls(sbom: dict[str, Any]) -> set[str]:
    return {c["purl"] for c in sbom["components"] if "purl" in c}


def test_root_component_is_the_shipped_package(tmp_path: Path) -> None:
    sbom = _generate(_dist(tmp_path), tmp_path)
    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.6"
    root = sbom["metadata"]["component"]
    assert root["name"] == "apothem"
    assert root["version"] == VERSION
    assert root["purl"] == f"pkg:pypi/apothem@{VERSION}"
    assert root["licenses"] == [{"expression": "MIT AND PSF-2.0"}]


def test_vendored_and_declared_packages_are_listed(tmp_path: Path) -> None:
    purls = _purls(_generate(_dist(tmp_path), tmp_path))
    for expected in (
        "pkg:pypi/pyyaml@6.0.3",
        "pkg:pypi/jsonschema@4.26.0",
        "pkg:pypi/attrs@26.1.0",
        "pkg:pypi/referencing@0.37.0",
        "pkg:pypi/jsonschema-specifications@2025.9.1",
        "pkg:pypi/typing-extensions@4.15.0",
        "pkg:pypi/click@8.4.2",
        "pkg:pypi/rich",
    ):
        assert expected in purls, expected


def test_shim_anchor_and_extras_are_not_components(tmp_path: Path) -> None:
    purls = _purls(_generate(_dist(tmp_path), tmp_path))
    assert not any("rpds" in p for p in purls), "the rpds shim is apothem's own code"
    assert not any("pytest" in p for p in purls), "extras are not shipped"


def test_vendored_licenses_come_through(tmp_path: Path) -> None:
    sbom = _generate(_dist(tmp_path), tmp_path)
    by_name = {c["name"]: c for c in sbom["components"]}
    assert by_name["typing-extensions"]["licenses"] == [{"license": {"id": "PSF-2.0"}}]
    assert by_name["pyyaml"]["licenses"] == [{"license": {"id": "MIT"}}]


def test_distribution_files_carry_their_digests(tmp_path: Path) -> None:
    dist = _dist(tmp_path)
    sbom = _generate(dist, tmp_path)
    files = {c["name"]: c for c in sbom["components"] if c["type"] == "file"}
    for name in (f"apothem-{VERSION}-py3-none-any.whl", f"apothem-{VERSION}.tar.gz"):
        digest = hashlib.sha256((dist / name).read_bytes()).hexdigest()
        assert files[name]["hashes"] == [{"alg": "SHA-256", "content": digest}]


def test_platform_archives_beside_the_dist_are_ignored(tmp_path: Path) -> None:
    dist = _dist(tmp_path)
    (dist / f"apothem-v{VERSION}-linux.tar.gz").write_bytes(b"archive")
    sbom = _generate(dist, tmp_path)
    files = {c["name"] for c in sbom["components"] if c["type"] == "file"}
    assert files == {f"apothem-{VERSION}-py3-none-any.whl", f"apothem-{VERSION}.tar.gz"}


def test_root_depends_on_every_library(tmp_path: Path) -> None:
    sbom = _generate(_dist(tmp_path), tmp_path)
    libraries = {c["bom-ref"] for c in sbom["components"] if c["type"] == "library"}
    (root_deps,) = [
        d
        for d in sbom["dependencies"]
        if d["ref"] == sbom["metadata"]["component"]["bom-ref"]
    ]
    assert set(root_deps["dependsOn"]) == libraries


def test_output_is_deterministic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1790000000")
    dist = _dist(tmp_path)
    first = json.dumps(_generate(dist, tmp_path), sort_keys=True)
    second = json.dumps(_generate(dist, tmp_path), sort_keys=True)
    assert first == second
    assert json.loads(first)["metadata"]["timestamp"] == "2026-09-21T14:13:20Z"


def test_missing_vendored_module_fails(tmp_path: Path) -> None:
    dist = _dist(tmp_path, vendored=tuple(p for p in VENDORED_PATHS if "yaml" not in p))
    out = tmp_path / "sbom.cdx.json"
    assert generate_sbom.main(["--dist", str(dist), "--output", str(out)]) == 1


def test_unknown_vendored_package_fails(tmp_path: Path) -> None:
    dist = _dist(tmp_path)
    vendor = tmp_path / "vendor.txt"
    vendor.write_text(VENDOR_TXT + "newpkg==1.0\n", encoding="utf-8")
    out = tmp_path / "sbom.cdx.json"
    args = ["--dist", str(dist), "--output", str(out), "--vendor-txt", str(vendor)]
    assert generate_sbom.main(args) == 1


def test_license_map_agrees_with_reuse() -> None:
    """The generator's vendored licenses match REUSE.toml's annotations."""
    tomllib = pytest.importorskip("tomllib")
    reuse = tomllib.loads((REPO_ROOT / "REUSE.toml").read_text(encoding="utf-8"))
    by_path: dict[str, str] = {}
    for annotation in reuse["annotations"]:
        paths = annotation["path"]
        for path in [paths] if isinstance(paths, str) else paths:
            by_path[path] = annotation["SPDX-License-Identifier"]
    for name, entry in generate_sbom.VENDORED.items():
        if entry is None:
            continue
        license_id, modules = entry
        for module in modules:
            key = f"src/apothem/_vendor/{module}"
            key = key + "**" if key.endswith("/") else key
            assert by_path.get(key) == license_id, f"{name}: {key}"


def test_vendored_map_covers_the_real_vendor_txt() -> None:
    pins = generate_sbom.parse_pins(
        (REPO_ROOT / "src" / "apothem" / "_vendor" / "vendor.txt").read_text(
            encoding="utf-8"
        )
    )
    assert set(pins) == set(generate_sbom.VENDORED)
