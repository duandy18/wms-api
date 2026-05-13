from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260513141432_pms_projection_pages_level2"
down_revision: str | Sequence[str] | None = "20260513130400_rehome_projection_pages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_PAGE_ROWS = (
    ("pms.item_projection", "商品投影", "pms", 2, 90),
    ("pms.supplier_projection", "供应商投影", "pms", 2, 91),
    ("pms.uom_projection", "包装单位投影", "pms", 2, 92),
    ("pms.sku_code_projection", "SKU 编码投影", "pms", 2, 93),
    ("pms.barcode_projection", "条码投影", "pms", 2, 94),
)

NEW_ROUTE_ROWS = (
    ("/pms/item-projection", "pms.item_projection", 90),
    ("/pms/supplier-projection", "pms.supplier_projection", 91),
    ("/pms/uom-projection", "pms.uom_projection", 92),
    ("/pms/sku-code-projection", "pms.sku_code_projection", 93),
    ("/pms/barcode-projection", "pms.barcode_projection", 94),
)

OLD_PAGE_ROWS = (
    ("pms.projections", "PMS 商品投影", "pms", 2, 90),
    ("pms.projections.items", "商品投影", "pms.projections", 3, 10),
    ("pms.projections.suppliers", "供应商投影", "pms.projections", 3, 20),
    ("pms.projections.uoms", "包装单位投影", "pms.projections", 3, 30),
    ("pms.projections.sku_codes", "SKU 编码投影", "pms.projections", 3, 40),
    ("pms.projections.barcodes", "条码投影", "pms.projections", 3, 50),
)

OLD_ROUTE_ROWS = (
    ("/pms/projections", "pms.projections", 90),
    ("/pms/projections/items", "pms.projections.items", 91),
    ("/pms/projections/suppliers", "pms.projections.suppliers", 92),
    ("/pms/projections/uoms", "pms.projections.uoms", 93),
    ("/pms/projections/sku-codes", "pms.projections.sku_codes", 94),
    ("/pms/projections/barcodes", "pms.projections.barcodes", 95),
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
              'pms',
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
              is_active = EXCLUDED.is_active
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
        DELETE FROM page_route_prefixes
        WHERE route_prefix IN (
          '/pms/projections',
          '/pms/projections/items',
          '/pms/projections/suppliers',
          '/pms/projections/uoms',
          '/pms/projections/sku-codes',
          '/pms/projections/barcodes'
        )
           OR page_code = 'pms.projections'
           OR page_code LIKE 'pms.projections.%'
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
          'pms.projections.barcodes'
        )
        """
    )
    op.execute("DELETE FROM page_registry WHERE code = 'pms.projections'")

    for code, name, parent_code, level, sort_order in NEW_PAGE_ROWS:
        _insert_page(code, name, parent_code, level, sort_order)

    for route_prefix, page_code, sort_order in NEW_ROUTE_ROWS:
        _insert_route(route_prefix, page_code, sort_order)


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM page_route_prefixes
        WHERE route_prefix IN (
          '/pms/item-projection',
          '/pms/supplier-projection',
          '/pms/uom-projection',
          '/pms/sku-code-projection',
          '/pms/barcode-projection'
        )
           OR page_code IN (
          'pms.item_projection',
          'pms.supplier_projection',
          'pms.uom_projection',
          'pms.sku_code_projection',
          'pms.barcode_projection'
        )
        """
    )

    op.execute(
        """
        DELETE FROM page_registry
        WHERE code IN (
          'pms.item_projection',
          'pms.supplier_projection',
          'pms.uom_projection',
          'pms.sku_code_projection',
          'pms.barcode_projection'
        )
        """
    )

    for code, name, parent_code, level, sort_order in OLD_PAGE_ROWS:
        _insert_page(code, name, parent_code, level, sort_order)

    for route_prefix, page_code, sort_order in OLD_ROUTE_ROWS:
        _insert_route(route_prefix, page_code, sort_order)
