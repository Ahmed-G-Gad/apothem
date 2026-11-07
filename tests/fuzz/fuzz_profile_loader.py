# SPDX-License-Identifier: MIT

"""Fuzz target: the shared-profile loader, :func:`load_profile_file`.

Every CLI command reads the operator's ``profile.yaml`` first, through the YAML
parser, the schema validator, the migrations and the normalization. The input
bytes are the file. Invariants:

* the load returns a :class:`CanonicalProfile` or raises
  :class:`ProfileValidationError`; any other exception escapes as a traceback
  and breaks the CLI's JSON envelope, so it is a crash;
* a loaded profile serializes and normalizes again to itself
  (``coerce_profile(profile.to_dict()) == profile``);
* the per-harness projection works for every supported harness id.

``tests/property/test_profile_loader_properties.py`` checks the first invariant
with Hypothesis; this target adds coverage-guided search.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from apothem.lib.profile import (
    SUPPORTED_HARNESS_IDS,
    CanonicalProfile,
    ProfileValidationError,
    coerce_profile,
    load_profile_file,
)

_PROFILE = Path(tempfile.mkdtemp(prefix="apothem-fuzz-profile-")) / "profile.yaml"


def fuzz_one_input(data: bytes) -> None:
    """Check the invariants for one input."""
    _PROFILE.write_bytes(data)
    try:
        profile = load_profile_file(_PROFILE)
    except ProfileValidationError:
        return
    if not isinstance(profile, CanonicalProfile):
        raise AssertionError(f"loaded a {type(profile).__name__}")
    if coerce_profile(profile.to_dict()) != profile:
        raise AssertionError("the profile does not normalize to itself")
    for harness_id in SUPPORTED_HARNESS_IDS:
        profile.for_harness(harness_id)


def main() -> None:
    """Run the target under Atheris."""
    import atheris

    atheris.instrument_all()
    atheris.Setup(sys.argv, fuzz_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
