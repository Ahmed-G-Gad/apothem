# SPDX-License-Identifier: MIT

"""Unit tests for the artifact classifier.

``apothem.audit.classify_artifacts`` consumes the per-scanner drift JSON
outputs from an ``--audit-dir`` and assigns one verdict per inventory
artifact. These tests guard two behaviours that the audit-cohort root
convention touched:

- ``_load_scan_findings`` resolves each scanner's drift JSON from the
  audit directory by filename, so an ``--audit-dir`` whose last path
  segment is not literally ``.audit`` still resolves (the prior
  ``audit_dir.parent / rel_path`` join silently read absent files).
- ``_is_genuine_secret`` flags any secret-candidate hit. The classifier
  consumes the content-root inventory, so the former path-based exemptions
  for ``tests/`` fixtures and ``.credentials.json`` (both outside the
  content root) could not fire and were removed.
"""

from __future__ import annotations

import json
from pathlib import Path

import apothem.audit.classify_artifacts as ca


class TestLoadScanFindings:
    def test_resolves_drift_json_from_non_default_audit_dir(
        self, tmp_path: Path
    ) -> None:
        # Regression guard: the loader joins audit_dir / <filename>, not
        # audit_dir.parent / ".audit/<filename>", so a non-".audit" audit
        # directory still resolves the per-scanner drift JSON files.
        audit_dir = tmp_path / "audit_out"
        audit_dir.mkdir()
        (audit_dir / "drift-feature-refs.json").write_text(
            json.dumps(
                {
                    "hits": [
                        {
                            "file": "rules/x.md",
                            "line": 1,
                            "signal": "feature-ref",
                            "severity": "MEDIUM",
                            "remediation": "",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        by_file = ca._load_scan_findings(audit_dir)

        assert "rules/x.md" in by_file
        assert by_file["rules/x.md"][0]["scanner"] == "scan_drift_features"

    def test_missing_audit_dir_yields_empty_mapping(self, tmp_path: Path) -> None:
        assert ca._load_scan_findings(tmp_path / "absent") == {}


class TestIsGenuineSecret:
    def test_secret_candidate_hit_is_genuine(self) -> None:
        hits = [{"signal": "secret-candidate:aws-key"}]
        assert ca._is_genuine_secret(hits) is True

    def test_former_fixture_paths_no_longer_exempt(self) -> None:
        # A secret-candidate hit is genuine regardless of path now that the
        # out-of-content-root exemptions are gone.
        hits = [{"signal": "secret-candidate:token"}]
        assert ca._is_genuine_secret(hits) is True

    def test_non_secret_hit_is_not_genuine(self) -> None:
        hits = [{"signal": "stale-token"}]
        assert ca._is_genuine_secret(hits) is False

    def test_empty_hits_is_not_genuine(self) -> None:
        assert ca._is_genuine_secret([]) is False
