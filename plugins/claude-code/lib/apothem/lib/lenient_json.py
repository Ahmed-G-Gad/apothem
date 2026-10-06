# SPDX-License-Identifier: MIT

"""Read-only parser for JSONC and JSON5 operator configs (stdlib only).

Several harnesses read a ``.json`` config file in a superset of JSON: OpenCode
accepts JSONC (comments and trailing commas) and OpenClaw reads JSON5 (also
unquoted keys, single-quoted strings, hexadecimal numbers, ``Infinity`` /
``NaN``, and leading or trailing decimal points). Apothem never *writes* those
dialects, because a strict-JSON re-dump would silently drop the operator's
comments. It only needs to *read* them, so the install can tell whether its
merge would change any value:

* no value would change: the operator's bytes are left exactly as they are;
* a value would change: the write is refused instead of losing the comments.

:func:`loads` returns plain Python values (``dict`` / ``list`` / ``str`` /
``int`` / ``float`` / ``bool`` / ``None``), the same shapes :func:`json.loads`
produces, so a parsed operator file compares directly against a parsed
strict-JSON template. A later duplicate key wins, as in :mod:`json`.
"""

from __future__ import annotations

from typing import Final

__all__ = ["LenientJSONError", "loads"]

# JSON5 line terminators: LF, CR, LINE SEPARATOR, PARAGRAPH SEPARATOR.
# Spelled with chr() so no invisible code point sits in the source.
_LINE_BREAKS: Final[frozenset[str]] = frozenset({"\n", "\r", chr(0x2028), chr(0x2029)})
# JSON5 white space: the line terminators plus space, tab, vertical tab,
# form feed, NO-BREAK SPACE and the BYTE ORDER MARK.
_WHITESPACE: Final[frozenset[str]] = _LINE_BREAKS | frozenset(
    {" ", "\t", "\v", "\f", chr(0x00A0), chr(0xFEFF)}
)
_SIMPLE_ESCAPES: Final[dict[str, str]] = {
    '"': '"',
    "'": "'",
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "v": "\v",
    "0": "\0",
}
_LITERALS: Final[dict[str, object]] = {"true": True, "false": False, "null": None}


class LenientJSONError(ValueError):
    """The text is not valid JSON, JSONC, or JSON5."""

    def __init__(self, message: str, position: int) -> None:
        """Record *message* and the character *position* it refers to."""
        super().__init__(f"{message} (at character {position})")
        self.position = position


