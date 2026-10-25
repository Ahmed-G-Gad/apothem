# SPDX-License-Identifier: MIT

"""The lock that spans a user-level write and its ledger record.

Holders of a user-level folder are read from the install ledger, so the write
and the record must not be separated by another install's removal. One lock
under the ledger state root spans both, for every user-level install,
uninstall and rollback. This is a leaf module: it also tells the other
user-level helpers which harnesses write a user-level folder at all.
"""

from __future__ import annotations

import contextlib
import functools
import inspect
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any, Final, TypeVar

from apothem.lib import atomic_io, install_ledger
from apothem.lib.propagation import HarnessRules

_USER_LEVEL_LOCK: Final[str] = "user-level.lock"

#: Seconds a user-level install, uninstall or rollback waits for the lock. The
#: holder writes the whole skills cohort, so this is longer than the default.
_LOCK_TIMEOUT: Final[float] = 120.0


def rules_for(harness_name: str) -> HarnessRules | None:
    """Return *harness_name*'s rules through the driver, or ``None`` when it has none."""
    from apothem.harnesses._shared import install_driver

    try:
        return install_driver.load_rules(harness_name)
    except RuntimeError:
        return None


def writes_user_level(harness_name: str) -> bool:
    """Return True when *harness_name*'s manifest has a user-level install entry."""
    rules = rules_for(harness_name)
    return rules is not None and any(entry.user_level for entry in rules.install)


def shared_scope(harness_name: str) -> AbstractContextManager[None]:
    """Return the lock to hold across a user-level write and its ledger record.

    Holders are read from the ledger, so a last-holder uninstall that runs
    between an install's first write and its ledger record would delete files
    the install has not yet recorded. One lock under the ledger state root spans
    both, for every user-level install, uninstall and rollback. Take it as the
    outermost lock, before the per-(harness, root) install lock. It is not
    re-entrant: do not take it again inside. A harness with no user-level entry
    gets a no-op scope.
    """
    if not writes_user_level(harness_name):
        return contextlib.nullcontext()
    return atomic_io.advisory_lock(
        install_ledger.STATE_ROOT / _USER_LEVEL_LOCK, timeout=_LOCK_TIMEOUT
    )


_F = TypeVar("_F", bound=Callable[..., Any])


def locked_for_harness(func: _F) -> _F:
    """Run *func* inside :func:`shared_scope` of its ``harness_name`` argument."""
    signature = inspect.signature(func)

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401  # Any: forwards the wrapped call unchanged
        bound = signature.bind(*args, **kwargs)
        with shared_scope(bound.arguments["harness_name"]):
            return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


__all__ = ["locked_for_harness", "rules_for", "shared_scope", "writes_user_level"]
