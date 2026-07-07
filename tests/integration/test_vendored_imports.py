# SPDX-License-Identifier: MIT

"""Proof that the vendored ``yaml`` + ``jsonschema`` stack runs zero-deps.

The self-contained plugin runtime requires apothem's third-party runtime
dependencies to be importable WITHOUT a package-installation step. The
runtime vendors the pure-Python ``yaml`` package and the ``jsonschema`` core
chain (``jsonschema`` + ``attrs`` + ``referencing`` +
``jsonschema_specifications``) under ``src/apothem/_vendor/``, plus a
pure-Python ``rpds`` shim standing in for the un-vendorable Rust
``rpds-py`` extension that the chain depends on.

This test proves the vendored stack works in genuine isolation. It spawns
a fresh subprocess whose import surface is ONLY the ``_vendor`` directory
plus the standard library — ``python -S`` skips ``site`` so no
site-packages copy can satisfy any import, and ``PYTHONPATH`` is set to
the vendor directory alone. Inside that subprocess it parses YAML, runs a
real ``jsonschema`` validation of the in-repo profile example against the
profile schema (exercising the ``rpds`` shim end-to-end through
``referencing``'s registry), confirms a deliberately-invalid document
raises ``ValidationError``, and asserts that the only ``rpds`` module
loaded is the pure-Python shim — no compiled ``rpds``/``_rpds`` extension.

Scope note. The runtime vendors ``pyyaml`` and ``jsonschema`` only.
``click`` and ``rich`` remain host prerequisites, so this is NOT a full
clean-machine zero-deps proof — it proves the vendored *subset* is
self-contained.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_VENDOR_DIR = _REPO_ROOT / "src" / "apothem" / "_vendor"
_SCHEMA_JSON = _REPO_ROOT / "src" / "apothem" / "schemas" / "profile.schema.json"
_MANIFEST_YAML = _REPO_ROOT / "src" / "apothem" / "schemas" / "profile.example.yaml"

# Runs inside the isolated subprocess. Imports resolve ONLY from the
# vendor directory (PYTHONPATH) and the stdlib (python -S skips site), so
# a passing run proves the vendored copies — not any site-packages
# install — satisfy every import.
_PROBE = r"""
import json, sys
from pathlib import Path

schema_path = Path(sys.argv[1])
manifest_path = Path(sys.argv[2])

# (1) Vendored YAML parses a document.
import yaml
parsed = yaml.safe_load("name: apothem\nitems:\n  - a\n  - b\n")
assert parsed == {"name": "apothem", "items": ["a", "b"]}, parsed

# (2) Vendored jsonschema validates a real schema/manifest pair. Loading
#     the manifest with the vendored yaml and validating against the
#     2020-12 schema drives referencing's registry, which is backed by
#     the rpds shim — so a clean validation exercises the shim end-to-end.
import jsonschema
from jsonschema import Draft202012Validator

with schema_path.open(encoding="utf-8") as fh:
    schema = json.load(fh)
with manifest_path.open(encoding="utf-8") as fh:
    manifest = yaml.safe_load(fh)

Draft202012Validator.check_schema(schema)
validator = Draft202012Validator(schema)
validator.validate(manifest)  # raises if the real manifest is invalid

# (3) A deliberately-invalid document raises ValidationError. Dropping the
#     required top-level "identity" key violates the schema's required set.
invalid = dict(manifest)
invalid.pop("identity", None)
raised = False
try:
    validator.validate(invalid)
except jsonschema.ValidationError:
    raised = True
assert raised, "invalid profile did not raise ValidationError"

# (4) The rpds in play is the pure-Python shim, and no compiled
#     rpds/_rpds extension module was imported.
import rpds
rpds_file = rpds.__file__
loaded = sorted(m for m in sys.modules if m == "rpds" or m.startswith("rpds.") or m == "_rpds")

print(json.dumps({
    "yaml_file": yaml.__file__,
    "jsonschema_file": jsonschema.__file__,
    "rpds_file": rpds_file,
    "loaded_rpds_modules": loaded,
}))
"""


def test_vendored_stack_imports_and_validates_in_isolation() -> None:
    """Vendored yaml + jsonschema run zero-deps through the rpds shim.

    Arrange a subprocess whose only import surface is the vendor directory
    plus the stdlib. Act by running the probe that parses YAML, validates
    the profile example, and rejects an invalid document. Assert each
    import resolved to a vendored path and only the pure-Python rpds shim
    was loaded.
    """
    # Arrange: an environment with no site-packages on the path. -S skips
    # site initialization; PYTHONPATH is the vendor dir alone. We pass an
    # empty base env (only PYTHONPATH) so no inherited PYTHONPATH leaks a
    # site-packages copy in.
    env = {"PYTHONPATH": str(_VENDOR_DIR)}
    # Preserve the variables a Windows Python needs to start at all.
    import os

    for key in ("SYSTEMROOT", "PATH", "PATHEXT", "TEMP", "TMP", "WINDIR"):
        if key in os.environ:
            env[key] = os.environ[key]

    # Act: drive the probe in a fresh, isolated interpreter.
    result = subprocess.run(
        [sys.executable, "-S", "-c", _PROBE, str(_SCHEMA_JSON), str(_MANIFEST_YAML)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(_REPO_ROOT),
        check=False,
    )

    # Assert: the subprocess succeeded and every import came from _vendor.
    assert result.returncode == 0, (
        f"isolated probe failed (rc={result.returncode})\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    report = json.loads(result.stdout.strip().splitlines()[-1])

    vendor_str = str(_VENDOR_DIR)
    assert vendor_str in report["yaml_file"], report["yaml_file"]
    assert vendor_str in report["jsonschema_file"], report["jsonschema_file"]
    assert vendor_str in report["rpds_file"], report["rpds_file"]

    # The rpds shim is pure-Python: the only loaded rpds module is the
    # shim package itself; no compiled `_rpds`/`rpds.rpds` extension.
    assert report["loaded_rpds_modules"] == ["rpds"], report["loaded_rpds_modules"]
