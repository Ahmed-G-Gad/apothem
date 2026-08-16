# SPDX-License-Identifier: MIT

"""Structured pass/fail/warn reporting for validation tools."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Final, TextIO

_PASS: Final[str] = "[PASS]"
_FAIL: Final[str] = "[FAIL]"
_WARN: Final[str] = "[WARN]"
_INFO: Final[str] = "[INFO]"


@dataclass
class Reporter:
    """Accumulates validation outcomes with running counts."""

    stream: TextIO = field(default_factory=lambda: sys.stdout)
    passed: int = 0
    failed: int = 0
    warned: int = 0
    errors: list[str] = field(default_factory=list)

    def ok(self, message: str) -> None:
        """Write a ``[PASS]`` line and increment the passed count."""
        self.stream.write(f"{_PASS} {message}\n")
        self.passed += 1

    def fail(self, message: str) -> None:
        """Write a ``[FAIL]`` line, increment the failed count, and record
        the message in :attr:`errors`."""
        self.stream.write(f"{_FAIL} {message}\n")
        self.failed += 1
        self.errors.append(message)

    def warn(self, message: str) -> None:
        """Write a ``[WARN]`` line and increment the warned count."""
        self.stream.write(f"{_WARN} {message}\n")
        self.warned += 1

    def info(self, message: str) -> None:
        """Write an ``[INFO]`` line; carries no pass/fail/warn weight."""
        self.stream.write(f"{_INFO} {message}\n")

    def section(self, title: str) -> None:
        """Write a section header to group the subsequent lines."""
        self.stream.write(f"\n=== {title} ===\n")

    def summary(self) -> None:
        """Write the final summary block with the passed/failed/warned counts."""
        self.stream.write("\n=== Summary ===\n")
        self.stream.write(f"{_INFO} Passed: {self.passed}\n")
        self.stream.write(f"{_INFO} Failed: {self.failed}\n")
        self.stream.write(f"{_INFO} Warnings: {self.warned}\n")

    @property
    def exit_code(self) -> int:
        """Process exit code: ``0`` when no check failed, else ``1``."""
        return 0 if self.failed == 0 else 1
