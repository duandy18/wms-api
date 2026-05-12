"""retire_wms_legacy_supplier_tables

Revision ID: 2b7e9d6a4c1f
Revises: 9f2a4c7d1e8b
Create Date: 2026-05-12 11:20:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2b7e9d6a4c1f"
down_revision: Union[str, Sequence[str], None] = "9f2a4c7d1e8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # WMS supplier owner tables are retired.
    # PMS owns suppliers/supplier_contacts.
    # WMS keeps only wms_pms_supplier_projection for current reads and snapshots for history.
    op.drop_table("supplier_contacts")

    op.execute("DROP TRIGGER IF EXISTS trg_suppliers_code_immutable ON suppliers")
    op.drop_table("suppliers")
    op.execute("DROP FUNCTION IF EXISTS trg_forbid_update_suppliers_code()")


def downgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id", name="suppliers_pkey"),
        sa.UniqueConstraint("code", name="uq_suppliers_code"),
        sa.UniqueConstraint("name", name="uq_suppliers_name"),
        sa.CheckConstraint("btrim(code) <> ''", name="ck_suppliers_code_nonblank"),
        sa.CheckConstraint("code = btrim(code)", name="ck_suppliers_code_trimmed"),
        sa.CheckConstraint("code = upper(code)", name="ck_suppliers_code_upper"),
        sa.CheckConstraint("btrim(name) <> ''", name="ck_suppliers_name_nonblank"),
        sa.CheckConstraint("name = btrim(name)", name="ck_suppliers_name_trimmed"),
    )
    op.create_index("ix_suppliers_active", "suppliers", ["active"])
    op.create_index("ix_suppliers_name", "suppliers", ["name"])

    op.create_table(
        "supplier_contacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("wechat", sa.String(length=64), nullable=True),
        sa.Column("role", sa.String(length=32), server_default=sa.text("'other'"), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="supplier_contacts_pkey"),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name="supplier_contacts_supplier_id_fkey",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_supplier_contacts_supplier_id",
        "supplier_contacts",
        ["supplier_id"],
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_contacts_primary_per_supplier
        ON supplier_contacts (supplier_id)
        WHERE is_primary = true
        """
    )
