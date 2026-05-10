# tests/ci/test_pms_owner_boundary_contract.py
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

BOUNDARY_DIRS = (
    "app/wms",
    "app/oms",
    "app/procurement",
    "app/finance",
)

RAW_PMS_OWNER_TABLE_RE = re.compile(
    r"\bFROM\s+items\b"
    r"|\bJOIN\s+items\b"
    r"|\bLEFT\s+JOIN\s+items\b"
    r"|\bFROM\s+item_uoms\b"
    r"|\bJOIN\s+item_uoms\b"
    r"|\bLEFT\s+JOIN\s+item_uoms\b"
    r"|\bFROM\s+item_barcodes\b"
    r"|\bJOIN\s+item_barcodes\b"
    r"|\bFROM\s+item_sku_codes\b"
    r"|\bJOIN\s+item_sku_codes\b",
    re.IGNORECASE,
)

DIRECT_PMS_OWNER_IMPORT_RE = re.compile(
    r"from\s+app\.pms\.items\.models\b"
    r"|import\s+app\.pms\.items\.models\b"
    r"|from\s+app\.pms\.items\.repos\b"
    r"|from\s+app\.pms\.items\.services\b"
)


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for directory in BOUNDARY_DIRS:
        root = ROOT / directory
        if root.exists():
            files.extend(sorted(root.rglob("*.py")))
    return files


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_no_runtime_wms_pms_projection_package() -> None:
    assert not (ROOT / "app/wms/pms_projection").exists()


def test_no_raw_pms_owner_table_reads_outside_pms() -> None:
    violations: list[str] = []

    for path in _iter_python_files():
        rel = _rel(path)
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if RAW_PMS_OWNER_TABLE_RE.search(line):
                violations.append(f"{rel}:{line_no}: {line.strip()}")

    assert violations == []


def test_no_direct_pms_owner_imports_outside_pms() -> None:
    violations: list[str] = []

    for path in _iter_python_files():
        rel = _rel(path)
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not DIRECT_PMS_OWNER_IMPORT_RE.search(stripped):
                continue

            violations.append(f"{rel}:{line_no}: {stripped}")

    assert violations == []
