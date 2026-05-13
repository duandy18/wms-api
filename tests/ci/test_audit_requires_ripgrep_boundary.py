# tests/ci/test_audit_requires_ripgrep_boundary.py
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_backend_ci_installs_ripgrep_for_audit_targets() -> None:
    text = (ROOT / ".github/workflows/backend-ci.yml").read_text(encoding="utf-8")

    assert "Install system audit tools" in text
    assert "apt-get install -y ripgrep" in text
    assert "rg --version" in text


def test_audit_targets_fail_fast_when_rg_is_missing() -> None:
    text = (ROOT / "scripts/make/audit.mk").read_text(encoding="utf-8")

    assert ".PHONY: audit-require-rg" in text
    assert "command -v rg" in text
    assert "exit 127" in text

    assert "audit-no-legacy-stock-sql: audit-require-rg" in text
    assert "audit-no-legacy-pricing-terms: audit-require-rg" in text
    assert "audit-no-implicit-warehouse-id: audit-require-rg" in text
