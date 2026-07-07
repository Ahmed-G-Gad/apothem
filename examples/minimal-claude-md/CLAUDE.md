<!-- SPDX-License-Identifier: MIT -->

# Project Configuration

> Minimal `CLAUDE.md` example. This file demonstrates the smallest viable configuration that Claude Code reads on session start.

## Project context

This is the `minimal-claude-md` example. Claude Code automatically loads this file when started from any directory at or below the location of this file.

## Conventions

- All Python code targets Python 3.10+.
- Tests live in `tests/` and are discovered by `pytest`.
- Commits follow Conventional Commits (`type(scope): subject`).

## Useful commands

- `pytest tests/` — run the test suite.
- `python -m mypy .` — run type checks.

## What lives where

- `src/` — application code.
- `tests/` — test suite.
- `docs/` — user-facing documentation.
