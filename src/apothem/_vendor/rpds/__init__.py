# SPDX-License-Identifier: MIT

"""Pure-Python ``rpds`` shim for the self-contained plugin runtime.

Why this module exists. ``jsonschema`` and its dependency ``referencing``
import three persistent-data-structure types from ``rpds`` —
``HashTrieMap``, ``HashTrieSet``, and ``List``. The upstream ``rpds-py``
distribution implements these in Rust (PyO3) and ships a compiled
``.pyd``/``.so`` extension, which cannot be vendored as portable
pure-Python source. This module reimplements exactly the API subset that
``jsonschema``/``referencing`` exercise, backed by builtin ``dict`` /
``frozenset`` / ``tuple``, so the vendored validation stack imports and
runs with zero compiled extensions and no package installation.

Persistence contract. The upstream types are *persistent* (immutable):
mutating methods (``insert``, ``remove``, ``discard``, ``update``,
``push_front``) return a NEW instance and leave the receiver unchanged.
This shim honors that contract — every instance is frozen at construction
and every "mutation" builds a fresh object. This matters because the
consumers store these structures as ``attrs`` frozen-class field defaults
and rely on the receiver never changing under them.

Surface fidelity. The implemented surface is verified against the actual
call sites in the installed ``jsonschema`` and ``referencing``
distributions (see the module docstring's method-by-method provenance in
the vendoring report). Methods present in the upstream ``rpds`` ``.pyi``
stub but unused by ``jsonschema``/``referencing`` (``Queue``,
``fromkeys``, ``Map.keys/values`` views beyond iteration) are implemented
where cheap and faithful, or omitted where they would add unverified
surface. ``HashTrieMap`` subclasses ``Mapping`` and ``HashTrieSet``
subclasses ``frozenset`` to match the upstream type hierarchy the
consumers' type hints assume.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from typing import Any, TypeVar

# ``Any`` is used only in the variadic ``update``/``convert`` signatures
# below, where the merged result genuinely loses static key/value typing
# (mirroring upstream ``rpds``'s generic-widening ``update``).

__all__ = ["HashTrieMap", "HashTrieSet", "List"]

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")
_T = TypeVar("_T")


class HashTrieMap(Mapping[_KT, _VT]):
    """Persistent (immutable) mapping backed by a builtin ``dict``.

    Construction accepts a mapping, an iterable of ``(key, value)`` pairs,
    or keyword arguments — mirroring ``dict``. Every mutating method
    returns a new ``HashTrieMap``; the receiver is never modified.
    """

    __slots__ = ("_data", "_hash")

    _data: dict[_KT, _VT]
    _hash: int | None

    def __init__(
        self,
        value: Mapping[_KT, _VT] | Iterable[tuple[_KT, _VT]] = (),
        **kwds: _VT,
    ) -> None:
        # dict() handles mapping, pair-iterable, and kwargs uniformly,
        # matching the upstream constructor's accepted shapes.
        data: dict[_KT, _VT] = dict(value, **kwds)
        # object.__setattr__ because instances are logically frozen and
        # __slots__ + immutability discourage post-construction writes.
        object.__setattr__(self, "_data", data)
        object.__setattr__(self, "_hash", None)

    def __getitem__(self, key: _KT) -> _VT:
        return self._data[key]

    def __iter__(self) -> Iterator[_KT]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: object) -> bool:
        return key in self._data

    # ``.get()`` is provided by the ``Mapping`` mixin (backed by the
    # ``__getitem__``/``__contains__`` defined here), matching the
    # upstream ``HashTrieMap``'s mapping-protocol ``get``.

    def insert(self, key: _KT, val: _VT) -> HashTrieMap[_KT, _VT]:
        """Return a new map with ``key`` set to ``val``."""
        new_data = dict(self._data)
        new_data[key] = val
        return HashTrieMap(new_data)

    def remove(self, key: _KT) -> HashTrieMap[_KT, _VT]:
        """Return a new map without ``key``; raise ``KeyError`` if absent."""
        if key not in self._data:
            raise KeyError(key)
        new_data = dict(self._data)
        del new_data[key]
        return HashTrieMap(new_data)

    def discard(self, key: _KT) -> HashTrieMap[_KT, _VT]:
        """Return a new map without ``key``; a no-op copy if absent."""
        if key not in self._data:
            return HashTrieMap(self._data)
        new_data = dict(self._data)
        del new_data[key]
        return HashTrieMap(new_data)

    def update(
        self,
        *args: Mapping[Any, Any] | Iterable[tuple[Any, Any]],
    ) -> HashTrieMap[Any, Any]:
        """Return a new map merged with each mapping/pair-iterable arg."""
        new_data = dict(self._data)
        for arg in args:
            new_data.update(arg)
        return HashTrieMap(new_data)

    @classmethod
    def convert(
        cls,
        value: Mapping[_KT, _VT] | Iterable[tuple[_KT, _VT]],
    ) -> HashTrieMap[_KT, _VT]:
        """Coerce ``value`` to a ``HashTrieMap`` (idempotent on instances)."""
        if isinstance(value, HashTrieMap):
            return value
        return cls(value)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, HashTrieMap):
            return self._data == other._data
        if isinstance(other, Mapping):
            return dict(self._data) == dict(other)
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __hash__(self) -> int:
        cached = self._hash
        if cached is None:
            cached = hash(frozenset(self._data.items()))
            object.__setattr__(self, "_hash", cached)
        return cached

    def __repr__(self) -> str:
        return f"HashTrieMap({self._data!r})"


class HashTrieSet(frozenset):  # type: ignore[type-arg]
    """Persistent (immutable) set; subclasses ``frozenset``.

    Subclassing ``frozenset`` gives membership, iteration, length,
    truthiness, hashing, and equality for free. The mutating methods are
    overridden to return new ``HashTrieSet`` instances per the persistence
    contract.
    """

    __slots__ = ()

    def __new__(cls, value: Iterable[_T] = ()) -> HashTrieSet:
        return super().__new__(cls, value)

    def insert(self, value: _T) -> HashTrieSet:
        """Return a new set with ``value`` added."""
        return HashTrieSet(super().union({value}))

    def remove(self, value: _T) -> HashTrieSet:  # type: ignore[override]
        """Return a new set without ``value``; raise ``KeyError`` if absent."""
        if value not in self:
            raise KeyError(value)
        return HashTrieSet(super().difference({value}))

    def discard(self, value: _T) -> HashTrieSet:  # type: ignore[override]
        """Return a new set without ``value``; a no-op copy if absent."""
        return HashTrieSet(super().difference({value}))

    def update(self, *args: Iterable[_T]) -> HashTrieSet:  # type: ignore[override]
        """Return a new set unioned with every iterable arg."""
        result: frozenset = self
        for arg in args:
            result = result.union(arg)
        return HashTrieSet(result)

    def __repr__(self) -> str:
        return f"HashTrieSet({set(self)!r})"


class List(Iterable[_T]):
    """Persistent (immutable) singly-linked-style list backed by a tuple.

    Iteration yields front-to-back. ``push_front`` returns a new ``List``
    with the value prepended (the new front), matching the upstream
    dynamic-scope semantics in ``referencing`` where the most recently
    pushed URI is visited first.
    """

    __slots__ = ("_items",)

    _items: tuple[_T, ...]

    def __init__(self, value: Iterable[_T] = (), *more: _T) -> None:
        items: tuple[_T, ...] = tuple(value)
        if more:
            items = items + more
        object.__setattr__(self, "_items", items)

    def __iter__(self) -> Iterator[_T]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __bool__(self) -> bool:
        return bool(self._items)

    def push_front(self, value: _T) -> List[_T]:
        """Return a new list with ``value`` prepended as the new front."""
        return List((value, *self._items))

    def drop_first(self) -> List[_T]:
        """Return a new list without the front element."""
        if not self._items:
            raise IndexError("drop_first from empty List")
        return List(self._items[1:])

    def __eq__(self, other: object) -> bool:
        if isinstance(other, List):
            return self._items == other._items
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __hash__(self) -> int:
        return hash(self._items)

    def __repr__(self) -> str:
        return f"List({list(self._items)!r})"
