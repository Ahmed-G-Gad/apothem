# SPDX-License-Identifier: MIT

"""Fuzz target: the JSONC / JSON5 reader, :func:`apothem.lib.lenient_json.loads`.

OpenCode's and OpenClaw's config files, which the operator writes by hand, go
through this parser before an install decides whether its merge would change a
value. Two invariants:

* any text either parses or raises :class:`LenientJSONError`; any other
  exception (``RecursionError``, ``IndexError``, ...) is a crash;
* the reader is a superset of JSON: text that :func:`json.loads` accepts parses
  to the same value (compared through :func:`json.dumps`, so ``1`` and ``1.0``,
  ``0.0`` and ``-0.0``, and ``NaN`` all stay distinct and comparable). The one
  allowed difference is the reader's nesting limit.

Run it with Atheris (see ``tests/fuzz/README.md``); ``fuzz_one_input`` also runs
without Atheris, which is how ``test_fuzz_corpus_replay.py`` replays the seeds.
"""

from __future__ import annotations

import json
import sys

from apothem.lib import lenient_json


def _same(left: object, right: object) -> bool:
    return json.dumps(left) == json.dumps(right)


def fuzz_one_input(data: bytes) -> None:
    """Check both invariants for one input."""
    text = data.decode("utf-8", "replace")
    try:
        value = lenient_json.loads(text)
        rejected: lenient_json.LenientJSONError | None = None
    except lenient_json.LenientJSONError as exc:
        value, rejected = None, exc
    try:
        strict = json.loads(text)
    except (ValueError, RecursionError):
        return
    if rejected is not None:
        if lenient_json.NESTING_TOO_DEEP in str(rejected):
            return
        raise AssertionError(f"rejects JSON that json.loads accepts: {rejected}")
    if not _same(value, strict):
        raise AssertionError(f"parses JSON differently: {value!r} != {strict!r}")


def main() -> None:
    """Run the target under Atheris."""
    import atheris

    atheris.instrument_all()
    atheris.Setup(sys.argv, fuzz_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
