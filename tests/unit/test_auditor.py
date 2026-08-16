# SPDX-License-Identifier: MIT

"""Unit tests for the unified conformance / security auditor.

Covers the three capabilities (config scan, secret detection, conformance), the
advisory-by-default + strict opt-in semantics, schema-validated output, the
closed secret catalog, the standalone CLI, and the pull-request audit contract.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from apothem.lib import auditor
from apothem.lib.auditor import (
    SECRET_PATTERNS,
    SECRET_PATTERNS_NA,
    AuditorError,
    Finding,
    Findings,
    Location,
    PrAuditInput,
    audit,
    detect_secrets,
    pr_audit,
    resolve_strict,
    run_conformance,
    scan_config,
    validate_findings,
)

_GHP_TOKEN = "ghp_" + "a" * 36
_AWS_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


# --- config scanning --------------------------------------------------------


def test_scan_config_parses_yaml(tmp_path: Path) -> None:
    cfg = _write(tmp_path, "ok.yaml", "name: demo\nvalues:\n  - a\n  - b\n")
    structure, finding = scan_config(cfg)
    assert finding is None
    assert structure == {"name": "demo", "values": ["a", "b"]}


def test_scan_config_missing_file_returns_finding(tmp_path: Path) -> None:
    structure, finding = scan_config(tmp_path / "absent.yaml")
    assert structure is None
    assert finding is not None
    assert finding.category == "config-scan"
    assert finding.id == "config-unreadable"


def test_scan_config_malformed_json_returns_finding_not_crash(tmp_path: Path) -> None:
    cfg = _write(tmp_path, "broken.json", "{ not valid json ")
    structure, finding = scan_config(cfg)
    assert structure is None
    assert finding is not None
    assert finding.category == "config-scan"
    assert finding.id == "config-malformed"
    assert finding.next_step  # non-empty determinant move


def test_audit_clean_config_reports_zero(tmp_path: Path) -> None:
    cfg = _write(tmp_path, "clean.yaml", "name: ok\npermissions:\n  - read\n  - list\n")
    result = audit([cfg])
    assert result.summary["total"] == 0
    assert result.present is False


# --- secret detection -------------------------------------------------------


def test_detect_secrets_reports_planted_token_with_location(tmp_path: Path) -> None:
    cfg = _write(tmp_path, "leak.yaml", f"token: {_GHP_TOKEN}\n")
    findings = detect_secrets(cfg, cfg.read_text(encoding="utf-8"))
    assert len(findings) == 1
    finding = findings[0]
    assert finding.category == "secret"
    assert finding.id == "secret-github-personal-token"
    assert finding.location.line == 1
    assert finding.location.column is not None


def test_detect_secrets_clean_fixture_reports_zero(tmp_path: Path) -> None:
    cfg = _write(tmp_path, "clean.yaml", "name: ok\nport: 8080\nlevel: info\n")
    assert detect_secrets(cfg, cfg.read_text(encoding="utf-8")) == []


def test_detect_secrets_aws_key(tmp_path: Path) -> None:
    cfg = _write(tmp_path, "aws.txt", f"aws_key = {_AWS_KEY}\n")
    findings = detect_secrets(cfg, cfg.read_text(encoding="utf-8"))
    assert any(f.id == "secret-aws-access-key-id" for f in findings)


def test_detect_secrets_pem_private_key(tmp_path: Path) -> None:
    cfg = _write(tmp_path, "key.pem", "-----BEGIN RSA PRIVATE KEY-----\nMII...\n")
    findings = detect_secrets(cfg, cfg.read_text(encoding="utf-8"))
    assert any(f.id == "secret-pem-private-key" for f in findings)


def test_detect_secrets_identity_allowlist_not_flagged(tmp_path: Path) -> None:
    # An owner-identity line must never trip the high-entropy heuristic.
    cfg = _write(
        tmp_path, "banner.md", "maintainer: me@ahmedgad.com github.com/ahmed-g-gad\n"
    )
    assert detect_secrets(cfg, cfg.read_text(encoding="utf-8")) == []


def test_detect_secrets_allowlist_does_not_shield_colocated_token(
    tmp_path: Path,
) -> None:
    """A live token sharing a line with the owner identity is still reported.

    The allowlist applies at match granularity: an identity string elsewhere
    on the line must not blind the scanner to a real secret.
    """
    cfg = _write(
        tmp_path,
        "colocated.yaml",
        f"# contact me@ahmedgad.com\ntoken: {_GHP_TOKEN}  # me@ahmedgad.com\n",
    )
    findings = detect_secrets(cfg, cfg.read_text(encoding="utf-8"))
    assert any(f.id == "secret-github-personal-token" for f in findings)
    assert all(f.location.line == 2 for f in findings)


def test_detect_secrets_high_entropy_token(tmp_path: Path) -> None:
    token = "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zA5bC7dE9f"  # noqa: S105 — 44-char high-entropy blob
    cfg = _write(tmp_path, "blob.txt", f"opaque = {token}\n")
    findings = detect_secrets(cfg, cfg.read_text(encoding="utf-8"))
    assert any(
        f.id == "secret-high-entropy-token" and f.severity == "LOW" for f in findings
    )


def test_detect_secrets_entropy_suppresses_placeholder(tmp_path: Path) -> None:
    cfg = _write(
        tmp_path, "ph.txt", "token = your-example-placeholder-value-goes-right-here\n"
    )
    assert detect_secrets(cfg, cfg.read_text(encoding="utf-8")) == []


# --- conformance ------------------------------------------------------------


@pytest.mark.parametrize(
    "grant",
    [
        "rm -rf /tmp/x",
        "sudo systemctl restart",
        "git push --force origin main",
        "cat ~/.ssh/id_rsa",
    ],
)
def test_run_conformance_flags_denied_grant(tmp_path: Path, grant: str) -> None:
    findings = run_conformance(tmp_path / "c.yaml", {"permissions": [grant]})
    assert len(findings) == 1
    assert findings[0].category == "conformance"
    assert findings[0].id == "denied-grant"
    assert findings[0].severity == "HIGH"


def test_run_conformance_clean_config_reports_zero(tmp_path: Path) -> None:
    findings = run_conformance(tmp_path / "c.yaml", {"permissions": ["read", "list"]})
    assert findings == []


# --- finding schema + output contract ---------------------------------------


def test_audit_output_validates_against_schema(tmp_path: Path) -> None:
    cfg = _write(
        tmp_path, "dirty.yaml", f'token: {_GHP_TOKEN}\npermissions:\n  - "rm -rf /"\n'
    )
    result = audit([cfg])
    validate_findings(result.to_dict())  # raises on violation


def test_validate_findings_rejects_bad_payload() -> None:
    bad = {
        "findings": [{"id": "x"}],
        "strict": False,
        "summary": {"total": 1, "high": 0, "medium": 0, "low": 0},
    }
    with pytest.raises(AuditorError):
        validate_findings(bad)


def test_finding_to_dict_omits_absent_location_fields() -> None:
    finding = Finding(
        id="x",
        category="conformance",
        severity="LOW",
        location=Location(path="p"),
        message="m",
        next_step="n",
    )
    assert finding.to_dict()["location"] == {"path": "p"}


def test_findings_summary_counts_by_severity() -> None:
    findings = (
        Finding(
            id="a",
            category="secret",
            severity="HIGH",
            location=Location("p"),
            message="m",
            next_step="n",
        ),
        Finding(
            id="b",
            category="conformance",
            severity="LOW",
            location=Location("p"),
            message="m",
            next_step="n",
        ),
    )
    result = Findings(findings=findings, strict=False)
    assert result.summary == {"total": 2, "high": 1, "medium": 0, "low": 1}


def test_every_finding_carries_next_step(tmp_path: Path) -> None:
    cfg = _write(
        tmp_path, "dirty.yaml", f'token: {_GHP_TOKEN}\npermissions: ["sudo rm"]\n'
    )
    result = audit([cfg])
    assert result.present
    assert all(f.next_step.strip() for f in result.findings)


# --- secret catalog closed set ----------------------------------------------


def test_secret_catalog_is_closed_and_well_formed() -> None:
    assert len(SECRET_PATTERNS) == 10
    labels = [p.label for p in SECRET_PATTERNS]
    assert len(labels) == len(set(labels))  # no duplicate labels
    for pattern in SECRET_PATTERNS:
        assert pattern.label
        assert pattern.match_rule
        re.compile(pattern.match_rule)  # every match_rule compiles


def test_secret_catalog_na_attestation_present() -> None:
    assert len(SECRET_PATTERNS_NA) >= 1
    assert all(isinstance(item, str) and item for item in SECRET_PATTERNS_NA)


# --- advisory / strict semantics --------------------------------------------


def test_resolve_strict_flag_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(auditor.STRICT_ENV, raising=False)
    assert resolve_strict(True) is True
    assert resolve_strict(False) is False


def test_resolve_strict_env_optin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(auditor.STRICT_ENV, "1")
    assert resolve_strict(False) is True
    monkeypatch.setenv(auditor.STRICT_ENV, "off")
    assert resolve_strict(False) is False


def test_audit_results_are_deterministically_ordered(tmp_path: Path) -> None:
    cfg = _write(
        tmp_path, "multi.yaml", f'a: {_GHP_TOKEN}\npermissions: ["rm -rf /"]\n'
    )
    first = audit([cfg]).to_dict()
    second = audit([cfg]).to_dict()
    assert first == second


# --- directory expansion + pr_audit -----------------------------------------


def test_audit_expands_directories(tmp_path: Path) -> None:
    _write(tmp_path, "a.yaml", f"t: {_GHP_TOKEN}\n")
    _write(tmp_path, "b.yaml", "clean: true\n")
    result = audit([tmp_path])
    assert result.summary["total"] == 1


def test_pr_audit_delegates_to_audit(tmp_path: Path) -> None:
    cfg = _write(tmp_path, "changed.yaml", f"t: {_GHP_TOKEN}\n")
    result = pr_audit(
        PrAuditInput(changed_paths=(cfg,), repo_context={"branch": "main"})
    )
    assert result.summary["total"] == 1
    validate_findings(result.to_dict())


# --- standalone CLI ---------------------------------------------------------


def test_cli_advisory_exits_zero_with_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = _write(tmp_path, "leak.yaml", f"t: {_GHP_TOKEN}\n")
    code = auditor.main([str(cfg)])
    assert code == 0
    assert "advisory" in capsys.readouterr().out


def test_cli_strict_exits_one_with_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = _write(tmp_path, "leak.yaml", f"t: {_GHP_TOKEN}\n")
    code = auditor.main([str(cfg), "--strict"])
    capsys.readouterr()
    assert code == 1


def test_cli_clean_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = _write(tmp_path, "clean.yaml", "name: ok\n")
    code = auditor.main([str(cfg), "--strict"])
    capsys.readouterr()
    assert code == 0


def test_cli_json_output_is_schema_valid(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = _write(tmp_path, "leak.yaml", f"t: {_GHP_TOKEN}\n")
    auditor.main([str(cfg), "--json"])
    payload = json.loads(capsys.readouterr().out)
    validate_findings(payload)
    assert payload["summary"]["total"] == 1


def test_audit_reads_each_file_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file is read once per audit, not once per capability.

    ``audit`` expands directories with ``rglob``, so a second read inside
    ``scan_config`` would double the I/O of every whole-tree run. The parse
    and the secret scan both need the same text; the caller reads it once and
    passes it down.
    """
    cfg = tmp_path / "config.yaml"
    cfg.write_text("alpha: 1\n", encoding="utf-8")

    reads: list[str] = []
    real_read_text = Path.read_text

    def counting_read_text(self: Path, *args: object, **kwargs: object) -> str:
        reads.append(str(self))
        return real_read_text(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", counting_read_text)

    findings = audit([cfg])

    assert reads.count(str(cfg)) == 1
    # The audit still produced a usable result from that single read.
    assert findings.findings == [] or all(f.category for f in findings.findings)
