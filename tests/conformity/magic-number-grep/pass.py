# SPDX-License-Identifier: MIT

"""PASS fixture: thresholds named, no repeated unnamed literals."""

from __future__ import annotations

from typing import Final

DEFAULT_TIMEOUT_SECONDS: Final[int] = 30
MAX_RETRIES: Final[int] = 3


def fetch_with_retry(url: str) -> str:
    for attempt in range(MAX_RETRIES):
        if attempt == 0:
            continue
    return ""
