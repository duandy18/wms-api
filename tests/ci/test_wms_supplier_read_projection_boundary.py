# tests/ci/test_wms_supplier_read_projection_boundary.py
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_OLD_SUPPLIER_READ_RE = re.compile(
    r"""
    \bFROM\s+suppliers\b
    |
    \bJOIN\s+suppliers\b
    |
    \bSELECT\b.*\bFROM\s+suppliers\b
    |
    \bINSERT\s+INTO\s+suppliers\b
    |
    \bUPDATE\s+suppliers\b
    |
    \bDELETE\s+FROM\s+suppliers\b
    |
    pg_get_serial_sequence\('suppliers'
    |
    from\s+app\.partners\.suppliers\.(models|repos)
    """,
    re.IGNORECASE | re.VERBOSE,
)

ALLOWED_PREFIXES = (
    "app/partners/suppliers/",
)

ALLOWED_FILES = {
    "tests/fixtures/base_seed.sql",
    "tests/ci/test_wms_supplier_read_projection_boundary.py",
}


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_non_owner_supplier_reads_use_wms_pms_supplier_projection() -> None:
    violations: list[str] = []

    for root_name in ("app", "tests", "scripts"):
        root = ROOT / root_name
        if not root.exists():
            continue

        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix not in {".py", ".sql"}:
                continue

            rel = _rel(path)
            if rel in ALLOWED_FILES:
                continue
            if any(rel.startswith(prefix) for prefix in ALLOWED_PREFIXES):
                continue
            if "__pycache__" in rel:
                continue

            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if FORBIDDEN_OLD_SUPPLIER_READ_RE.search(line):
                    violations.append(f"{rel}:{line_no}: {line.strip()}")

    assert violations == []


def test_supplier_export_read_service_uses_projection_table() -> None:
    text = (
        ROOT / "app/partners/export/suppliers/services/supplier_read_service.py"
    ).read_text(encoding="utf-8")

    assert "wms_pms_supplier_projection" in text
    assert "FROM suppliers" not in text
    assert "app.partners.suppliers.models" not in text
    assert "app.partners.suppliers.repos" not in text
