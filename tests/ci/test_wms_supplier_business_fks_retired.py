# tests/ci/test_wms_supplier_business_fks_retired.py
from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_APP_SUPPLIER_FK_RE = re.compile(
    r"""
    ForeignKey\(["']suppliers\.id["']
    |
    fk_items_supplier
    |
    fk_purchase_orders_supplier_id
    |
    fk_inbound_receipts_supplier
    |
    fk_wms_inbound_operations_supplier
    |
    FK\s*→\s*suppliers\.id
    |
    通常来自\s+suppliers\.name
    """,
    re.VERBOSE,
)

ALLOWED_PREFIXES = (
    "app/partners/suppliers/",
)


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_non_owner_models_do_not_declare_supplier_business_fks() -> None:
    violations: list[str] = []

    for path in sorted((ROOT / "app").rglob("*.py")):
        rel = _rel(path)
        if any(rel.startswith(prefix) for prefix in ALLOWED_PREFIXES):
            continue
        if "__pycache__" in rel:
            continue

        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if FORBIDDEN_APP_SUPPLIER_FK_RE.search(line):
                violations.append(f"{rel}:{line_no}: {line.strip()}")

    assert violations == []


@pytest.mark.asyncio
async def test_supplier_business_fk_constraints_are_retired_in_database(
    session: AsyncSession,
) -> None:
    rows = (
        await session.execute(
            text(
                """
                SELECT
                  c.conname AS constraint_name,
                  c.conrelid::regclass::text AS owner_table,
                  c.confrelid::regclass::text AS referenced_table
                FROM pg_constraint c
                WHERE c.contype = 'f'
                  AND c.confrelid = 'suppliers'::regclass
                ORDER BY owner_table, constraint_name
                """
            )
        )
    ).mappings().all()

    pairs = {(str(row["owner_table"]), str(row["constraint_name"])) for row in rows}

    assert ("items", "fk_items_supplier") not in pairs
    assert ("purchase_orders", "fk_purchase_orders_supplier_id") not in pairs
    assert ("inbound_receipts", "fk_inbound_receipts_supplier") not in pairs
    assert ("wms_inbound_operations", "fk_wms_inbound_operations_supplier") not in pairs

    assert pairs == {("supplier_contacts", "supplier_contacts_supplier_id_fkey")}