class _Parser:
    """A recursive-descent reader over one document."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def error(self, message: str) -> LenientJSONError:
        return LenientJSONError(message, self.pos)

    def peek(self) -> str:
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def skip_space(self) -> None:
        text = self.text
        while self.pos < len(text):
            char = text[self.pos]
            if char in _WHITESPACE:
                self.pos += 1
            elif text.startswith("//", self.pos):
                while self.pos < len(text) and text[self.pos] not in _LINE_BREAKS:
                    self.pos += 1
            elif text.startswith("/*", self.pos):
                end = text.find("*/", self.pos + 2)
                if end == -1:
                    raise self.error("unterminated block comment")
                self.pos = end + 2
            else:
                return

    def document(self) -> object:
        self.skip_space()
        value = self.value()
        self.skip_space()
        if self.pos != len(self.text):
            raise self.error("unexpected trailing content")
        return value

    def value(self) -> object:
        char = self.peek()
        if char == "{":
            return self.obj()
        if char == "[":
            return self.array()
        if char in {'"', "'"}:
            return self.string()
        if char == "":
            raise self.error("unexpected end of input")
        if char in "+-.0123456789IN":
            return self.number()
        word = self.identifier()
        if word in _LITERALS:
            return _LITERALS[word]
        raise self.error(f"unexpected token {word!r}")

    def obj(self) -> dict[str, object]:
        self.pos += 1
        result: dict[str, object] = {}
        while True:
            self.skip_space()
            if self.peek() == "}":
                self.pos += 1
                return result
            key = self.string() if self.peek() in {'"', "'"} else self.identifier()
            self.skip_space()
            if self.peek() != ":":
                raise self.error("expected ':' after object key")
            self.pos += 1
            self.skip_space()
            result[key] = self.value()
            self.skip_space()
            char = self.peek()
            if char == ",":
                self.pos += 1
            elif char != "}":
                raise self.error("expected ',' or '}' in object")

    def array(self) -> list[object]:
        self.pos += 1
        result: list[object] = []
        while True:
            self.skip_space()
            if self.peek() == "]":
                self.pos += 1
                return result
            result.append(self.value())
            self.skip_space()
            char = self.peek()
            if char == ",":
                self.pos += 1
            elif char != "]":
                raise self.error("expected ',' or ']' in array")

    def identifier(self) -> str:
        start = self.pos
        text = self.text
        while self.pos < len(text) and (
            text[self.pos].isalnum() or text[self.pos] in "_$"
        ):
            self.pos += 1
        word = text[start : self.pos]
        if not word or word[0].isdigit():
            self.pos = start
            raise self.error("expected a value or an object key")
        return word

    def string(self) -> str:
        quote = self.text[self.pos]
        self.pos += 1
        parts: list[str] = []
        text = self.text
        while True:
            if self.pos >= len(text):
                raise self.error("unterminated string")
            char = text[self.pos]
            if char == quote:
                self.pos += 1
                return "".join(parts)
            if char in _LINE_BREAKS:
                raise self.error("unescaped line break in string")
            if char != "\\":
                parts.append(char)
                self.pos += 1
                continue
            self.pos += 1
            escape = self.peek()
            if escape == "":
                raise self.error("unterminated string")
            if escape in _LINE_BREAKS:
                # A backslash before a line break continues the string.
                self.pos += 2 if text.startswith("\r\n", self.pos) else 1
            elif escape in _SIMPLE_ESCAPES:
                parts.append(_SIMPLE_ESCAPES[escape])
                self.pos += 1
            elif escape in {"x", "u"}:
                width = 2 if escape == "x" else 4
                digits = text[self.pos + 1 : self.pos + 1 + width]
                if len(digits) != width or any(
                    d not in "0123456789abcdefABCDEF" for d in digits
                ):
                    raise self.error("invalid hexadecimal escape")
                code = int(digits, 16)
                self.pos += 1 + width
                low = text[self.pos + 2 : self.pos + 6]
                if (
                    0xD800 <= code <= 0xDBFF
                    and text.startswith("\\u", self.pos)
                    and len(low) == 4
                    and all(d in "0123456789abcdefABCDEF" for d in low)
                    and 0xDC00 <= int(low, 16) <= 0xDFFF
                ):
                    # A UTF-16 surrogate pair, as json.dumps writes non-BMP
                    # characters: combine it into one code point.
                    code = 0x10000 + ((code - 0xD800) << 10) + (int(low, 16) - 0xDC00)
                    self.pos += 6
                parts.append(chr(code))
            else:
                parts.append(escape)
                self.pos += 1

    def number(self) -> int | float:
        text = self.text
        sign = 1
        if self.peek() in "+-":
            sign = -1 if self.peek() == "-" else 1
            self.pos += 1
        if text.startswith("Infinity", self.pos):
            self.pos += len("Infinity")
            return sign * float("inf")
        if text.startswith("NaN", self.pos):
            self.pos += len("NaN")
            return float("nan")
        if text.startswith(("0x", "0X"), self.pos):
            start = self.pos + 2
            self.pos = start
            while self.pos < len(text) and text[self.pos] in "0123456789abcdefABCDEF":
                self.pos += 1
            if self.pos == start:
                raise self.error("invalid hexadecimal number")
            return sign * int(text[start : self.pos], 16)
        start = self.pos
        while self.pos < len(text) and text[self.pos] in "0123456789.eE+-":
            if text[self.pos] in "+-" and text[self.pos - 1] not in "eE":
                break
            self.pos += 1
        literal = text[start : self.pos]
        if not literal or literal == ".":
            raise self.error("invalid number")
        try:
            if any(mark in literal for mark in ".eE"):
                return sign * float(literal)
            return sign * int(literal, 10)
        except ValueError as exc:
            raise self.error(f"invalid number {literal!r}") from exc


def loads(text: str) -> object:
    """Parse *text* as JSON, JSONC, or JSON5 and return the Python value.

    Raises:
        LenientJSONError: When *text* is not valid in any of the three dialects.
    """
    return _Parser(text).document()
