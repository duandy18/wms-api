"""oms_fsku_retire_guard_use_platform_code_mapping

Revision ID: 3fc161fb9104
Revises: 608d67699902
Create Date: 2026-05-05

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "3fc161fb9104"
down_revision: Union[str, Sequence[str], None] = "608d67699902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.ck_oms_fskus_retire_not_referenced()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $func$
        BEGIN
          IF NEW.status = 'retired'
             AND OLD.status IS DISTINCT FROM NEW.status
             AND EXISTS (
               SELECT 1
                 FROM platform_code_fsku_mappings m
                WHERE m.fsku_id = NEW.id
             )
          THEN
            RAISE EXCEPTION 'FSKU 已被平台编码映射引用，请先解除映射后再归档';
          END IF;

          RETURN NEW;
        END;
        $func$;
        """
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.ck_oms_fskus_retire_not_referenced()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $func$
        BEGIN
          IF NEW.status = 'retired'
             AND OLD.status IS DISTINCT FROM NEW.status
             AND EXISTS (
               SELECT 1
                 FROM merchant_code_fsku_bindings b
                WHERE b.fsku_id = NEW.id
             )
          THEN
            RAISE EXCEPTION 'FSKU 已被 merchant_code 绑定引用，请先解绑后再归档';
          END IF;

          RETURN NEW;
        END;
        $func$;
        """
    )
