"""retire_wms_pms_projection_tables

Revision ID: 9f3d2c8a7b41
Revises: d4f8c2b1a790
Create Date: 2026-05-09 22:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "9f3d2c8a7b41"
down_revision: Union[str, Sequence[str], None] = "d4f8c2b1a790"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Retire WMS PMS projection tables."""

    op.execute("DROP TABLE IF EXISTS wms_pms_item_barcode_projection CASCADE")
    op.execute("DROP TABLE IF EXISTS wms_pms_item_sku_code_projection CASCADE")
    op.execute("DROP TABLE IF EXISTS wms_pms_item_policy_projection CASCADE")
    op.execute("DROP TABLE IF EXISTS wms_pms_item_uom_projection CASCADE")
    op.execute("DROP TABLE IF EXISTS wms_pms_item_projection CASCADE")
    op.execute("DROP TABLE IF EXISTS wms_pms_projection_sync_cursors CASCADE")


def downgrade() -> None:
    """This retirement migration is intentionally one-way."""

    raise RuntimeError("retire_wms_pms_projection_tables is intentionally irreversible")
