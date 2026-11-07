# SPDX-License-Identifier: MIT

"""Fuzz target: the frontmatter probe, :mod:`apothem.lib.frontmatter`.

The conformity validators and the rule emitters for Kiro and Cursor read every
Markdown file's frontmatter through this module, including files an operator or
a contributor wrote. The input bytes are the file. Invariants:

* nothing raises;
* :func:`split_frontmatter` loses nothing: ``block + rest == text``, and the
  block opens with ``---``;
* a field value found by :func:`field_value_in_text` is text from the file.

The probe is regular-expression based, so the fuzzer also guards against a
pattern whose matching time grows out of proportion with its input: libFuzzer
reports an input that runs past its time limit.
"""

from __future__ import annotations

import sys

from apothem.lib import frontmatter

#: Field names the validators look up, plus one the input can also spell.
_FIELDS = ("name", "description", "applyTo", "globs", "paths", "updated")


def fuzz_one_input(data: bytes) -> None:
    """Check the invariants for one input."""
    text = data.decode("utf-8", "replace")
    split = frontmatter.split_frontmatter(text)
    if split is not None:
        block, rest = split
        if block + rest != text or not block.startswith("---"):
            raise AssertionError("split_frontmatter loses or moves text")
    for field in _FIELDS:
        value = frontmatter.field_value_in_text(text, field)
        if value is not None and value not in text:
            raise AssertionError(f"{field}: {value!r} is not text from the file")


def main() -> None:
    """Run the target under Atheris."""
    import atheris

    atheris.instrument_all()
    atheris.Setup(sys.argv, fuzz_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
