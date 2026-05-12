"""add_wms_pms_projection_sync_admin_ops

Revision ID: 8a4f2d6c9b31
Revises: 3c6f2a9b8d10
Create Date: 2026-05-12 12:45:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8a4f2d6c9b31"
down_revision: Union[str, Sequence[str], None] = "3c6f2a9b8d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_PAGE_ROWS = (
    ("admin.pms_integration", "PMS 接入管理", "admin", 2, 20),
    ("admin.pms_integration.items", "商品投影", "admin.pms_integration", 3, 10),
    ("admin.pms_integration.suppliers", "供应商投影", "admin.pms_integration", 3, 20),
    ("admin.pms_integration.uoms", "包装单位投影", "admin.pms_integration", 3, 30),
    ("admin.pms_integration.sku_codes", "SKU 编码投影", "admin.pms_integration", 3, 40),
    ("admin.pms_integration.barcodes", "条码投影", "admin.pms_integration", 3, 50),
)

NEW_ROUTE_ROWS = (
    ("admin.pms_integration", "/admin/pms-integration", 20),
    ("admin.pms_integration.items", "/admin/pms-integration/items", 10),
    ("admin.pms_integration.suppliers", "/admin/pms-integration/suppliers", 20),
    ("admin.pms_integration.uoms", "/admin/pms-integration/uoms", 30),
    ("admin.pms_integration.sku_codes", "/admin/pms-integration/sku-codes", 40),
    ("admin.pms_integration.barcodes", "/admin/pms-integration/barcodes", 50),
)

OLD_PAGE_RESTORE_ROWS = (
    ("pms", "商品主数据", None, 1, "pms", True, False, False, 80),
    ("pms.items", "商品列表", "pms", 2, "pms", False, True, True, 10),
    ("pms.brands", "品牌管理", "pms", 2, "pms", False, True, True, 20),
    ("pms.categories", "商品分类编码", "pms", 2, "pms", False, True, True, 30),
    ("pms.item_attributes", "属性模板", "pms", 2, "pms", False, True, True, 40),
    ("pms.sku_coding", "SKU 编码工具", "pms", 2, "pms", False, True, True, 50),
    ("pms.item_barcodes", "商品条码", "pms", 2, "pms", False, True, True, 60),
    ("pms.item_uoms", "包装单位", "pms", 2, "pms", False, True, True, 70),
)

OLD_ROUTE_RESTORE_ROWS = (
    ("pms.items", "/items", 10),
    ("pms.brands", "/pms/brands", 20),
    ("pms.categories", "/pms/categories", 30),
    ("pms.item_attributes", "/pms/item-attribute-defs", 40),
    ("pms.sku_coding", "/items/sku-coding", 50),
    ("pms.item_barcodes", "/item-barcodes", 60),
    ("pms.item_uoms", "/item-uoms", 70),
)


def upgrade() -> None:
    conn = op.get_bind()

    op.create_table(
        "wms_pms_projection_sync_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("resource", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("fetched", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("upserted", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("pages", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("triggered_by_user_id", sa.Integer(), nullable=True),
        sa.Column("pms_api_base_url_snapshot", sa.String(length=512), nullable=True),
        sa.Column("sync_version", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_wms_pms_projection_sync_runs"),
        sa.ForeignKeyConstraint(
            ["triggered_by_user_id"],
            ["users.id"],
            name="fk_wms_pms_projection_sync_runs_triggered_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "resource IN ('items', 'suppliers', 'uoms', 'sku-codes', 'barcodes', 'all')",
            name="ck_wms_pms_projection_sync_runs_resource",
        ),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'SUCCESS', 'FAILED')",
            name="ck_wms_pms_projection_sync_runs_status",
        ),
        sa.CheckConstraint(
            "fetched >= 0",
            name="ck_wms_pms_projection_sync_runs_fetched_non_negative",
        ),
        sa.CheckConstraint(
            "upserted >= 0",
            name="ck_wms_pms_projection_sync_runs_upserted_non_negative",
        ),
        sa.CheckConstraint(
            "pages >= 0",
            name="ck_wms_pms_projection_sync_runs_pages_non_negative",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_wms_pms_projection_sync_runs_duration_non_negative",
        ),
    )
    op.create_index(
        "ix_wms_pms_projection_sync_runs_resource_started_at",
        "wms_pms_projection_sync_runs",
        ["resource", "started_at"],
    )
    op.create_index(
        "ix_wms_pms_projection_sync_runs_status",
        "wms_pms_projection_sync_runs",
        ["status"],
    )

    conn.execute(
        sa.text(
            """
            DELETE FROM page_route_prefixes
            WHERE route_prefix IN (
              '/items',
              '/item-barcodes',
              '/item-uoms',
              '/items/sku-coding',
              '/pms/brands',
              '/pms/categories',
              '/pms/item-attribute-defs'
            )
               OR page_code = 'pms'
               OR page_code LIKE 'pms.%'
            """
        )
    )

    conn.execute(
        sa.text(
            """
            DELETE FROM page_registry
            WHERE code IN (
              'pms.item_barcodes',
              'pms.item_uoms',
              'pms.sku_coding',
              'pms.item_attributes',
              'pms.categories',
              'pms.brands',
              'pms.items'
            )
            """
        )
    )
    conn.execute(sa.text("DELETE FROM page_registry WHERE code = 'pms'"))

    conn.execute(
        sa.text(
            """
            DELETE FROM permissions
            WHERE name IN ('page.pms.read', 'page.pms.write')
            """
        )
    )

    for code, name, parent_code, level, sort_order in NEW_PAGE_ROWS:
        conn.execute(
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
                  'admin',
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

    for page_code, route_prefix, sort_order in NEW_ROUTE_ROWS:
        conn.execute(
            sa.text(
                """
                INSERT INTO page_route_prefixes (
                  page_code,
                  route_prefix,
                  sort_order,
                  is_active
                )
                VALUES (
                  :page_code,
                  :route_prefix,
                  :sort_order,
                  TRUE
                )
                ON CONFLICT (route_prefix) DO UPDATE
                SET
                  page_code = EXCLUDED.page_code,
                  sort_order = EXCLUDED.sort_order,
                  is_active = EXCLUDED.is_active
                """
            ),
            {
                "page_code": page_code,
                "route_prefix": route_prefix,
                "sort_order": sort_order,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
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
    )

    conn.execute(sa.text("DELETE FROM page_registry WHERE code LIKE 'admin.pms_integration.%'"))
    conn.execute(sa.text("DELETE FROM page_registry WHERE code = 'admin.pms_integration'"))

    op.drop_index(
        "ix_wms_pms_projection_sync_runs_status",
        table_name="wms_pms_projection_sync_runs",
    )
    op.drop_index(
        "ix_wms_pms_projection_sync_runs_resource_started_at",
        table_name="wms_pms_projection_sync_runs",
    )
    op.drop_table("wms_pms_projection_sync_runs")

    conn.execute(
        sa.text(
            """
            INSERT INTO permissions (name)
            VALUES ('page.pms.read'), ('page.pms.write')
            ON CONFLICT (name) DO NOTHING
            """
        )
    )

    for code, name, parent_code, level, domain_code, show_in_topbar, show_in_sidebar, inherit_permissions, sort_order in OLD_PAGE_RESTORE_ROWS:
        conn.execute(
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
                  :domain_code,
                  :show_in_topbar,
                  :show_in_sidebar,
                  :inherit_permissions,
                  CASE
                    WHEN :inherit_permissions THEN NULL
                    ELSE (SELECT id FROM permissions WHERE name = 'page.pms.read')
                  END,
                  CASE
                    WHEN :inherit_permissions THEN NULL
                    ELSE (SELECT id FROM permissions WHERE name = 'page.pms.write')
                  END,
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
                "domain_code": domain_code,
                "show_in_topbar": show_in_topbar,
                "show_in_sidebar": show_in_sidebar,
                "inherit_permissions": inherit_permissions,
                "sort_order": sort_order,
            },
        )

    for page_code, route_prefix, sort_order in OLD_ROUTE_RESTORE_ROWS:
        conn.execute(
            sa.text(
                """
                INSERT INTO page_route_prefixes (
                  page_code,
                  route_prefix,
                  sort_order,
                  is_active
                )
                VALUES (
                  :page_code,
                  :route_prefix,
                  :sort_order,
                  TRUE
                )
                ON CONFLICT (route_prefix) DO UPDATE
                SET
                  page_code = EXCLUDED.page_code,
                  sort_order = EXCLUDED.sort_order,
                  is_active = EXCLUDED.is_active
                """
            ),
            {
                "page_code": page_code,
                "route_prefix": route_prefix,
                "sort_order": sort_order,
            },
        )

    conn.execute(
        sa.text(
            """
            WITH mappings AS (
              SELECT 'page.admin.read' AS source_name, 'page.pms.read' AS target_name
              UNION ALL
              SELECT 'page.admin.write', 'page.pms.write'
            ),
            pairs AS (
              SELECT DISTINCT
                up.user_id AS user_id,
                tp.id AS permission_id
              FROM mappings m
              JOIN permissions sp
                ON sp.name = m.source_name
              JOIN user_permissions up
                ON up.permission_id = sp.id
              JOIN permissions tp
                ON tp.name = m.target_name
            )
            INSERT INTO user_permissions (user_id, permission_id)
            SELECT user_id, permission_id
            FROM pairs
            ON CONFLICT (user_id, permission_id) DO NOTHING
            """
        )
    )
