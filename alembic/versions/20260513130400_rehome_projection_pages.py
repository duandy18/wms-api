# alembic/versions/20260513130400_rehome_projection_pages.py
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260513130400_rehome_projection_pages"
down_revision: str | Sequence[str] | None = "20260513122748_wms_oms_fulfillment_projection"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PMS_PROJECTION_PAGE_ROWS = (
    ("pms", "商品管理", None, 1, "pms", True, False, False, "page.pms.read", "page.pms.write", 80, True),
    ("pms.projections", "PMS 商品投影", "pms", 2, "pms", False, True, True, None, None, 90, True),
    ("pms.projections.items", "商品投影", "pms.projections", 3, "pms", False, True, True, None, None, 10, True),
    ("pms.projections.suppliers", "供应商投影", "pms.projections", 3, "pms", False, True, True, None, None, 20, True),
    ("pms.projections.uoms", "包装单位投影", "pms.projections", 3, "pms", False, True, True, None, None, 30, True),
    ("pms.projections.sku_codes", "SKU 编码投影", "pms.projections", 3, "pms", False, True, True, None, None, 40, True),
    ("pms.projections.barcodes", "条码投影", "pms.projections", 3, "pms", False, True, True, None, None, 50, True),
)

PMS_PROJECTION_ROUTE_ROWS = (
    ("/pms/projections", "pms.projections", 90),
    ("/pms/projections/items", "pms.projections.items", 91),
    ("/pms/projections/suppliers", "pms.projections.suppliers", 92),
    ("/pms/projections/uoms", "pms.projections.uoms", 93),
    ("/pms/projections/sku-codes", "pms.projections.sku_codes", 94),
    ("/pms/projections/barcodes", "pms.projections.barcodes", 95),
)

OMS_PROJECTION_PAGE_ROWS = (
    ("oms.fulfillment_projection", "履约投影", "oms", 2, "oms", False, True, True, None, None, 90, True),
    ("oms.fulfillment_projection.orders", "订单投影", "oms.fulfillment_projection", 3, "oms", False, True, True, None, None, 10, True),
    ("oms.fulfillment_projection.lines", "订单行投影", "oms.fulfillment_projection", 3, "oms", False, True, True, None, None, 20, True),
    ("oms.fulfillment_projection.components", "履约组件投影", "oms.fulfillment_projection", 3, "oms", False, True, True, None, None, 30, True),
)

OMS_PROJECTION_ROUTE_ROWS = (
    ("/oms/fulfillment-projection", "oms.fulfillment_projection", 90),
    ("/oms/fulfillment-projection/orders", "oms.fulfillment_projection.orders", 91),
    ("/oms/fulfillment-projection/lines", "oms.fulfillment_projection.lines", 92),
    ("/oms/fulfillment-projection/components", "oms.fulfillment_projection.components", 93),
)

OLD_ADMIN_PMS_PAGE_CODES = (
    "admin.pms_integration.items",
    "admin.pms_integration.suppliers",
    "admin.pms_integration.uoms",
    "admin.pms_integration.sku_codes",
    "admin.pms_integration.barcodes",
    "admin.pms_integration",
)

OLD_ADMIN_PMS_ROUTE_PREFIXES = (
    "/admin/pms-integration",
    "/admin/pms-integration/items",
    "/admin/pms-integration/suppliers",
    "/admin/pms-integration/uoms",
    "/admin/pms-integration/sku-codes",
    "/admin/pms-integration/barcodes",
)


