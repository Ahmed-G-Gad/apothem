# SPDX-License-Identifier: MIT

"""The header-exceptions glob must exempt the real ``_vendor/`` tree (PK-2).

The exception list used ``**/vendor/**``, which never matches the
leading-underscore ``src/apothem/_vendor/`` tree, so the header machinery did
not recognise apothem's vendored upstream tree as exempt. The fix adds
``**/_vendor/**``. This test pins the match so the glob cannot silently regress.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_INJECTOR = _REPO_ROOT / "scripts" / "inject-header.py"
_EXCEPTIONS = _REPO_ROOT / "src" / "apothem" / "schemas" / "header-exceptions.txt"


def _load_injector():
    """Import the hyphenated injector script as a module via its file path."""
    spec = importlib.util.spec_from_file_location("apothem_inject_header", _INJECTOR)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec so the script's dataclasses resolve __module__.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_vendor_tree_is_exempt_from_header_machinery() -> None:
    injector = _load_injector()
    globs = injector.load_exception_globs(_EXCEPTIONS)

    # The real vendored tree (leading underscore) is exempt — this fails if the
    # glob regresses to the original ``**/vendor/**`` (which never matches it).
    assert injector.matches_exception("src/apothem/_vendor/attr/_make.py", globs)
    assert injector.matches_exception("src/apothem/_vendor/attrs/converters.py", globs)

    # A first-party source path is NOT exempt.
    assert injector.matches_exception("src/apothem/lib/profile.py", globs) is None
