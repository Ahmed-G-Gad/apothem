# SPDX-License-Identifier: MIT

"""Fuzz target: the install-ledger reader, :func:`install_ledger.read_records`.

The ledger is the JSON-lines file an uninstall and a rollback trust to know
what an install wrote. It lives in the operator's state folder, so a crash, a
full disk or a hand edit can leave it torn or damaged. The input bytes are the
ledger. Invariants:

* the read returns the records or raises :class:`LedgerError`; any other
  exception is a crash (the uninstall cannot report what is wrong);
* every record read back serializes to a line that reads back to the same line,
  so a record the ledger keeps survives a compaction unchanged.
"""

from __future__ import annotations

import atexit
import json
import shutil
import sys
import tempfile
from pathlib import Path

from apothem.lib import install_ledger

_HARNESS = "fuzz"
_STATE_ROOT = Path(tempfile.mkdtemp(prefix="apothem-fuzz-ledger-"))
atexit.register(shutil.rmtree, _STATE_ROOT, ignore_errors=True)
_LEDGER = install_ledger.ledger_path(_HARNESS, state_root=_STATE_ROOT)
_LEDGER.parent.mkdir(parents=True, exist_ok=True)


def fuzz_one_input(data: bytes) -> None:
    """Check the invariants for one input."""
    _LEDGER.write_bytes(data)
    try:
        records = install_ledger.read_records(_HARNESS, state_root=_STATE_ROOT)
    except install_ledger.LedgerError:
        return
    for record in records:
        line = record.to_json_line()
        again = install_ledger.LedgerRecord.from_dict(json.loads(line))
        if again.to_json_line() != line:
            raise AssertionError(f"a record does not round-trip: {line}")


def main() -> None:
    """Run the target under Atheris."""
    import atheris

    atheris.instrument_all()
    atheris.Setup(sys.argv, fuzz_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