def _insert_page(
    *,
    code: str,
    name: str,
    parent_code: str | None,
    level: int,
    domain_code: str,
    show_in_topbar: bool,
    show_in_sidebar: bool,
    inherit_permissions: bool,
    read_permission: str | None,
    write_permission: str | None,
    sort_order: int,
    is_active: bool,
) -> None:
    params: dict[str, object] = {
        "code": code,
        "name": name,
        "parent_code": parent_code,
        "level": level,
        "domain_code": domain_code,
        "show_in_topbar": show_in_topbar,
        "show_in_sidebar": show_in_sidebar,
        "inherit_permissions": inherit_permissions,
        "sort_order": sort_order,
        "is_active": is_active,
    }

    if read_permission is None:
        read_permission_sql = "NULL"
    else:
        read_permission_sql = "(SELECT id FROM permissions WHERE name = :read_permission)"
        params["read_permission"] = read_permission

    if write_permission is None:
        write_permission_sql = "NULL"
    else:
        write_permission_sql = "(SELECT id FROM permissions WHERE name = :write_permission)"
        params["write_permission"] = write_permission

    op.get_bind().execute(
        sa.text(
            f"""
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
            VALUES (
              :code,
              :name,
              :parent_code,
              :level,
              :domain_code,
              :show_in_topbar,
              :show_in_sidebar,
              :inherit_permissions,
              {read_permission_sql},
              {write_permission_sql},
              :sort_order,
              :is_active
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
        ),
        params,
    )


def _insert_route(route_prefix: str, page_code: str, sort_order: int) -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO page_route_prefixes (
              route_prefix,
              page_code,
              sort_order,
              is_active
            )
            VALUES (
              :route_prefix,
              :page_code,
              :sort_order,
              TRUE
            )
            ON CONFLICT (route_prefix) DO UPDATE
            SET
              page_code = EXCLUDED.page_code,
              sort_order = EXCLUDED.sort_order,
              is_active = TRUE
            """
        ).bindparams(
            route_prefix=route_prefix,
            page_code=page_code,
            sort_order=sort_order,
        )
    )


