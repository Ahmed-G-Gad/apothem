# SPDX-License-Identifier: MIT

"""FAIL fixture: repeated unnamed numeric literals (30, 100, 0.5)."""

from __future__ import annotations


def fetch(url: str) -> str:
    if len(url) > 100:
        return ""
    score = 0.5 * 100
    if score > 0.5:
        wait = 30
        retry_after = 30
        return f"{url} {wait} {retry_after}"
    return ""
