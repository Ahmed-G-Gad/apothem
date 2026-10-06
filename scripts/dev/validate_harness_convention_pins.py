#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Validate harness standard-convention pin coverage and freshness.

The adapter count is derived dynamically from ``_harness_dirs`` — this script
never hardcodes it. NOTE(dynamism): the harness-registry docs page narrates
this count in hand-authored prose ("the registry still enumerates seventeen
adapters") at ``site/content/docs/reference/harness-registry.mdx``. That prose
lives outside the generated reference block, so it must be bumped by hand when
the registry grows; a follow-up could surface the live count from this module
into that page so the number never goes stale.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Final

_PIN_LINE: Final[re.Pattern[str]] = re.compile(
    r"""^\s*standard_convention_pin\s*:\s*["']?(?P<path>[^"'\s#]+)["']?""",
    re.MULTILINE,
)
_SNAPSHOT_DATE_LINE: Final[re.Pattern[str]] = re.compile(
    r"^\s*-\s*Snapshot date:\s*(?P<date>\d{4}-\d{2}-\d{2})\s*$",
    re.MULTILINE,
)
_REQUIRED_PIN_FIELDS: Final[tuple[str, ...]] = (
    "- Snapshot date:",
    "- Adapter source:",
    "- Evidence level:",
    "## Recommended Postfix Rendering",
    "## Long Context and Compaction",
    "## Large-Codebase Practice Projection",
)
_BRANCH_POINTED_URL: Final[re.Pattern[str]] = re.compile(
    r"https?://[^\s)]+/(?:blob|tree)/(?:main|master|HEAD|trunk)(?:/|\b)"
)
_ABSOLUTE_URL: Final[re.Pattern[str]] = re.compile(r"https://[^\s<>()\[\]`\"'|]+")
# Addresses that are not vendor evidence: Apothem's own site and repository,
# and the reserved example / loopback hosts.
_PROJECT_HOSTS: Final[frozenset[str]] = frozenset({"apothem.ahmedgad.com"})
_PROJECT_REPO_PREFIXES: Final[tuple[str, ...]] = (
    "github.com/ahmed-g-gad/apothem",
    "raw.githubusercontent.com/ahmed-g-gad/apothem",
)
_RESERVED_DOMAINS: Final[tuple[str, ...]] = (
    "example.com",
    "example.org",
    "example.net",
    "localhost",
)
# ``- Discovery target: <capability> by <YYYY-MM-DD> — <what is decided>``
_DISCOVERY_LINE: Final[re.Pattern[str]] = re.compile(
    r"^\s*-\s*Discovery target:(?P<rest>.*)$", re.MULTILINE
)
_DISCOVERY_TARGET: Final[re.Pattern[str]] = re.compile(
    r"^\s*(?P<capability>[a-z_]+)\s+by\s+(?P<date>\S+)"
)


@dataclass(frozen=True)
class DriftedHarness:
    """A harness convention pin that is missing, malformed, or stale."""

    harness: str
    reason: str
    pin_path: str
    snapshot_date: str | None = None
    age_days: int | None = None
    pinned_sha: str = "n/a"
    observed_sha: str = "n/a"


@dataclass(frozen=True)
class CheckedHarness:
    """A harness convention pin that passed validation."""

    harness: str
    pin_path: str
    snapshot_date: str
    age_days: int
    discovery_targets: dict[str, str] = field(default_factory=dict)


def _harness_dirs(root: Path) -> list[Path]:
    """Return harness directories that declare a capabilities manifest."""
    return sorted(
        child
        for child in root.iterdir()
        if child.is_dir()
        and not child.name.startswith(".")
        and not child.name.startswith("_")
        and (child / "capabilities.yml").is_file()
    )


def _pin_relpath(capabilities_path: Path) -> str:
    """Extract the declared standard-convention pin path."""
    text = capabilities_path.read_text(encoding="utf-8")
    match = _PIN_LINE.search(text)
    if match is None:
        return "STANDARD-CONVENTION-PIN.md"
    return match.group("path")


def _snapshot_date(pin_path: Path) -> date | None:
    """Extract the pin snapshot date."""
    text = pin_path.read_text(encoding="utf-8")
    match = _SNAPSHOT_DATE_LINE.search(text)
    if match is None:
        return None
    try:
        return date.fromisoformat(match.group("date"))
    except ValueError:
        return None


def _is_vendor_url(url: str) -> bool:
    """Return True when *url* points at a vendor rather than Apothem or a placeholder."""
    address = url.split("://", 1)[1]
    host = address.split("/", 1)[0].split(":", 1)[0].lower()
    if host in _PROJECT_HOSTS or address.startswith(_PROJECT_REPO_PREFIXES):
        return False
    return not any(
        host == domain or host.endswith(f".{domain}") for domain in _RESERVED_DOMAINS
    )


def _pin_schema_error(pin_path: Path) -> str | None:
    """Return the first convention-pin schema error, if any."""
    text = pin_path.read_text(encoding="utf-8")
    for required in _REQUIRED_PIN_FIELDS:
        if required not in text:
            return f"standard convention pin is missing required field: {required}"
    if _BRANCH_POINTED_URL.search(text):
        return "standard convention pin uses branch-pointed evidence URL"
    if not any(_is_vendor_url(m.group(0)) for m in _ABSOLUTE_URL.finditer(text)):
        return "standard convention pin cites no absolute vendor URL"
    return None


def _discovery_targets(pin_path: Path) -> tuple[dict[str, date], str | None]:
    """Parse the pin's discovery targets; return (targets, first error)."""
    text = pin_path.read_text(encoding="utf-8")
    targets: dict[str, date] = {}
    for line in _DISCOVERY_LINE.finditer(text):
        match = _DISCOVERY_TARGET.match(line.group("rest"))
        if match is None:
            return targets, (
                "Discovery target line must read "
                "'<capability> by <YYYY-MM-DD>': " + line.group(0).strip()
            )
        capability, raw_date = match.group("capability"), match.group("date")
        try:
            targets[capability] = date.fromisoformat(raw_date)
        except ValueError:
            return targets, (
                f"discovery target for {capability} has an invalid date: {raw_date}"
            )
    return targets, None


def _validate(
    harnesses_root: Path,
    today: date,
    max_age_days: int,
) -> tuple[list[CheckedHarness], list[DriftedHarness]]:
    """Validate all harness pin declarations under ``harnesses_root``."""
    checked: list[CheckedHarness] = []
    drifted: list[DriftedHarness] = []

    for harness_dir in _harness_dirs(harnesses_root):
        capabilities_path = harness_dir / "capabilities.yml"
        pin_relpath = _pin_relpath(capabilities_path)
        pin_path = harness_dir / pin_relpath
        rel_pin = pin_path.as_posix()

        if not pin_path.is_file():
            drifted.append(
                DriftedHarness(
                    harness=harness_dir.name,
                    reason="standard convention pin is missing",
                    pin_path=rel_pin,
                )
            )
            continue

        schema_error = _pin_schema_error(pin_path)
        if schema_error is not None:
            drifted.append(
                DriftedHarness(
                    harness=harness_dir.name,
                    reason=schema_error,
                    pin_path=rel_pin,
                )
            )
            continue

        snapshot = _snapshot_date(pin_path)
        if snapshot is None:
            drifted.append(
                DriftedHarness(
                    harness=harness_dir.name,
                    reason="snapshot date is missing or invalid",
                    pin_path=rel_pin,
                )
            )
            continue

        age_days = (today - snapshot).days
        if age_days < 0:
            drifted.append(
                DriftedHarness(
                    harness=harness_dir.name,
                    reason="snapshot date is in the future",
                    pin_path=rel_pin,
                    snapshot_date=snapshot.isoformat(),
                    age_days=age_days,
                )
            )
            continue

        if age_days > max_age_days:
            drifted.append(
                DriftedHarness(
                    harness=harness_dir.name,
                    reason=f"snapshot is older than {max_age_days} days",
                    pin_path=rel_pin,
                    snapshot_date=snapshot.isoformat(),
                    age_days=age_days,
                )
            )
            continue

        targets, target_error = _discovery_targets(pin_path)
        overdue = sorted(
            (due, capability) for capability, due in targets.items() if due < today
        )
        if target_error is None and overdue:
            due, capability = overdue[0]
            target_error = (
                f"discovery target for {capability} is overdue (due {due.isoformat()})"
            )
        if target_error is not None:
            drifted.append(
                DriftedHarness(
                    harness=harness_dir.name,
                    reason=target_error,
                    pin_path=rel_pin,
                    snapshot_date=snapshot.isoformat(),
                    age_days=age_days,
                )
            )
            continue

        checked.append(
            CheckedHarness(
                harness=harness_dir.name,
                pin_path=rel_pin,
                snapshot_date=snapshot.isoformat(),
                age_days=age_days,
                discovery_targets={
                    capability: due.isoformat() for capability, due in targets.items()
                },
            )
        )

    return checked, drifted


def _payload(
    harnesses_root: Path,
    today: date,
    max_age_days: int,
    checked: list[CheckedHarness],
    drifted: list[DriftedHarness],
) -> dict[str, object]:
    """Build the JSON report payload."""
    return {
        "validator": "validate_harness_convention_pins",
        "passed": not drifted,
        "generated_at": today.isoformat(),
        "harnesses_root": harnesses_root.as_posix(),
        "harness_count": len(checked) + len(drifted),
        "max_age_days": max_age_days,
        "checked_harnesses": [asdict(item) for item in checked],
        "drifted_harnesses": [asdict(item) for item in drifted],
    }


def _write_payload(payload: dict[str, object], output: Path | None) -> None:
    """Write the validation report to a file or stdout."""
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output is None:
        sys.stdout.write(rendered)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate that each harness adapter declares a fresh "
            "STANDARD-CONVENTION-PIN.md snapshot."
        )
    )
    parser.add_argument(
        "--harnesses-root",
        type=Path,
        default=Path("src/apothem/harnesses"),
        help="Root directory containing harness adapter packages.",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=90,
        help="Maximum allowed age for a pin snapshot.",
    )
    parser.add_argument(
        "--today",
        type=date.fromisoformat,
        default=None,
        help="Override today's date for deterministic tests.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON report output path.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = _parse_args(argv)
    harnesses_root: Path = args.harnesses_root
    today: date = args.today or date.today()
    max_age_days: int = args.max_age_days
    output: Path | None = args.output

    if max_age_days < 0:
        sys.stderr.write("--max-age-days must be non-negative\n")
        return 1

    if not harnesses_root.is_dir():
        sys.stderr.write(f"harnesses root not found: {harnesses_root}\n")
        return 1

    checked, drifted = _validate(
        harnesses_root=harnesses_root,
        today=today,
        max_age_days=max_age_days,
    )
    payload = _payload(
        harnesses_root=harnesses_root,
        today=today,
        max_age_days=max_age_days,
        checked=checked,
        drifted=drifted,
    )
    _write_payload(payload, output)

    return 2 if drifted else 0


if __name__ == "__main__":
    raise SystemExit(main())
