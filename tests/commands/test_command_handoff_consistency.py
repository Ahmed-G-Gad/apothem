# SPDX-License-Identifier: MIT

"""Regression coverage for command-handoff drift.

Slash commands are markdown specifications interpreted by the runtime;
they have no Python entry point, so these tests verify the contract
surface rather than an end-to-end invocation. The contract is the
operating-loop wiring that connects the ``/plan`` planning pipeline to
the eleven-command audit-fortress sequence:

* every audit-fortress command declares an ``Upstream``/``Downstream``
  pair that, taken together, reconstructs exactly one canonical linear
  chain entered at ``/code-review`` and terminal at ``/threat-model-audit``;
* the canonical arrow-joined sequence string appears verbatim in every
  audit-fortress command file (a single drift in one file fails here);
* each ``/plan`` stage's terminal handoff recommends the correct
  successor command, including the conditional architecture-bearing
  route through ``/plan-design``;
* ``/plan-audit`` is documented as the orthogonal pre-execute closure,
  never modelled as the fortress chain's downstream.

These assertions are the regression guard for the operating loop: any
edit that reorders the chain, drops ``/code-review`` as the entry, or
mis-wires a planning handoff breaks one of them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = PROJECT_ROOT / "src" / "apothem" / "commands"
# The seven planning stages are first-class top-level commands (plan-<stage>.md),
# each independently invocable — the /plan decomposition.

# The canonical audit-fortress linear sequence, entry to terminal.
FORTRESS_CHAIN: tuple[str, ...] = (
    "code-review",
    "code-audit",
    "security-audit",
    "perf-audit",
    "architecture-review",
    "ux-review",
    "a11y-audit",
    "docs-review",
    "dependency-audit",
    "supply-chain-audit",
    "threat-model-audit",
)

# The verbatim arrow-joined sequence string every fortress file embeds.
CANONICAL_SEQUENCE_STRING = " → ".join(f"/{name}" for name in FORTRESS_CHAIN)

# The canonical research-pipeline linear sequence, entry to terminal. Research
# stages wire their chain through a prose ``## Sequence Gate`` carrying a
# ``Blocked: run /research-<predecessor> first`` line and embed the verbatim
# arrow-joined sequence string in their ``Pipeline position`` line — unlike the
# fortress stages, which use bold Upstream/Downstream tokens.
RESEARCH_CHAIN: tuple[str, ...] = (
    "research-ideate",
    "research-spec",
    "research-theory",
    "research-sources",
    "research-synthesis",
    "research-proposal",
    "research-design",
    "research-experiment",
    "research-analysis",
    "research-paper",
    "research-review",
    "research-publish",
    "research-disseminate",
)

# The verbatim arrow-joined sequence string every research stage file embeds.
CANONICAL_RESEARCH_SEQUENCE_STRING = " → ".join(f"/{name}" for name in RESEARCH_CHAIN)


def _read(command: str) -> str:
    path = COMMANDS_DIR / f"{command}.md"
    assert path.is_file(), f"command file missing at {path}"
    return path.read_text(encoding="utf-8")


def _segment(text: str, marker: str) -> str:
    """Text following a bold ``marker`` up to the next bold marker or EOL."""
    start = text.index(marker) + len(marker)
    tail = text[start:]
    nxt = re.search(r"\*\*[A-Z]", tail)
    end = nxt.start() if nxt else tail.find("\n")
    return tail[:end] if end != -1 else tail


def _first_token(segment: str) -> str:
    """Return ``none`` or the first ``/command`` token in a segment."""
    none_at = re.search(r"\bnone\b", segment)
    cmd = re.search(r"`/([a-z0-9-]+)`", segment)
    if none_at and (cmd is None or none_at.start() < cmd.start()):
        return "none"
    if cmd:
        return cmd.group(1)
    raise AssertionError(f"no upstream/downstream token in segment: {segment!r}")


def _next_step_block(text: str) -> str:
    """The ``## Recommended Next Step`` or ``## Next Steps`` block body."""
    m = re.search(r"^##\s+(?:Recommended Next Step|Next Steps)\s*$", text, re.M)
    assert m, "command file carries no terminal next-step heading"
    tail = text[m.end() :]
    nxt = re.search(r"^##\s", tail, re.M)
    return tail[: nxt.start()] if nxt else tail


@pytest.mark.parametrize("command", FORTRESS_CHAIN)
def test_fortress_command_embeds_canonical_sequence(command: str) -> None:
    """Every fortress file carries the verbatim arrow-joined sequence."""
    assert CANONICAL_SEQUENCE_STRING in _read(command), (
        f"{command}.md does not embed the canonical sequence string "
        f"{CANONICAL_SEQUENCE_STRING!r} — sequence drift"
    )


@pytest.mark.parametrize("command", RESEARCH_CHAIN)
def test_research_command_embeds_canonical_sequence(command: str) -> None:
    """Every research stage file carries the verbatim thirteen-stage sequence."""
    assert CANONICAL_RESEARCH_SEQUENCE_STRING in _read(command), (
        f"{command}.md does not embed the canonical research sequence string "
        f"{CANONICAL_RESEARCH_SEQUENCE_STRING!r} — sequence drift"
    )