def upgrade() -> None:
    # 商品投影从系统管理迁回商品管理。
    op.execute(
        """
        INSERT INTO permissions (name)
        VALUES ('page.pms.read'), ('page.pms.write')
        ON CONFLICT (name) DO NOTHING
        """
    )

    # 保证原来能看系统管理 PMS projection 的用户，迁移后仍能看商品管理下 projection。
    op.execute(
        """
        WITH mappings AS (
          SELECT 'page.admin.read' AS source_name, 'page.pms.read' AS target_name
          UNION ALL
          SELECT 'page.admin.write', 'page.pms.write'
        ),
        pairs AS (
          SELECT DISTINCT
            up.user_id,
            tp.id AS permission_id
          FROM mappings m
          JOIN permissions sp ON sp.name = m.source_name
          JOIN user_permissions up ON up.permission_id = sp.id
          JOIN permissions tp ON tp.name = m.target_name
        )
        INSERT INTO user_permissions (user_id, permission_id)
        SELECT user_id, permission_id
        FROM pairs
        ON CONFLICT (user_id, permission_id) DO NOTHING
        """
    )

    op.execute(
        """
        DELETE FROM page_route_prefixes
        WHERE route_prefix IN (
          '/admin/pms-integration',
          '/admin/pms-integration/items',
          '/admin/pms-integration/suppliers',
          '/admin/pms-integration/uoms',
          '/admin/pms-integration/sku-codes',
          '/admin/pms-integration/barcodes'
        )
           OR page_code = 'admin.pms_integration'
           OR page_code LIKE 'admin.pms_integration.%'
        """
    )

    op.execute(
        """
        DELETE FROM page_registry
        WHERE code IN (
          'admin.pms_integration.items',
          'admin.pms_integration.suppliers',
          'admin.pms_integration.uoms',
          'admin.pms_integration.sku_codes',
          'admin.pms_integration.barcodes'
        )
        """
    )
    op.execute("DELETE FROM page_registry WHERE code = 'admin.pms_integration'")

    for row in PMS_PROJECTION_PAGE_ROWS:
        _insert_page(
            code=row[0],
            name=row[1],
            parent_code=row[2],
            level=row[3],
            domain_code=row[4],
            show_in_topbar=row[5],
            show_in_sidebar=row[6],
            inherit_permissions=row[7],
            read_permission=row[8],
            write_permission=row[9],
            sort_order=row[10],
            is_active=row[11],
        )

    for route_prefix, page_code, sort_order in PMS_PROJECTION_ROUTE_ROWS:
        _insert_route(route_prefix, page_code, sort_order)

    # OMS fulfillment projection 归订单管理。
    for row in OMS_PROJECTION_PAGE_ROWS:
        _insert_page(
            code=row[0],
            name=row[1],
            parent_code=row[2],
            level=row[3],
            domain_code=row[4],
            show_in_topbar=row[5],
            show_in_sidebar=row[6],
            inherit_permissions=row[7],
            read_permission=row[8],
            write_permission=row[9],
            sort_order=row[10],
            is_active=row[11],
        )

    for route_prefix, page_code, sort_order in OMS_PROJECTION_ROUTE_ROWS:
        _insert_route(route_prefix, page_code, sort_order)


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM page_route_prefixes
        WHERE route_prefix IN (
          '/pms/projections',
          '/pms/projections/items',
          '/pms/projections/suppliers',
          '/pms/projections/uoms',
          '/pms/projections/sku-codes',
          '/pms/projections/barcodes',
          '/oms/fulfillment-projection',
          '/oms/fulfillment-projection/orders',
          '/oms/fulfillment-projection/lines',
          '/oms/fulfillment-projection/components'
        )
           OR page_code = 'pms.projections'
           OR page_code LIKE 'pms.projections.%'
           OR page_code = 'oms.fulfillment_projection'
           OR page_code LIKE 'oms.fulfillment_projection.%'
        """
    )

    op.execute(
        """
        DELETE FROM page_registry
        WHERE code IN (
          'pms.projections.items',
          'pms.projections.suppliers',
          'pms.projections.uoms',
          'pms.projections.sku_codes',
          'pms.projections.barcodes',
          'oms.fulfillment_projection.orders',
          'oms.fulfillment_projection.lines',
          'oms.fulfillment_projection.components'
        )
        """
    )
    op.execute(
        """
        DELETE FROM page_registry
        WHERE code IN (
          'pms.projections',
          'oms.fulfillment_projection'
        )
        """
    )
    op.execute(
        """
        DELETE FROM page_registry
        WHERE code = 'pms'
          AND NOT EXISTS (
            SELECT 1 FROM page_registry child WHERE child.parent_code = 'pms'
          )
        """
    )

    for code, name, parent_code, level, sort_order in (
        ("admin.pms_integration", "PMS 接入管理", "admin", 2, 20),
        ("admin.pms_integration.items", "商品投影", "admin.pms_integration", 3, 10),
        ("admin.pms_integration.suppliers", "供应商投影", "admin.pms_integration", 3, 20),
        ("admin.pms_integration.uoms", "包装单位投影", "admin.pms_integration", 3, 30),
        ("admin.pms_integration.sku_codes", "SKU 编码投影", "admin.pms_integration", 3, 40),
        ("admin.pms_integration.barcodes", "条码投影", "admin.pms_integration", 3, 50),
    ):
        _insert_page(
            code=code,
            name=name,
            parent_code=parent_code,
            level=level,
            domain_code="admin",
            show_in_topbar=False,
            show_in_sidebar=True,
            inherit_permissions=True,
            read_permission=None,
            write_permission=None,
            sort_order=sort_order,
            is_active=True,
        )

    for route_prefix, page_code, sort_order in (
        ("/admin/pms-integration", "admin.pms_integration", 20),
        ("/admin/pms-integration/items", "admin.pms_integration.items", 10),
        ("/admin/pms-integration/suppliers", "admin.pms_integration.suppliers", 20),
        ("/admin/pms-integration/uoms", "admin.pms_integration.uoms", 30),
        ("/admin/pms-integration/sku-codes", "admin.pms_integration.sku_codes", 40),
        ("/admin/pms-integration/barcodes", "admin.pms_integration.barcodes", 50),
    ):
        _insert_route(route_prefix, page_code, sort_order)
