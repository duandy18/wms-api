"""retire_wms_residual_pms_owner_tables

Revision ID: 3c6f2a9b8d10
Revises: 2b7e9d6a4c1f
Create Date: 2026-05-12 11:40:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "3c6f2a9b8d10"
down_revision: Union[str, Sequence[str], None] = "2b7e9d6a4c1f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PMS owner tables are retired from WMS DB.
    # PMS owner runtime and owner DB live in pms-api.
    # WMS keeps only wms_pms_*_projection tables as local read indexes.
    #
    # Drop order follows FK dependency order inside the legacy PMS owner cluster.
    op.drop_table("item_barcodes")
    op.drop_table("item_sku_codes")
    op.drop_table("item_attribute_values")
    op.drop_table("sku_code_template_segments")
    op.drop_table("item_uoms")
    op.drop_table("items")
    op.drop_table("item_attribute_options")
    op.drop_table("item_attribute_defs")
    op.drop_table("sku_code_templates")
    op.drop_table("pms_brands")
    op.drop_table("pms_business_categories")

    # Do not drop expiry_policy / lot_source_policy enum types here.
    # They are still used by WMS lot snapshot columns.


def downgrade() -> None:
    raise RuntimeError(
        "WMS residual PMS owner tables are retired. "
        "PMS owner data must be restored from pms-api / PMS DB, not from wms-api downgrade."
    )