@pytest.mark.parametrize(("position", "command"), list(enumerate(RESEARCH_CHAIN)))
def test_research_sequence_gate_blocks_on_predecessor(
    position: int, command: str
) -> None:
    """Each non-entry research stage blocks on its predecessor; the entry
    stage (research-ideate) declares no predecessor and is never blocked, and
    the terminal stage (research-disseminate) has no successor downstream."""
    text = _read(command)
    # Whitespace-robust: collapse runs of whitespace before substring search.
    collapsed = re.sub(r"\s+", " ", text)
    # A live Sequence-Gate block line names a concrete predecessor stage; the
    # placeholder form ``/research-<predecessor>`` (used in prose that explains
    # the convention, e.g. in the entry stage) is deliberately excluded.
    concrete_block = re.compile(r"Blocked: run /(research-[a-z]+) first")

    if position == 0:
        # research-ideate is the entry stage: no concrete Blocked-on-predecessor
        # line. The placeholder ``/research-<predecessor>`` mention is allowed.
        assert command == "research-ideate", (
            f"entry research stage must be research-ideate, got {command!r}"
        )
        assert not concrete_block.search(collapsed), (
            f"entry stage {command} must not carry a concrete "
            f"Blocked-on-predecessor line — it has no predecessor"
        )
    else:
        predecessor = RESEARCH_CHAIN[position - 1]
        expected = f"Blocked: run /{predecessor} first"
        assert expected in collapsed, (
            f"{command}.md Sequence Gate omits {expected!r}; a non-entry stage "
            f"must block on its predecessor /{predecessor}"
        )

    if position == len(RESEARCH_CHAIN) - 1:
        # research-disseminate is terminal: nothing downstream blocks on it.
        assert command == "research-disseminate", (
            f"terminal research stage must be research-disseminate, got {command!r}"
        )


@pytest.mark.parametrize(("position", "command"), list(enumerate(FORTRESS_CHAIN)))
def test_fortress_upstream_downstream_chain(position: int, command: str) -> None:
    """Each command's Upstream/Downstream reconstructs the linear chain."""
    text = _read(command)
    upstream = _first_token(_segment(text, "**Upstream:**"))
    downstream = _first_token(_segment(text, "**Downstream:**"))

    if position == 0:
        assert upstream == "none", (
            f"entry command {command} must declare Upstream none "
            f"from the fortress, got {upstream!r}"
        )
    else:
        assert upstream == FORTRESS_CHAIN[position - 1], (
            f"{command} Upstream {upstream!r} != {FORTRESS_CHAIN[position - 1]!r}"
        )

    if position == len(FORTRESS_CHAIN) - 1:
        assert downstream == "none", (
            f"terminal command {command} must declare Downstream none, "
            f"got {downstream!r}"
        )
    else:
        assert downstream == FORTRESS_CHAIN[position + 1], (
            f"{command} Downstream {downstream!r} != {FORTRESS_CHAIN[position + 1]!r}"
        )


def test_code_review_is_fortress_entry() -> None:
    """The chain is entered at /code-review, never elsewhere."""
    assert FORTRESS_CHAIN[0] == "code-review"
    text = _read("code-review")
    assert "entry point" in text.lower()


@pytest.mark.parametrize(
    ("command", "expected_successors"),
    [
        ("plan-spec", ("/plan-generate",)),
        ("plan-generate", ("/plan-review",)),
        # Conditional handoff: architecture-bearing → design, else execute.
        ("plan-review", ("/plan-design", "/plan-execute")),
        ("plan-design", ("/plan-execute",)),
        ("plan-execute", ("/code-review",)),
        ("plan-audit", ("/plan-execute",)),
        # /plan-amend re-derives the affected artifacts, then re-audits.
        ("plan-amend", ("/plan-review",)),
    ],
)
def test_plan_command_recommends_successor(
    command: str, expected_successors: tuple[str, ...]
) -> None:
    """Each /plan stage terminal handoff names its canonical successor(s)."""
    block = _next_step_block(_read(command))
    for successor in expected_successors:
        assert successor in block, (
            f"{command}.md next-step block omits successor {successor!r}; "
            f"block was:\n{block}"
        )


def test_plan_review_records_design_skip_logic() -> None:
    """plan-review routes architecture-bearing suites through /plan-design."""
    block = _next_step_block(_read("plan-review"))
    assert "/plan-design" in block, (
        "plan-review must offer the architecture-bearing /plan-design route"
    )
    assert "/plan-execute" in block, (
        "plan-review must offer the direct /plan-execute route"
    )
    assert "architecture-bearing" in block.lower(), (
        "plan-review next-step block must record the architecture-bearing "
        "routing condition (the /plan-design skip logic)"
    )


def test_plan_audit_is_orthogonal_not_fortress_downstream() -> None:
    """plan-audit is the orthogonal pre-execute closure, not fortress tail."""
    text = _read("plan-audit").lower()
    assert "orthogonal" in text, "plan-audit must declare its orthogonal role"
    assert "/plan-execute" in text, (
        "plan-audit must leave the suite ready for /plan-execute"
    )
    # It must not model itself as a downstream consumer of a fortress command.
    assert "downstream of /threat-model-audit" not in text
    assert "fortress chain's downstream" not in text or (
        "not the fortress chain's downstream" in text
        or "not modeled as the fortress" in text
    )
