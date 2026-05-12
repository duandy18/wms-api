# tests/ci/test_wms_supplier_business_fks_retired.py
from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_APP_SUPPLIER_OWNER_RE = re.compile(
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
    |
    app\.partners\.suppliers\.models
    |
    __tablename__\s*=\s*["']suppliers["']
    |
    __tablename__\s*=\s*["']supplier_contacts["']
    """,
    re.VERBOSE,
)


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_wms_legacy_supplier_owner_models_are_removed() -> None:
    assert not (ROOT / "app/partners/suppliers").exists()


def test_non_owner_models_do_not_declare_supplier_business_fks_or_owner_tables() -> None:
    violations: list[str] = []

    for path in sorted((ROOT / "app").rglob("*.py")):
        rel = _rel(path)
        if "__pycache__" in rel:
            continue

        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if FORBIDDEN_APP_SUPPLIER_OWNER_RE.search(line):
                violations.append(f"{rel}:{line_no}: {line.strip()}")

    assert violations == []


@pytest.mark.asyncio
async def test_legacy_supplier_owner_tables_are_retired_in_database(
    session: AsyncSession,
) -> None:
    rows = (
        await session.execute(
            text(
                """
                SELECT
                  to_regclass('public.suppliers') AS suppliers_table,
                  to_regclass('public.supplier_contacts') AS supplier_contacts_table
                """
            )
        )
    ).mappings().one()

    assert rows["suppliers_table"] is None
    assert rows["supplier_contacts_table"] is None


@pytest.mark.asyncio
async def test_no_fk_constraints_reference_legacy_supplier_owner_tables(
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
                  AND c.confrelid IN (
                    to_regclass('public.suppliers'),
                    to_regclass('public.supplier_contacts')
                  )
                ORDER BY owner_table, constraint_name
                """
            )
        )
    ).mappings().all()

    assert rows == []
