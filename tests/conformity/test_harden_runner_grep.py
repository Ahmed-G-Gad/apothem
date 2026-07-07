# SPDX-License-Identifier: MIT

"""Regression tests for harden-runner egress-policy resolution.

A reusable workflow may parameterize ``egress-policy`` via a
``workflow_call`` input (``${{ inputs.<name> }}``). The matcher resolves
that expression to the input's declared default so a conformant default
is not flagged as too-permissive.
"""

from __future__ import annotations

from pathlib import Path

from apothem.conformity import harden_runner_grep as hr

_REUSABLE_CONFORMANT = """\
name: reusable-setup
on:
  workflow_call:
    inputs:
      egress-policy:
        description: harden-runner egress policy.
        required: false
        type: string
        default: audit
jobs:
  setup-and-run:
    runs-on: ubuntu-latest
    steps:
      - name: Harden Runner
        uses: step-security/harden-runner@v2
        with:
          egress-policy: ${{ inputs.egress-policy }}
"""

_REUSABLE_PERMISSIVE_DEFAULT = """\
name: reusable-setup-bad
on:
  workflow_call:
    inputs:
      egress-policy:
        type: string
        default: log
jobs:
  setup-and-run:
    runs-on: ubuntu-latest
    steps:
      - name: Harden Runner
        uses: step-security/harden-runner@v2
        with:
          egress-policy: ${{ inputs.egress-policy }}
"""


def _write_workflow(root: Path, name: str, body: str) -> None:
    wf_dir = root / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / name).write_text(body, encoding="utf-8")


def test_parameterized_egress_with_conformant_default_passes(tmp_path: Path) -> None:
    _write_workflow(tmp_path, "reusable.yml", _REUSABLE_CONFORMANT)
    result = hr.check_root(tmp_path)
    assert result.passed, [f.detail for f in result.findings]


def test_parameterized_egress_with_permissive_default_fails(tmp_path: Path) -> None:
    _write_workflow(tmp_path, "reusable.yml", _REUSABLE_PERMISSIVE_DEFAULT)
    result = hr.check_root(tmp_path)
    assert not result.passed
    assert any(f.drift == hr.DRIFT_PERMISSIVE for f in result.findings)


def test_resolve_egress_literal_unchanged() -> None:
    assert hr._resolve_egress("block", {}) == "block"


def test_resolve_egress_expression_to_default() -> None:
    inputs = {"egress-policy": {"default": "block"}}
    assert hr._resolve_egress("${{ inputs.egress-policy }}", inputs) == "block"


def test_resolve_egress_expression_no_default_unchanged() -> None:
    expr = "${{ inputs.egress-policy }}"
    assert hr._resolve_egress(expr, {"egress-policy": {}}) == expr
