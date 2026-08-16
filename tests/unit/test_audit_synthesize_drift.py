# SPDX-License-Identifier: MIT

"""Unit tests for the drift synthesiser.

``apothem.audit.synthesize_drift`` aggregates the per-scanner drift JSON
outputs from an ``--audit-dir`` into one findings document. This test
guards that ``_gather`` resolves each scanner's drift JSON from the audit
directory by filename, so an ``--audit-dir`` whose last path segment is not
literally ``.audit`` still resolves (the prior ``audit_root.parent /
rel_path`` join silently read absent files and reported everything missing).
"""

from __future__ import annotations

import json
from pathlib import Path

import apothem.audit.synthesize_drift as sd


class TestGather:
    """Gathering the drift findings.

    Covers resolution from a non-default audit directory and the missing
    directory yielding no findings rather than raising.
    """

    def test_resolves_drift_json_from_non_default_audit_dir(
        self, tmp_path: Path
    ) -> None:
        audit_dir = tmp_path / "audit_out"
        audit_dir.mkdir()
        (audit_dir / "drift-feature-refs.json").write_text(
            json.dumps(
                {
                    "hit-count": 1,
                    "hits": [
                        {
                            "file": "rules/x.md",
                            "line": 3,
                            "signal": "feature-ref",
                            "severity": "MEDIUM",
                            "remediation": "remove",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        findings, _envelopes = sd._gather(audit_dir)

        assert any(
            f.file == "rules/x.md" and f.scanner == "scan_drift_features"
            for f in findings
        )

    def test_missing_audit_dir_yields_no_findings(self, tmp_path: Path) -> None:
        findings, envelopes = sd._gather(tmp_path / "absent")

        assert findings == []
        assert all(e.get("missing") for e in envelopes)
