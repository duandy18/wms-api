"""retire WMS procurement management navigation

Revision ID: 20260515123000_retire_wms_procurement_nav
Revises: 20260513133000_source_line_id
Create Date: 2026-05-15 12:30:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "20260515123000_retire_wms_procurement_nav"
down_revision: str | Sequence[str] | None = "20260513133000_source_line_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PROCUREMENT_PAGE_CODES = (
    "procurement.purchase_order_detail",
    "procurement.purchase_orders_new",
    "procurement.purchase_reports",
    "procurement.purchase_orders",
    "procurement",
)

PROCUREMENT_ROUTE_PREFIX_SQL = (
    "'/purchase-orders'",
    "'/purchase-orders/new'",
    "'/purchase-orders/' || chr(58) || 'poId'",
    "'/purchase-reports'",
)


def upgrade() -> None:
    """Remove WMS-side procurement management navigation.

    Boundary:
    - Procurement purchase order owner has moved to procurement-api/procurement-web.
    - WMS keeps inbound execution pages:
      /inbound-receipts/purchase and /receiving/purchase.
    - This migration only changes navigation registry data.
    - It does not unmount legacy WMS API routers.
    - It does not drop local historical procurement tables.
    """

    # 1) Delete procurement management route prefixes only.
    # Do not touch:
    # - /inbound-receipts/purchase
    # - /receiving/purchase
    # - /finance/purchase-costs
    op.execute(
        """
        DELETE FROM page_route_prefixes
        WHERE page_code = 'procurement'
           OR page_code LIKE 'procurement.%'
           OR route_prefix IN (
             '/purchase-orders',
             '/purchase-orders/new',
             '/purchase-orders/' || chr(58) || 'poId',
             '/purchase-reports'
           )
        """
    )

    # 2) Delete procurement child pages first because page_registry parent FK is restrictive.
    op.execute(
        """
        DELETE FROM page_registry
        WHERE code IN (
          'procurement.purchase_order_detail',
          'procurement.purchase_orders_new',
          'procurement.purchase_reports',
          'procurement.purchase_orders'
        )
        """
    )

    # 3) Delete procurement root page.
    op.execute(
        """
        DELETE FROM page_registry
        WHERE code = 'procurement'
        """
    )

    # 4) Remove now-unreferenced procurement page permissions.
    # user_permissions.permission_id has ON DELETE CASCADE.
    op.execute(
        """
        DELETE FROM permissions
        WHERE name IN (
          'page.procurement.read',
          'page.procurement.write'
        )
          AND NOT EXISTS (
            SELECT 1
            FROM page_registry pr
            WHERE pr.read_permission_id = permissions.id
               OR pr.write_permission_id = permissions.id
          )
        """
    )


def downgrade() -> None:
    """Restore WMS-side procurement management navigation.

    This is only a navigation rollback. It does not recreate or change
    purchase order tables or routers.
    """

    op.execute(
        """
        INSERT INTO permissions (name)
        VALUES
          ('page.procurement.read'),
          ('page.procurement.write')
        ON CONFLICT (name) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO page_registry (
          code,
          name,
          parent_code,
          level,
          domain_code,
          show_in_topbar,
          show_in_sidebar,
          inherit_permissions,
          read_permission_id,
          write_permission_id,
          sort_order,
          is_active
        )
        VALUES
          (
            'procurement',
            '采购管理',
            NULL,
            1,
            'procurement',
            TRUE,
            FALSE,
            FALSE,
            (SELECT id FROM permissions WHERE name = 'page.procurement.read'),
            (SELECT id FROM permissions WHERE name = 'page.procurement.write'),
            25,
            TRUE
          ),
          (
            'procurement.purchase_orders',
            '采购列表',
            'procurement',
            2,
            'procurement',
            FALSE,
            TRUE,
            TRUE,
            NULL,
            NULL,
            10,
            TRUE
          ),
          (
            'procurement.purchase_orders_new',
            '新建采购单',
            'procurement',
            2,
            'procurement',
            FALSE,
            TRUE,
            TRUE,
            NULL,
            NULL,
            20,
            TRUE
          ),
          (
            'procurement.purchase_order_detail',
            '查看采购单',
            'procurement',
            2,
            'procurement',
            FALSE,
            FALSE,
            TRUE,
            NULL,
            NULL,
            30,
            TRUE
          ),
          (
            'procurement.purchase_reports',
            '采购报表',
            'procurement',
            2,
            'procurement',
            FALSE,
            TRUE,
            TRUE,
            NULL,
            NULL,
            40,
            TRUE
          )
        ON CONFLICT (code) DO UPDATE
        SET
          name = EXCLUDED.name,
          parent_code = EXCLUDED.parent_code,
          level = EXCLUDED.level,
          domain_code = EXCLUDED.domain_code,
          show_in_topbar = EXCLUDED.show_in_topbar,
          show_in_sidebar = EXCLUDED.show_in_sidebar,
          inherit_permissions = EXCLUDED.inherit_permissions,
          read_permission_id = EXCLUDED.read_permission_id,
          write_permission_id = EXCLUDED.write_permission_id,
          sort_order = EXCLUDED.sort_order,
          is_active = EXCLUDED.is_active
        """
    )

    op.execute(
        """
        INSERT INTO page_route_prefixes (
          page_code,
          route_prefix,
          sort_order,
          is_active
        )
        VALUES
          ('procurement.purchase_orders', '/purchase-orders', 20, TRUE),
          ('procurement.purchase_orders_new', '/purchase-orders/new', 21, TRUE),
          ('procurement.purchase_order_detail', '/purchase-orders/' || chr(58) || 'poId', 22, TRUE),
          ('procurement.purchase_reports', '/purchase-reports', 40, TRUE)
        ON CONFLICT (route_prefix) DO UPDATE
        SET
          page_code = EXCLUDED.page_code,
          sort_order = EXCLUDED.sort_order,
          is_active = EXCLUDED.is_active
        """
    )
