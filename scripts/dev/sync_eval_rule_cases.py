# SPDX-License-Identifier: MIT

"""Keep the rule-effect eval cases in step with the rules they measure.

Why this exists. A plugin eval run loads no rules and no ``CLAUDE.md``, so an
always-on rule's effect is measured with paired cases that differ only by
``append_system_prompt``: the ``rule-on`` case carries the rule's text, the
``rule-off`` case does not. That text is a copy, and a copy drifts the moment
the rule changes. This script rewrites every ``rule-on`` case's
``append_system_prompt`` from the rule source; ``--check`` reports drift and
exits 1 without writing, which is what the eval-suite test runs.

The copied text is the rule as a harness delivers it at runtime: the rule file
without its YAML frontmatter, without the SPDX comment line, and without the
trailing ``## Bindings`` section (maintainer cross-references, stripped from
runtime bodies). A case names its rule with the tag ``rule:<name>`` and its arm
with ``arm:rule-on`` or ``arm:rule-off``.

Exit codes: 0 in sync (or rewritten); 1 drift found with ``--check``.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
EVALS = REPO_ROOT / "evals"
RULES = SRC / "apothem" / "rules"

if str(SRC / "apothem" / "_vendor") not in sys.path:
    sys.path.insert(0, str(SRC / "apothem" / "_vendor"))

import yaml  # noqa: E402  (vendored PyYAML)

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_SPDX_LINE = re.compile(r"^<!-- SPDX-License-Identifier: MIT -->\n?", re.MULTILINE)
_BINDINGS = re.compile(r"^## Bindings\b.*\Z", re.MULTILINE | re.DOTALL)


def runtime_rule_text(rule_path: Path) -> str:
    """Return a rule's text as delivered at runtime (see module docstring)."""
    text = rule_path.read_text(encoding="utf-8")
    match = _FRONTMATTER.match(text)
    body = text[match.end() :] if match else text
    body = _SPDX_LINE.sub("", body)
    body = _BINDINGS.sub("", body)
    return body.strip() + "\n"


class _Dumper(yaml.SafeDumper):
    """Block style for multi-line strings, flow style for scalar lists."""


def _str_presenter(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    if "\n" in value:
        return dumper.represent_scalar("tag:yaml.org,2002:str", value, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", value)


def _list_presenter(dumper: yaml.SafeDumper, value: list[Any]) -> yaml.SequenceNode:
    flow = all(isinstance(item, (str, int, float, bool)) for item in value)
    return dumper.represent_sequence("tag:yaml.org,2002:seq", value, flow_style=flow)


_Dumper.add_representer(str, _str_presenter)
_Dumper.add_representer(list, _list_presenter)


def dump_frontmatter(fields: dict[str, Any]) -> str:
    """Return ``---\\n<yaml>---\\n`` for a case or grader frontmatter mapping."""
    text = yaml.dump(
        fields,
        Dumper=_Dumper,
        sort_keys=False,
        allow_unicode=True,
        width=100,
        default_flow_style=False,
    )
    return f"---\n{text}---\n"


def split_markdown(path: Path) -> tuple[dict[str, Any], str]:
    """Return ``(frontmatter mapping, body)`` of a case Markdown file."""
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER.match(text)
    if match is None:
        return {}, text
    fields = yaml.safe_load(match.group(1)) or {}
    if not isinstance(fields, dict):
        raise ValueError(f"{path}: frontmatter is not a mapping")
    return fields, text[match.end() :]


def rule_on_cases(evals: Path) -> list[tuple[Path, str]]:
    """Return ``(prompt.md, rule name)`` for every ``arm:rule-on`` case."""
    found = []
    for prompt in sorted(evals.rglob("prompt.md")):
        fields, _body = split_markdown(prompt)
        tags = [str(tag) for tag in fields.get("tags", [])]
        if "arm:rule-on" not in tags:
            continue
        names = [tag.split(":", 1)[1] for tag in tags if tag.startswith("rule:")]
        if len(names) != 1:
            raise ValueError(
                f"{prompt}: a rule-on case names exactly one rule:<name> tag"
            )
        found.append((prompt, names[0]))
    return found


def sync(evals: Path, rules: Path, *, check: bool) -> list[str]:
    """Rewrite (or, with ``check``, only compare) each rule-on case's text."""
    drift = []
    for prompt, rule in rule_on_cases(evals):
        source = rules / f"{rule}.md"
        if not source.is_file():
            drift.append(f"{prompt}: rule {rule!r} not found at {source}")
            continue
        expected = runtime_rule_text(source)
        fields, body = split_markdown(prompt)
        if str(fields.get("append_system_prompt", "")).strip() == expected.strip():
            continue
        drift.append(f"{prompt.relative_to(evals.parent)}: out of step with {rule}.md")
        if not check:
            fields["append_system_prompt"] = expected
            prompt.write_text(dump_frontmatter(fields) + body, encoding="utf-8")
    return drift


def main(argv: list[str] | None = None) -> int:
    """Sync or check the rule-effect cases; return the exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true", help="Report drift; write nothing."
    )
    args = parser.parse_args(argv)
    drift = sync(EVALS, RULES, check=args.check)
    for line in drift:
        print(line)
    if drift and args.check:
        print(
            f"sync-eval-rule-cases: {len(drift)} case(s) out of step; "
            "run python scripts/dev/sync_eval_rule_cases.py",
            file=sys.stderr,
        )
        return 1
    verb = "rewrote" if drift else "in step:"
    print(
        f"sync-eval-rule-cases: {verb} {len(drift) or len(rule_on_cases(EVALS))} case(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
