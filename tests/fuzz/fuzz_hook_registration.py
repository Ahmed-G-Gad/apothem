# SPDX-License-Identifier: MIT

"""Fuzz target: merging Apothem's hooks into a hook file the operator may edit.

Kiro's and GitHub Copilot's ``apothem.json`` and Cursor's ``.cursor/hooks.json``
(which a team edits and commits) go through :func:`merge_registration` on
install and :func:`strip_registration` on uninstall. The first input byte picks
one of the three templates (byte modulo 3) and whether the file is
operator-owned (byte divided by 3 is odd); the rest is the file already on disk.
Invariants:

* the merge returns text holding a JSON object, or, for an operator-owned file
  only, refuses with ``_UnmergeableError``; the strip returns text or ``None``
  (delete the file). Any other exception is a crash;
* a second install changes nothing: merging into the merged file returns it
  byte for byte;
* the merge keeps the operator's hook entries, in order, whenever the file
  already held hooks of the template's shape;
* an uninstall after the install leaves no Apothem hook behind.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import apothem.harnesses

# The install driver first: imported on its own, install_driver_hookfile reaches
# it through a circular import that fails part-way.
from apothem.harnesses._shared import install_driver  # noqa: F401
from apothem.harnesses._shared.install_driver_hookfile import (
    _UnmergeableError,
    _without_ours,
    merge_registration,
    strip_registration,
)

_HARNESSES = Path(apothem.harnesses.__file__).resolve().parent
_TOKENS = {
    "${PYTHON_BIN}": "/usr/bin/python3",
    "${PROJECT_ROOT}": "/work/project",
    "${CALL_OP}": "",
}


def _rendered(harness: str) -> str:
    path = _HARNESSES / harness / "templates" / "apothem-hooks.json"
    text = path.read_text(encoding="utf-8")
    for token, value in _TOKENS.items():
        text = text.replace(token, value)
    return text


#: The rendered templates, read once: Kiro's list shape, then the event-map
#: shape of GitHub Copilot and Cursor.
_RENDERED = tuple(_rendered(name) for name in ("kiro", "github_copilot", "cursor"))


def _operator_entries(document: object) -> str | None:
    """Return the operator's hook entries in *document*, in file order, as JSON.

    ``None`` when *document* is not a hook registration. An event-map value
    that is not a list holds no entry.
    """
    kept = _without_ours(document)
    if kept is None:
        return None
    hooks = kept[0]["hooks"]
    if isinstance(hooks, list):
        return json.dumps(hooks)
    assert isinstance(hooks, dict)
    return json.dumps(
        [
            [event, hook]
            for event, listed in hooks.items()
            if isinstance(listed, list)
            for hook in listed
        ]
    )


def _parsed(text: str) -> object:
    try:
        return json.loads(text)
    except (ValueError, RecursionError):
        return None


def fuzz_one_input(data: bytes) -> None:
    """Check the invariants for one input."""
    if not data:
        return
    # ASCII 0-2 pick a template for an Apothem-owned file, 3-5 the same three
    # for an operator-owned one.
    rendered = _RENDERED[data[0] % len(_RENDERED)]
    operator_owned = (data[0] // len(_RENDERED)) % 2 == 1
    existing = data[1:].decode("utf-8", "replace")

    stripped = strip_registration(existing)
    if stripped is not None and not isinstance(stripped, str):
        raise AssertionError(f"strip returned {type(stripped).__name__}")

    try:
        merged = merge_registration(existing, rendered, operator_owned=operator_owned)
    except _UnmergeableError:
        if not operator_owned:
            raise
        return
    document = json.loads(merged)
    if not isinstance(document, dict):
        raise AssertionError("the merged file is not a JSON object")

    again = merge_registration(merged, rendered, operator_owned=operator_owned)
    if again != merged:
        raise AssertionError(f"a second install changes the file:\n{merged}\n{again}")

    before = _parsed(existing)
    template_hooks = json.loads(rendered)["hooks"]
    if isinstance(before, dict) and (
        type(before.get("hooks")) is type(template_hooks)
        or (operator_owned and "hooks" not in before)
    ):
        if "hooks" not in before:
            before = {**before, "hooks": type(template_hooks)()}
        if _operator_entries(document) != _operator_entries(before):
            raise AssertionError("the merge lost or reordered an operator hook")

    after_uninstall = strip_registration(merged)
    if after_uninstall is not None:
        left = json.loads(after_uninstall)
        kept = _without_ours(left)
        if kept is not None and kept[0] != left:
            raise AssertionError("an uninstall leaves an Apothem hook behind")


def main() -> None:
    """Run the target under Atheris."""
    import atheris

    atheris.instrument_all()
    atheris.Setup(sys.argv, fuzz_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
