# SPDX-License-Identifier: MIT

"""Module entry point: ``python -m apothem``.

``python -m apothem`` is the canonical invocation surface — apothem ships
no ``[project.scripts]`` console-script shim. The npm shim
(``npx @ahmed-g-gad/apothem``), the Claude Code plugin, and the one-shot
installers all run this same module surface; the installers additionally
place a thin ``apothem`` shell shim on ``PATH`` that forwards here.

Two start-up duties run here, before the CLI is imported, using the standard
library only:

- The vendored dependency directory (``apothem/_vendor``) is put at the front
  of ``sys.path``, the same vendor-first order the npm shim, the installers,
  and the plugin bootstrap use. ``PYTHONPATH=src python -m apothem`` from a
  checkout therefore needs nothing from the host except the two packages
  below.
- ``click`` and ``rich`` are the two dependencies the engine does not vendor.
  When either is missing, the entry point prints a structured error naming the
  exact ``pip`` command for the running interpreter (a JSON envelope under
  ``--json`` / ``--format json``) instead of a ``ModuleNotFoundError``
  traceback.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

#: Packages the engine imports from the host interpreter, paired with the pip
#: requirement spec from ``[project.dependencies]`` in ``pyproject.toml`` (a
#: test pins the two in lockstep). Every other runtime dependency is vendored.
HOST_PREREQUISITES: tuple[tuple[str, str], ...] = (
    ("click", "click==8.4.2"),
    ("rich", "rich>=15.0.0"),
)

#: Stable error code for a missing host prerequisite.
DEPENDENCY_MISSING_CODE = "runtime.dependency_missing"

_VENDOR_DIR = Path(__file__).resolve().parent / "_vendor"

_EXIT_EXPECTED = 1

#: The CLI JSON contract version (``apothem.cli._json_formatter``), repeated
#: here because this module must not import the CLI package; a test keeps the
#: two equal.
JSON_SCHEMA_VERSION = 1


def prepend_vendor_dir() -> None:
    """Move the vendored dependency directory to ``sys.path[0]`` (idempotent)."""
    if not _VENDOR_DIR.is_dir():
        return
    entry = str(_VENDOR_DIR)
    while entry in sys.path:
        sys.path.remove(entry)
    sys.path.insert(0, entry)


def missing_prerequisites() -> list[tuple[str, str]]:
    """Return the ``(module, pip spec)`` pairs that are not importable."""
    return [
        (module, spec)
        for module, spec in HOST_PREREQUISITES
        if importlib.util.find_spec(module) is None
    ]


def _json_requested(argv: list[str]) -> bool:
    """Return True when *argv* asks for JSON output (``--json`` or ``--format json``)."""
    for index, arg in enumerate(argv):
        if arg in {"--json", "--format=json"}:
            return True
        following = argv[index + 1] if index + 1 < len(argv) else ""
        if arg == "--format" and following.lower() == "json":
            return True
    return False


def _quoted(path: str) -> str:
    """Quote an interpreter path that contains whitespace."""
    return f'"{path}"' if any(char.isspace() for char in path) else path


def dependency_error(missing: list[tuple[str, str]]) -> dict[str, object]:
    """Build the structured error object for missing host prerequisites."""
    names = " and ".join(module for module, _ in missing)
    specs = " ".join(f'"{spec}"' for _, spec in missing)
    interpreter = sys.executable or "python3"
    return {
        "code": DEPENDENCY_MISSING_CODE,
        "message": "Apothem cannot start: required Python packages are missing.",
        "field": "runtime",
        "reason": (
            f"{names} {'is' if len(missing) == 1 else 'are'} not importable under "
            f"{interpreter}. Apothem vendors its other dependencies but not "
            "these, so the interpreter must provide them."
        ),
        "fix": (
            f"{_quoted(interpreter)} -m pip install {specs} (on an externally "
            "managed Python, install them in a virtual environment and point "
            "APOTHEM_PYTHON at its interpreter, or use your distribution's "
            "packages)."
        ),
        "safe_value": None,
        "files_written": [],
    }


def report_missing_prerequisites(
    missing: list[tuple[str, str]], argv: list[str]
) -> int:
    """Print the missing-prerequisite error in the requested format; return the exit code."""
    error = dependency_error(missing)
    if _json_requested(argv):
        envelope = {
            "schema_version": JSON_SCHEMA_VERSION,
            "status": "error",
            "command": None,
            "harness": None,
            "profile_path": None,
            "project": None,
            "files_written": [],
            "results": [],
            "warnings": [],
            "error": error,
        }
        sys.stdout.write(json.dumps(envelope) + "\n")
        return _EXIT_EXPECTED
    sys.stderr.write(
        f"Error: {error['message']}\n"
        f"Field: {error['field']}\n"
        f"Reason: {error['reason']}\n"
        f"Fix: {error['fix']}\n"
        "Files written: none.\n"
    )
    return _EXIT_EXPECTED


def run() -> int:
    """Run the CLI after the stdlib-only start-up checks; return the exit code."""
    prepend_vendor_dir()
    missing = missing_prerequisites()
    if missing:
        return report_missing_prerequisites(missing, sys.argv[1:])

    from apothem.cli import configure_stdio, main

    # Force UTF-8 stdio (Windows) before Click parses anything. Click emits
    # ``--help`` / ``--version`` from eager-option handling, and usage errors
    # from argument parsing, *before* the group callback body runs — so a
    # reconfigure inside that callback (apothem/cli/__init__.py) never reaches
    # those surfaces. Doing it here, at the invocation entry and never at
    # import, makes every Click surface inherit UTF-8 on a legacy-codepage host
    # when stdout is a pipe or redirect. The group-callback call remains as
    # defense-in-depth for a direct ``apothem.cli.main`` import that bypasses
    # this entry.
    configure_stdio()
    # Pin the completion trigger. Click derives the completion env var from
    # the detected program name, which under ``python -m apothem`` is
    # "python -m apothem" — an unmatchable variable name — so the emitted
    # completion scripts (which all set ``_APOTHEM_COMPLETE``) would never
    # engage. Pinning complete_var keeps shell completion working on every
    # invocation surface without altering usage strings.
    result = main(complete_var="_APOTHEM_COMPLETE")
    return int(result) if isinstance(result, int) else 0


if __name__ == "__main__":
    raise SystemExit(run())
