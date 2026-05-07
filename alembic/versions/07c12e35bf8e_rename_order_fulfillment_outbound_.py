"""rename order fulfillment outbound timestamps

Revision ID: 07c12e35bf8e
Revises: 'f24a651ec4a9'
Create Date: 2026-05-07

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "07c12e35bf8e"
down_revision: str | Sequence[str] | None = 'f24a651ec4a9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rename WMS outbound timestamp columns away from shipment wording."""

    op.execute(
        """
        ALTER TABLE order_fulfillment
        DROP CONSTRAINT IF EXISTS ck_order_fulfillment_ship_time_order
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
              FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name = 'order_fulfillment'
               AND column_name = 'ship_committed_at'
          )
          AND NOT EXISTS (
            SELECT 1
              FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name = 'order_fulfillment'
               AND column_name = 'outbound_committed_at'
          )
          THEN
            ALTER TABLE order_fulfillment
            RENAME COLUMN ship_committed_at TO outbound_committed_at;
          END IF;

          IF EXISTS (
            SELECT 1
              FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name = 'order_fulfillment'
               AND column_name = 'shipped_at'
          )
          AND NOT EXISTS (
            SELECT 1
              FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name = 'order_fulfillment'
               AND column_name = 'outbound_completed_at'
          )
          THEN
            ALTER TABLE order_fulfillment
            RENAME COLUMN shipped_at TO outbound_completed_at;
          END IF;
        END $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
              FROM pg_constraint
             WHERE conname = 'ck_order_fulfillment_outbound_time_order'
          )
          THEN
            ALTER TABLE order_fulfillment
            ADD CONSTRAINT ck_order_fulfillment_outbound_time_order
            CHECK (
              outbound_completed_at IS NULL
              OR outbound_committed_at IS NOT NULL
            );
          END IF;
        END $$;
        """
    )

    op.execute(
        """
        COMMENT ON COLUMN order_fulfillment.outbound_committed_at
        IS 'WMS 出库提交/裁决链路进入时间；非物流发货时间'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN order_fulfillment.outbound_completed_at
        IS 'WMS 库存出库完成时间；非物流单号/面单完成时间'
        """
    )


def downgrade() -> None:
    """Restore legacy shipment-worded timestamp column names."""

    op.execute(
        """
        ALTER TABLE order_fulfillment
        DROP CONSTRAINT IF EXISTS ck_order_fulfillment_outbound_time_order
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
              FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name = 'order_fulfillment'
               AND column_name = 'outbound_committed_at'
          )
          AND NOT EXISTS (
            SELECT 1
              FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name = 'order_fulfillment'
               AND column_name = 'ship_committed_at'
          )
          THEN
            ALTER TABLE order_fulfillment
            RENAME COLUMN outbound_committed_at TO ship_committed_at;
          END IF;

          IF EXISTS (
            SELECT 1
              FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name = 'order_fulfillment'
               AND column_name = 'outbound_completed_at'
          )
          AND NOT EXISTS (
            SELECT 1
              FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name = 'order_fulfillment'
               AND column_name = 'shipped_at'
          )
          THEN
            ALTER TABLE order_fulfillment
            RENAME COLUMN outbound_completed_at TO shipped_at;
          END IF;
        END $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
              FROM pg_constraint
             WHERE conname = 'ck_order_fulfillment_ship_time_order'
          )
          THEN
            ALTER TABLE order_fulfillment
            ADD CONSTRAINT ck_order_fulfillment_ship_time_order
            CHECK (
              shipped_at IS NULL
              OR ship_committed_at IS NOT NULL
            );
          END IF;
        END $$;
        """
    )

    op.execute(
        """
        COMMENT ON COLUMN order_fulfillment.ship_committed_at
        IS '进入出库裁决链路锚点（事实字段）'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN order_fulfillment.shipped_at
        IS '出库完成时间（事实字段）'
        """
    )
