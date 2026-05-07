"""add manual outbound receiver fields

Revision ID: 9c1f2a3b4d5e
Revises: 6f2c7d4a9e18
Create Date: 2026-05-08 00:40:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "9c1f2a3b4d5e"
down_revision: Union[str, Sequence[str], None] = "6f2c7d4a9e18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add receiver address fields to manual outbound docs."""

    op.execute(
        """
        ALTER TABLE manual_outbound_docs
          ADD COLUMN IF NOT EXISTS receiver_phone varchar(64),
          ADD COLUMN IF NOT EXISTS receiver_province varchar(64),
          ADD COLUMN IF NOT EXISTS receiver_city varchar(64),
          ADD COLUMN IF NOT EXISTS receiver_district varchar(64),
          ADD COLUMN IF NOT EXISTS receiver_address varchar(255),
          ADD COLUMN IF NOT EXISTS receiver_postcode varchar(32)
        """
    )

    op.execute(
        """
        COMMENT ON COLUMN manual_outbound_docs.receiver_phone IS
          '手工出库收件电话，用于 WMS -> Logistics 交接快照'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN manual_outbound_docs.receiver_province IS
          '手工出库收件省份，用于 WMS -> Logistics 交接快照'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN manual_outbound_docs.receiver_city IS
          '手工出库收件城市，用于 WMS -> Logistics 交接快照'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN manual_outbound_docs.receiver_district IS
          '手工出库收件区县，用于 WMS -> Logistics 交接快照'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN manual_outbound_docs.receiver_address IS
          '手工出库收件详细地址，用于 WMS -> Logistics 交接快照'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN manual_outbound_docs.receiver_postcode IS
          '手工出库收件邮编，用于 WMS -> Logistics 交接快照'
        """
    )


def downgrade() -> None:
    """Drop manual outbound receiver address fields."""

    op.execute(
        """
        ALTER TABLE manual_outbound_docs
          DROP COLUMN IF EXISTS receiver_postcode,
          DROP COLUMN IF EXISTS receiver_address,
          DROP COLUMN IF EXISTS receiver_district,
          DROP COLUMN IF EXISTS receiver_city,
          DROP COLUMN IF EXISTS receiver_province,
          DROP COLUMN IF EXISTS receiver_phone
        """
    )
