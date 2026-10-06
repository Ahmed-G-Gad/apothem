# SPDX-License-Identifier: MIT

# Makefile — apothem build / validate / release runner.
#
# Make is the canonical orchestration surface for every cross-tool target.
# Each target invokes the tool
# in scripts/ or pytest at the canonical entry point.
#
# Usage: `make <target>`. Run `make help` for a rendered target list.

PYTHON       ?= python
PIP          ?= $(PYTHON) -m pip
PYTEST       ?= $(PYTHON) -m pytest
RUFF         ?= $(PYTHON) -m ruff
MYPY         ?= $(PYTHON) -m mypy
INJECT       ?= $(PYTHON) scripts/inject-header.py
CONFORMITY   ?= $(PYTHON) -m apothem.conformity.gate
AUDIT_ALL    ?= $(PYTHON) scripts/dev/audit_all.py
VALIDATE     ?= $(PYTHON) scripts/dev/validate_ecosystem.py

.DEFAULT_GOAL := help
.PHONY: help install uninstall update lint format test validate \
        validate-ecosystem audit release plans-doctor headers-doctor \
        headers-fix ai-surfaces-doctor benchmarks clean

# ----- meta ----------------------------------------------------------

help:
	@echo "apothem — Make targets"
	@echo ""
	@echo "  install                Install the ecosystem (Claude Code adapter installs under ~/.claude; paired scripts/installer/install.sh / install.ps1)."
	@echo "  uninstall              Uninstall with default-backup (paired scripts/installer/uninstall.sh / uninstall.ps1)."
	@echo "  update                 Re-fetch the Apothem source and re-materialize harness config (paired scripts/installer/update.sh / update.ps1)."
	@echo ""
	@echo "  lint                   Run ruff check + ruff format --check across the tree."
	@echo "  format                 Run ruff format (writes); follow with lint to verify."
	@echo "  test                   Run pytest across tests/."
	@echo "  validate               Run the conformity gate --all --strict (every standalone validator; findings fail the run)."
	@echo "  validate-ecosystem     Run validate_ecosystem.py (structural + frontmatter validator)."
	@echo "  audit                  Run audit_all.py (drift / inventory / classification refresh)."
	@echo ""
	@echo "  plans-doctor           Walk plan-suite layout invariants (forge/spec/_inputs/_spec/phases)."
	@echo "  headers-doctor         Run file-header-grep across every applicable file (read-only check)."
	@echo "  headers-fix            Run inject-header.py --mode fix-in-place across every applicable file."
	@echo "  ai-surfaces-doctor     Run multi-surface-coherence + copilot-instructions-presence + license-author-consistency."
	@echo ""
	@echo "  benchmarks             Run src/apothem/benchmarks/ per-class budget verifiers."
	@echo "  release                Extract release notes for the current tag."
	@echo "  clean                  Remove __pycache__ / .pytest_cache / .mypy_cache / .ruff_cache / .hypothesis / *.egg-info caches."

# ----- install / uninstall / update (delegate to host-OS scripts) ----

install:
	@if command -v bash >/dev/null 2>&1; then bash scripts/installer/install.sh; else pwsh -NoProfile -File scripts/installer/install.ps1; fi

uninstall:
	@if command -v bash >/dev/null 2>&1; then bash scripts/installer/uninstall.sh; else pwsh -NoProfile -File scripts/installer/uninstall.ps1; fi

update:
	@if command -v bash >/dev/null 2>&1; then bash scripts/installer/update.sh; else pwsh -NoProfile -File scripts/installer/update.ps1; fi

# ----- code-craft surface --------------------------------------------

lint:
	$(RUFF) check .
	$(RUFF) format --check .

format:
	$(RUFF) format .
	$(RUFF) check --fix .

test:
	$(PYTEST)

# ----- conformity surface --------------------------------------------

validate:
	$(CONFORMITY) --all --strict

validate-ecosystem:
	$(VALIDATE)

audit:
	$(AUDIT_ALL)

plans-doctor:
	$(CONFORMITY) --check plans-discipline-language
	$(CONFORMITY) --check no-global-plans

headers-doctor:
	$(PYTHON) src/apothem/conformity/file_header_grep.py

headers-fix:
	$(INJECT) --mode fix-in-place .

ai-surfaces-doctor:
	$(CONFORMITY) --check copilot-instructions-presence
	$(CONFORMITY) --check multi-surface-coherence
	$(CONFORMITY) --check license-author-consistency

# bench_hooks.py with no --event measures every event hooks.json registers, on
# a real payload. bench_agents.py is not run here: an agent spawn needs a host
# harness and a model call, so it can only report NOT MEASURED (exit 3).
benchmarks:
	$(PYTHON) src/apothem/benchmarks/bench_validate_ecosystem.py
	$(PYTHON) src/apothem/benchmarks/bench_hooks.py
	$(PYTHON) src/apothem/benchmarks/bench_tests.py
	$(PYTHON) src/apothem/benchmarks/bench_install.py

# ----- release -------------------------------------------------------

# Release version is read from the single source of truth (pyproject.toml);
# override on demand with `make release VERSION=X.Y.Z`. Mirrors the CI
# release-notes extraction in .github/workflows/release.yml.
VERSION ?= $(shell sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)

release:
	$(PYTHON) scripts/release/extract_release_notes.py \
		--version "$(VERSION)" \
		--changelog CHANGELOG.md \
		--output release-notes.md

# ----- maintenance ---------------------------------------------------

clean:
	@find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .mypy_cache -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .ruff_cache -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .hypothesis -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -prune -exec rm -rf {} + 2>/dev/null || true
