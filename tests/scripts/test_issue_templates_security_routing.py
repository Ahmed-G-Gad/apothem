# SPDX-License-Identifier: MIT

"""Security-disclosure routing invariant for the GitHub issue templates.

The repository routes vulnerability reports through GitHub Private Vulnerability
Reporting (SECURITY.md names it the primary preferred channel). A public
`.github/ISSUE_TEMPLATE/*.yml` issue *form* can only ever open a public issue,
so any public "security disclosure" form contradicts that policy by inviting
disclosure through the de-prioritized public channel.

These tests pin the routing so a public security form cannot be reintroduced
without a failing signal: no issue-template YAML declares itself a security
report form, blank issues stay disabled, and the config carries a contact link
that points reporters at the repository Security tab.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATE_DIR = _REPO_ROOT / ".github" / "ISSUE_TEMPLATE"


def _load_yaml(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{path} did not parse to a mapping"
    return loaded


def test_no_public_security_disclosure_form() -> None:
    """No issue-template form routes security disclosure through a public issue."""
    form_files = [p for p in _TEMPLATE_DIR.glob("*.yml") if p.name != "config.yml"]
    assert form_files, "expected at least one issue-template form to be present"

    for form in form_files:
        data = _load_yaml(form)
        name = str(data.get("name", ""))
        title = str(data.get("title", ""))
        labels = data.get("labels") or []
        label_set = {str(label).lower() for label in labels}

        signals_security_report = (
            "security" in name.lower()
            or "vulnerabilit" in name.lower()
            or "[security]" in title.lower()
            or "security" in label_set
        )
        assert not signals_security_report, (
            f"{form.name} presents a public security-report form; vulnerability "
            f"disclosure must route to GitHub Private Vulnerability Reporting "
            f"(the Security tab), never a public issue"
        )


def test_config_routes_security_privately() -> None:
    """config.yml disables blank issues and links reporters to the Security tab."""
    config = _load_yaml(_TEMPLATE_DIR / "config.yml")

    assert config.get("blank_issues_enabled") is False, (
        "blank_issues_enabled must be False so an ad-hoc public issue cannot "
        "become a de-facto disclosure channel"
    )

    contact_links = config.get("contact_links") or []
    security_links = [
        link
        for link in contact_links
        if isinstance(link, dict) and "/security" in str(link.get("url", ""))
    ]
    assert security_links, (
        "config.yml must carry a contact link routing security disclosure to "
        "the repository Security tab (private vulnerability reporting)"
    )
