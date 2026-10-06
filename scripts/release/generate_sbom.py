# SPDX-License-Identifier: MIT

"""Write a CycloneDX SBOM describing the built apothem distributions.

Why this script exists. The release SBOM was produced by scanning the
repository checkout. It listed the docs site's npm packages and the build
toolchain as if they shipped, and none of the third-party code the wheel
actually carries under ``apothem/_vendor``: the vendored trees have no
``*.dist-info``, so a scanner cannot see them. It also had no apothem root
component. A vulnerability scanner reading it missed PyYAML, jsonschema and
the rest.

This generator reads what ships instead:

- the wheel's ``METADATA`` for the package name, version, license expression
  and declared runtime requirements (extras are skipped);
- the vendored pins in ``src/apothem/_vendor/vendor.txt``, read from the sdist
  (or ``--vendor-txt``), each checked against the wheel: every vendored
  package's modules must be present under ``apothem/_vendor/``;
- the SHA-256 of every wheel and sdist, recorded as file components.

The output is deterministic: no random serial number, and the timestamp comes
from ``SOURCE_DATE_EPOCH`` when it is set. Stdlib only.

Usage::

    python scripts/release/generate_sbom.py --dist dist --output dist/sbom.cdx.json

Exit codes: ``0`` on success, ``1`` when the distributions disagree with the
vendored pins or cannot be read, ``2`` on a usage error.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import email.parser
import hashlib
import json
import os
import re
import sys
import tarfile
import uuid
import zipfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDOR_TXT_REL = "src/apothem/_vendor/vendor.txt"

#: Every package pinned in vendor.txt, by normalized name: its SPDX license
#: (as REUSE.toml annotates the vendored tree; a test holds the two together)
#: and the module paths under ``apothem/_vendor/`` that ship it. ``None`` marks
#: a pin that is not shipped third-party code. A new pin without an entry here
#: fails the run, so the SBOM cannot silently drop a vendored package.
VENDORED: dict[str, tuple[str, tuple[str, ...]] | None] = {
    "attrs": ("MIT", ("attr/", "attrs/")),
    "jsonschema": ("MIT", ("jsonschema/",)),
    "jsonschema-specifications": ("MIT", ("jsonschema_specifications/",)),
    "referencing": ("MIT", ("referencing/",)),
    "typing-extensions": ("PSF-2.0", ("typing_extensions.py",)),
    "pyyaml": ("MIT", ("yaml/",)),
    # The rpds module is an apothem-authored shim; its pin only records the
    # upstream rpds-py API it mirrors. It is apothem code, not a dependency.
    "rpds-py": None,
}

_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s#;]+)")
_REQUIREMENT = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*(.*)$")


class SbomError(RuntimeError):
    """The distributions cannot be described consistently."""


def normalize(name: str) -> str:
    """PEP 503 name normalization, as the pypi purl type requires."""
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_pins(text: str) -> dict[str, str]:
    """Return ``{normalized name: version}`` for every ``name==version`` line."""
    pins: dict[str, str] = {}
    for line in text.splitlines():
        match = _PIN.match(line.strip())
        if match:
            pins[normalize(match[1])] = match[2]
    return pins


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _single(dist: Path, pattern: str) -> Path:
    matches = sorted(dist.glob(pattern))
    if len(matches) != 1:
        raise SbomError(f"expected one {pattern} in {dist}, found {len(matches)}")
    return matches[0]


def _wheel_facts(wheel: Path) -> tuple[dict[str, Any], set[str]]:
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        metadata_names = [n for n in names if n.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise SbomError(f"{wheel.name}: expected one dist-info/METADATA")
        raw = archive.read(metadata_names[0]).decode("utf-8")
    message = email.parser.Parser().parsestr(raw, headersonly=True)
    facts = {
        "name": message["Name"],
        "version": message["Version"],
        "license": message["License-Expression"] or message["License"],
        "requires": message.get_all("Requires-Dist") or [],
    }
    return facts, names


def _vendor_text(sdist: Path | None, override: Path | None) -> str:
    if override is not None:
        return override.read_text(encoding="utf-8")
    if sdist is not None:
        with tarfile.open(sdist) as archive:
            for member in archive.getmembers():
                if member.name.endswith(f"/{VENDOR_TXT_REL}"):
                    handle = archive.extractfile(member)
                    if handle is not None:
                        return handle.read().decode("utf-8")
    fallback = REPO_ROOT / VENDOR_TXT_REL
    if fallback.is_file():
        return fallback.read_text(encoding="utf-8")
    raise SbomError(f"no {VENDOR_TXT_REL} in the sdist or the checkout")


def _library(name: str, version: str | None, **extra: object) -> dict[str, Any]:
    purl = f"pkg:pypi/{name}" + (f"@{version}" if version else "")
    component: dict[str, Any] = {"type": "library", "bom-ref": purl, "name": name}
    if version:
        component["version"] = version
    component["purl"] = purl
    component.update(extra)
    return component


def build_sbom(dist: Path, vendor_txt: Path | None = None) -> dict[str, Any]:
    """Return the CycloneDX document for the distributions in *dist*."""
    wheel = _single(dist, "*.whl")
    facts, names = _wheel_facts(wheel)
    # The sdist matching the wheel; platform archives (apothem-vX.Y.Z-*.tar.gz)
    # may share the directory and are not Python distributions.
    sdist_path = dist / f"{facts['name']}-{facts['version']}.tar.gz"
    sdist = sdist_path if sdist_path.is_file() else None
    sdists = [sdist] if sdist else []
    root_ref = f"pkg:pypi/{normalize(facts['name'])}@{facts['version']}"

    components: list[dict[str, Any]] = []
    for path in [wheel, *sdists]:
        components.append(
            {
                "type": "file",
                "bom-ref": f"file:{path.name}",
                "name": path.name,
                "hashes": [{"alg": "SHA-256", "content": _sha256(path)}],
            }
        )

    libraries: dict[str, dict[str, Any]] = {}
    for name, version in sorted(parse_pins(_vendor_text(sdist, vendor_txt)).items()):
        if name not in VENDORED:
            raise SbomError(
                f"vendor.txt pins {name}, which generate_sbom.VENDORED does not "
                "describe; add its license and module paths"
            )
        entry = VENDORED[name]
        if entry is None:
            continue
        license_id, modules = entry
        for module in modules:
            path = f"apothem/_vendor/{module}"
            if not any(n == path or n.startswith(path) for n in names):
                raise SbomError(
                    f"{wheel.name} does not ship {path} for vendored {name}"
                )
        libraries[name] = _library(
            name,
            version,
            licenses=[{"license": {"id": license_id}}],
            properties=[{"name": "apothem:vendored-under", "value": "apothem/_vendor"}],
        )

    for requirement in facts["requires"]:
        spec, _, marker = requirement.partition(";")
        if "extra" in marker:
            continue
        match = _REQUIREMENT.match(spec.strip())
        if match is None:
            raise SbomError(f"cannot parse Requires-Dist: {requirement}")
        name, constraint = normalize(match[1]), match[3].strip()
        if name in libraries:
            libraries[name].setdefault("properties", []).append(
                {"name": "apothem:also-required", "value": constraint}
            )
            continue
        exact = constraint[2:] if constraint.startswith("==") else None
        properties = (
            [] if exact else [{"name": "apothem:requirement", "value": constraint}]
        )
        libraries[name] = _library(
            name,
            exact,
            scope="required",
            **({"properties": properties} if properties else {}),
        )

    components.extend(libraries[name] for name in sorted(libraries))
    root: dict[str, Any] = {
        "type": "application",
        "bom-ref": root_ref,
        "name": facts["name"],
        "version": facts["version"],
        "purl": root_ref,
    }
    if facts["license"]:
        root["licenses"] = [{"expression": facts["license"]}]

    metadata: dict[str, Any] = {}
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        stamp = _dt.datetime.fromtimestamp(int(epoch), tz=_dt.timezone.utc)
        metadata["timestamp"] = stamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    metadata["tools"] = {
        "components": [
            {"type": "application", "name": "apothem scripts/release/generate_sbom.py"}
        ]
    }
    metadata["component"] = root

    digest = next(c["hashes"][0]["content"] for c in components if c["type"] == "file")
    return {
        "$schema": "http://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, root_ref + '#' + digest)}",
        "version": 1,
        "metadata": metadata,
        "components": components,
        "dependencies": [
            {
                "ref": root_ref,
                "dependsOn": [libraries[n]["bom-ref"] for n in sorted(libraries)],
            }
        ],
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dist",
        type=Path,
        required=True,
        help="Directory holding the wheel and sdist.",
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="Path of the SBOM to write."
    )
    parser.add_argument(
        "--vendor-txt", type=Path, help="vendor.txt to use instead of the sdist's."
    )
    args = parser.parse_args(argv)
    try:
        sbom = build_sbom(args.dist, args.vendor_txt)
    except (SbomError, OSError, zipfile.BadZipFile, tarfile.TarError) as exc:
        print(f"generate-sbom: {exc}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(sbom, handle, indent=2, sort_keys=False)
        handle.write("\n")
    libraries = sum(1 for c in sbom["components"] if c["type"] == "library")
    print(
        f"generate-sbom: {args.output} ({libraries} packages, root {sbom['metadata']['component']['purl']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
