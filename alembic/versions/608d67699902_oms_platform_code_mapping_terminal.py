"""oms_platform_code_mapping_terminal

Revision ID: 608d67699902
Revises: e1340008003d
Create Date: 2026-05-05

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "608d67699902"
down_revision: Union[str, Sequence[str], None] = "e1340008003d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS platform_code_fsku_mappings (
          id SERIAL PRIMARY KEY,
          platform VARCHAR(32) NOT NULL,
          store_code TEXT NOT NULL,
          identity_kind VARCHAR(32) NOT NULL,
          identity_value VARCHAR(256) NOT NULL,
          fsku_id INTEGER NOT NULL REFERENCES oms_fskus(id) ON DELETE RESTRICT,
          reason TEXT,
          created_at TIMESTAMPTZ NOT NULL,
          updated_at TIMESTAMPTZ NOT NULL,
          CONSTRAINT ck_platform_code_fsku_mappings_identity_kind
            CHECK (identity_kind IN ('merchant_code', 'platform_sku_id', 'platform_item_sku')),
          CONSTRAINT ck_platform_code_fsku_mappings_identity_value_non_empty
            CHECK (length(trim(identity_value)) > 0),
          CONSTRAINT ux_platform_code_fsku_mappings_unique
            UNIQUE (platform, store_code, identity_kind, identity_value)
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_platform_code_fsku_mappings_fsku_id
        ON platform_code_fsku_mappings(fsku_id)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_platform_code_fsku_mappings_lookup
        ON platform_code_fsku_mappings(platform, store_code, identity_kind, identity_value)
        """
    )

    op.execute(
        """
        INSERT INTO platform_code_fsku_mappings (
          platform,
          store_code,
          identity_kind,
          identity_value,
          fsku_id,
          reason,
          created_at,
          updated_at
        )
        SELECT
          platform,
          store_code,
          'merchant_code',
          merchant_code,
          fsku_id,
          reason,
          created_at,
          updated_at
        FROM merchant_code_fsku_bindings
        ON CONFLICT (platform, store_code, identity_kind, identity_value)
        DO UPDATE SET
          fsku_id = EXCLUDED.fsku_id,
          reason = EXCLUDED.reason,
          updated_at = EXCLUDED.updated_at
        """
    )

    op.execute("DROP TABLE IF EXISTS merchant_code_fsku_bindings")
    op.execute("DROP TABLE IF EXISTS oms_order_sku_resolution_components")
    op.execute("DROP TABLE IF EXISTS oms_order_sku_resolution_decisions")


def downgrade() -> None:
    """Downgrade schema."""

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS merchant_code_fsku_bindings (
          id SERIAL PRIMARY KEY,
          platform VARCHAR(32) NOT NULL,
          store_code TEXT NOT NULL,
          merchant_code VARCHAR(128) NOT NULL,
          fsku_id INTEGER NOT NULL REFERENCES oms_fskus(id) ON DELETE RESTRICT,
          reason TEXT,
          created_at TIMESTAMPTZ NOT NULL,
          updated_at TIMESTAMPTZ NOT NULL,
          CONSTRAINT ux_mc_fsku_bindings_store_unique
            UNIQUE (platform, store_code, merchant_code)
        )
        """
    )

    op.execute(
        """
        INSERT INTO merchant_code_fsku_bindings (
          platform,
          store_code,
          merchant_code,
          fsku_id,
          reason,
          created_at,
          updated_at
        )
        SELECT
          platform,
          store_code,
          identity_value,
          fsku_id,
          reason,
          created_at,
          updated_at
        FROM platform_code_fsku_mappings
        WHERE identity_kind = 'merchant_code'
        ON CONFLICT (platform, store_code, merchant_code)
        DO UPDATE SET
          fsku_id = EXCLUDED.fsku_id,
          reason = EXCLUDED.reason,
          updated_at = EXCLUDED.updated_at
        """
    )

    op.execute("DROP TABLE IF EXISTS platform_code_fsku_mappings")
