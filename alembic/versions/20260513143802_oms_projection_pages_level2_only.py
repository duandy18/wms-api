from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260513143802_oms_projection_pages_level2_only"
down_revision: str | Sequence[str] | None = "20260513141432_pms_projection_pages_level2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_PAGE_ROWS = (
    ("oms.order_projection", "订单投影", "oms", 2, 10),
    ("oms.line_projection", "订单行投影", "oms", 2, 20),
    ("oms.component_projection", "履约组件投影", "oms", 2, 30),
)

NEW_ROUTE_ROWS = (
    ("/oms", "oms.order_projection", 9),
    ("/oms/order-projection", "oms.order_projection", 10),
    ("/oms/line-projection", "oms.line_projection", 20),
    ("/oms/component-projection", "oms.component_projection", 30),
)

OLD_RESTORE_PAGE_ROWS = (
    ("oms.fsku_rules", "FSKU 组合规则", "oms", 2, 10),
    ("oms.pdd", "拼多多", "oms", 2, 20),
    ("oms.pdd.platform_order_mirror", "平台订单镜像", "oms.pdd", 3, 10),
    ("oms.pdd.fsku_mapping", "平台编码映射", "oms.pdd", 3, 20),
    ("oms.taobao", "淘宝", "oms", 2, 30),
    ("oms.taobao.platform_order_mirror", "平台订单镜像", "oms.taobao", 3, 10),
    ("oms.taobao.fsku_mapping", "平台编码映射", "oms.taobao", 3, 20),
    ("oms.jd", "京东", "oms", 2, 40),
    ("oms.jd.platform_order_mirror", "平台订单镜像", "oms.jd", 3, 10),
    ("oms.jd.fsku_mapping", "平台编码映射", "oms.jd", 3, 20),
    ("oms.fulfillment_projection", "履约投影", "oms", 2, 90),
    ("oms.fulfillment_projection.orders", "订单投影", "oms.fulfillment_projection", 3, 10),
    ("oms.fulfillment_projection.lines", "订单行投影", "oms.fulfillment_projection", 3, 20),
    ("oms.fulfillment_projection.components", "履约组件投影", "oms.fulfillment_projection", 3, 30),
)

OLD_RESTORE_ROUTE_ROWS = (
    ("/oms", "oms.pdd.platform_order_mirror", 9),
    ("/oms/fskus", "oms.fsku_rules", 10),
    ("/oms/pdd/platform-order-mirror", "oms.pdd.platform_order_mirror", 20),
    ("/oms/pdd/fsku-mapping", "oms.pdd.fsku_mapping", 30),
    ("/oms/taobao/platform-order-mirror", "oms.taobao.platform_order_mirror", 40),
    ("/oms/taobao/fsku-mapping", "oms.taobao.fsku_mapping", 50),
    ("/oms/jd/platform-order-mirror", "oms.jd.platform_order_mirror", 60),
    ("/oms/jd/fsku-mapping", "oms.jd.fsku_mapping", 70),
    ("/oms/fulfillment-projection", "oms.fulfillment_projection", 90),
    ("/oms/fulfillment-projection/orders", "oms.fulfillment_projection.orders", 91),
    ("/oms/fulfillment-projection/lines", "oms.fulfillment_projection.lines", 92),
    ("/oms/fulfillment-projection/components", "oms.fulfillment_projection.components", 93),
)


def _insert_page(code: str, name: str, parent_code: str, level: int, sort_order: int) -> None:
    op.get_bind().execute(
        sa.text(
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
            VALUES (
              :code,
              :name,
              :parent_code,
              :level,
              'oms',
              FALSE,
              TRUE,
              TRUE,
              NULL,
              NULL,
              :sort_order,
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
              is_active = TRUE
            """
        ),
        {
            "code": code,
            "name": name,
            "parent_code": parent_code,
            "level": level,
            "sort_order": sort_order,
        },
    )


def _insert_route(route_prefix: str, page_code: str, sort_order: int) -> None:
    op.get_bind().execute(
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
        ),
        {
            "route_prefix": route_prefix,
            "page_code": page_code,
            "sort_order": sort_order,
        },
    )


def upgrade() -> None:
    op.execute(
        """
        UPDATE page_registry
           SET name = '订单管理',
               parent_code = NULL,
               level = 1,
               domain_code = 'oms',
               show_in_topbar = TRUE,
               show_in_sidebar = FALSE,
               inherit_permissions = FALSE,
               read_permission_id = (SELECT id FROM permissions WHERE name = 'page.oms.read'),
               write_permission_id = (SELECT id FROM permissions WHERE name = 'page.oms.write'),
               sort_order = 30,
               is_active = TRUE
         WHERE code = 'oms'
        """
    )

    op.execute(
        """
        DELETE FROM page_route_prefixes
        WHERE route_prefix = '/oms'
           OR route_prefix LIKE '/oms/%'
           OR page_code = 'oms'
           OR page_code LIKE 'oms.%'
        """
    )

    op.execute("DELETE FROM page_registry WHERE code LIKE 'oms.%.%'")
    op.execute("DELETE FROM page_registry WHERE code LIKE 'oms.%'")

    for code, name, parent_code, level, sort_order in NEW_PAGE_ROWS:
        _insert_page(code, name, parent_code, level, sort_order)

    for route_prefix, page_code, sort_order in NEW_ROUTE_ROWS:
        _insert_route(route_prefix, page_code, sort_order)


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM page_route_prefixes
        WHERE route_prefix IN (
          '/oms',
          '/oms/order-projection',
          '/oms/line-projection',
          '/oms/component-projection'
        )
           OR page_code IN (
          'oms.order_projection',
          'oms.line_projection',
          'oms.component_projection'
        )
        """
    )

    op.execute(
        """
        DELETE FROM page_registry
        WHERE code IN (
          'oms.order_projection',
          'oms.line_projection',
          'oms.component_projection'
        )
        """
    )

    for code, name, parent_code, level, sort_order in OLD_RESTORE_PAGE_ROWS:
        _insert_page(code, name, parent_code, level, sort_order)

    for route_prefix, page_code, sort_order in OLD_RESTORE_ROUTE_ROWS:
        _insert_route(route_prefix, page_code, sort_order)
