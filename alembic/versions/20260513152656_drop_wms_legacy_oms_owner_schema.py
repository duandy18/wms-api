from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "20260513152656_drop_wms_legacy_oms_owner_schema"
down_revision: str | Sequence[str] | None = "20260513143802_oms_projection_pages_level2_only"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


LEGACY_OMS_OWNER_TABLES = (
    "platform_order_manual_decisions",
    "platform_order_addresses",
    "platform_order_lines",
    "platform_code_fsku_mappings",
    "oms_pdd_order_mirror_lines",
    "oms_taobao_order_mirror_lines",
    "oms_jd_order_mirror_lines",
    "oms_pdd_order_mirrors",
    "oms_taobao_order_mirrors",
    "oms_jd_order_mirrors",
    "oms_fsku_components",
    "oms_fskus",
)


def upgrade() -> None:
    # Terminal cleanup:
    # WMS no longer owns OMS runtime/owner tables. WMS keeps only
    # wms_oms_fulfillment_* projection tables sourced from oms-api read-v1.
    op.execute(
        """
        DO $legacy_oms_drop$
        BEGIN
          IF to_regclass('public.oms_fskus') IS NOT NULL THEN
            DROP TRIGGER IF EXISTS trg_ck_oms_fskus_retire_not_referenced
            ON public.oms_fskus;
          END IF;
        END
        $legacy_oms_drop$;
        """
    )
    op.execute("DROP FUNCTION IF EXISTS public.ck_oms_fskus_retire_not_referenced()")

    op.execute("DROP TABLE IF EXISTS platform_order_manual_decisions")
    op.execute("DROP TABLE IF EXISTS platform_order_addresses")
    op.execute("DROP TABLE IF EXISTS platform_order_lines")

    op.execute("DROP TABLE IF EXISTS oms_pdd_order_mirror_lines")
    op.execute("DROP TABLE IF EXISTS oms_taobao_order_mirror_lines")
    op.execute("DROP TABLE IF EXISTS oms_jd_order_mirror_lines")

    op.execute("DROP TABLE IF EXISTS platform_code_fsku_mappings")
    op.execute("DROP TABLE IF EXISTS oms_fsku_components")

    op.execute("DROP TABLE IF EXISTS oms_pdd_order_mirrors")
    op.execute("DROP TABLE IF EXISTS oms_taobao_order_mirrors")
    op.execute("DROP TABLE IF EXISTS oms_jd_order_mirrors")

    op.execute("DROP TABLE IF EXISTS oms_fskus")


def downgrade() -> None:
    # Irreversible by design.
    # Old OMS owner/runtime schema has moved out of WMS ownership.
    pass
