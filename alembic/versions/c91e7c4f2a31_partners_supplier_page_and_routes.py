"""partners supplier page and routes

Revision ID: c91e7c4f2a31
Revises: 9c1f2a3b4d5e
Create Date: 2026-05-09 08:10:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "c91e7c4f2a31"
down_revision: Union[str, Sequence[str], None] = "9c1f2a3b4d5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DOMAIN_CHECK_WITH_PARTNERS = (
    "domain_code IN ("
    "'finance', 'oms', 'pms', 'procurement', 'partners', "
    "'wms', 'shipping_assist', 'admin', 'inbound'"
    ")"
)

DOMAIN_CHECK_WITHOUT_PARTNERS = (
    "domain_code IN ("
    "'finance', 'oms', 'pms', 'procurement', "
    "'wms', 'shipping_assist', 'admin', 'inbound'"
    ")"
)


def upgrade() -> None:
    """Move supplier ownership from PMS to Partners navigation boundary."""

    # 1) 扩展 page_registry.domain_code 终态约束，纳入 partners。
    op.execute("ALTER TABLE page_registry DROP CONSTRAINT IF EXISTS ck_page_registry_domain_code")
    op.create_check_constraint(
        "ck_page_registry_domain_code",
        "page_registry",
        DOMAIN_CHECK_WITH_PARTNERS,
    )

    # 2) 新增 Partners 权限。
    op.execute(
        """
        INSERT INTO permissions (name)
        VALUES
          ('page.partners.read'),
          ('page.partners.write')
        ON CONFLICT (name) DO NOTHING
        """
    )

    # 3) page_route_prefixes.page_code -> page_registry.code 有 FK；
    #    先删除旧 /suppliers 路由，再删除旧 pms.suppliers 页面。
    op.execute(
        """
        DELETE FROM page_route_prefixes
         WHERE route_prefix = '/suppliers'
        """
    )

    op.execute(
        """
        DELETE FROM page_registry
         WHERE code = 'pms.suppliers'
        """
    )

    # 4) 注册 partners 根页面。
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
        VALUES (
          'partners',
          '合作方',
          NULL,
          1,
          'partners',
          TRUE,
          FALSE,
          FALSE,
          (SELECT id FROM permissions WHERE name = 'page.partners.read'),
          (SELECT id FROM permissions WHERE name = 'page.partners.write'),
          90,
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

    # 5) 注册 partners.suppliers 页面。
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
        VALUES (
          'partners.suppliers',
          '供应商管理',
          'partners',
          2,
          'partners',
          FALSE,
          TRUE,
          TRUE,
          NULL,
          NULL,
          10,
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

    # 6) 绑定新前端路由。
    op.execute(
        """
        INSERT INTO page_route_prefixes (route_prefix, page_code, sort_order, is_active)
        VALUES ('/partners/suppliers', 'partners.suppliers', 10, TRUE)
        ON CONFLICT (route_prefix) DO UPDATE
        SET
          page_code = EXCLUDED.page_code,
          sort_order = EXCLUDED.sort_order,
          is_active = EXCLUDED.is_active
        """
    )

    # 7) 权限迁移：已有 PMS 权限的用户补发 Partners 权限。
    op.execute(
        """
        WITH mappings AS (
          SELECT 'page.pms.read' AS source_name, 'page.partners.read' AS target_name
          UNION ALL
          SELECT 'page.pms.write', 'page.partners.write'
        ),
        pairs AS (
          SELECT DISTINCT
            up.user_id,
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


def downgrade() -> None:
    """Move supplier page back under PMS navigation boundary."""

    # 1) 先删 route_prefix，再删 partners 页面，避免 FK 阻塞。
    op.execute(
        """
        DELETE FROM page_route_prefixes
         WHERE route_prefix = '/partners/suppliers'
        """
    )

    op.execute(
        """
        DELETE FROM page_registry
         WHERE code IN ('partners.suppliers', 'partners')
        """
    )

    # 2) 删除 Partners 权限。user_permissions 会随 permissions 删除级联清理。
    op.execute(
        """
        DELETE FROM permissions
         WHERE name IN ('page.partners.read', 'page.partners.write')
        """
    )

    # 3) 恢复 PMS suppliers 页面和旧路由。
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
        VALUES (
          'pms.suppliers',
          '供应商管理',
          'pms',
          2,
          'pms',
          FALSE,
          TRUE,
          TRUE,
          NULL,
          NULL,
          80,
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
        INSERT INTO page_route_prefixes (route_prefix, page_code, sort_order, is_active)
        VALUES ('/suppliers', 'pms.suppliers', 10, TRUE)
        ON CONFLICT (route_prefix) DO UPDATE
        SET
          page_code = EXCLUDED.page_code,
          sort_order = EXCLUDED.sort_order,
          is_active = EXCLUDED.is_active
        """
    )

    # 4) 收回 partners domain_code 约束。
    op.execute("ALTER TABLE page_registry DROP CONSTRAINT IF EXISTS ck_page_registry_domain_code")
    op.create_check_constraint(
        "ck_page_registry_domain_code",
        "page_registry",
        DOMAIN_CHECK_WITHOUT_PARTNERS,
    )
