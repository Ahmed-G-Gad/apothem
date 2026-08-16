# SPDX-License-Identifier: MIT

"""Unit tests for the secrets / PII / paths scanner.

``apothem.audit.scan_secrets_pii`` walks narrative artifacts for secret
patterns, non-banner email tokens, and absolute home-directory paths. The PII
pass exempts exactly one contact — the canonical banner email — and flags every
other email MEDIUM. This module pins the email exemption and guards against the
retired website / github-handle / name constants being re-introduced as dead
code.
"""

from __future__ import annotations

import apothem.audit.scan_secrets_pii as ssp


class TestScanPii:
    """Scanning for personally-identifying information.

    Covers the banner email being exempt while a non-banner email is a
    medium-severity finding, including the mixed case where only the
    non-banner addresses are flagged.
    """

    def test_banner_email_is_exempt(self) -> None:
        assert ssp._scan_pii("docs/x.md", f"contact {ssp.BANNER_EMAIL}\n") == []

    def test_non_banner_email_is_medium_severity(self) -> None:
        hits = ssp._scan_pii("docs/x.md", "reach me at other@example.com\n")
        assert len(hits) == 1
        assert hits[0].severity == ssp.SEVERITY_MEDIUM
        assert hits[0].signal.startswith("non-banner-email:")
        assert "other@example.com" in hits[0].signal

    def test_banner_email_among_other_emails_only_flags_the_others(self) -> None:
        content = f"{ssp.BANNER_EMAIL} and stranger@example.org\n"
        hits = ssp._scan_pii("docs/x.md", content)
        assert len(hits) == 1
        assert "stranger@example.org" in hits[0].signal


class TestBannerConstants:
    """The exempt banner constants.

    Covers that only the wired constants are defined, so an unused exemption
    cannot silently widen the allow-list.
    """

    def test_only_the_wired_banner_constants_are_defined(self) -> None:
        # Regression guard: BANNER_WEBSITE / BANNER_GITHUB_HANDLE / BANNER_NAME
        # were removed as dead code — the module has no website / handle / name
        # detector for them to exempt. Only the two wired constants remain:
        # BANNER_EMAIL (the _scan_pii exemption) and BANNER_USERNAME (the
        # _scan_paths anchor). Re-introducing an unused sibling fails here.
        banner_names = {n for n in vars(ssp) if n.startswith("BANNER_")}
        assert banner_names == {"BANNER_EMAIL", "BANNER_USERNAME"}
