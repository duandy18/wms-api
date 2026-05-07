"""register shipping assist handoff subpages

Revision ID: 6f2c7d4a9e18
Revises: bf9a287b97de
Create Date: 2026-05-07 22:58:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "6f2c7d4a9e18"
down_revision: Union[str, Sequence[str], None] = "bf9a287b97de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Register handoff status/payload as independent frontend routes."""

    # 父级入口：侧边菜单只显示“发货交接”
    op.execute(
        """
        UPDATE page_registry
           SET name = '发货交接',
               is_active = TRUE,
               parent_code = 'shipping_assist',
               level = 2,
               domain_code = 'shipping_assist',
               show_in_topbar = FALSE,
               show_in_sidebar = TRUE,
               inherit_permissions = TRUE,
               read_permission_id = NULL,
               write_permission_id = NULL,
               sort_order = 10
         WHERE code = 'shipping_assist.handoffs'
        """
    )

    # 三级子页：真实页面路由，但不在侧边栏单独显示
    op.execute(
        """
        INSERT INTO page_registry (
          code,
          name,
          read_permission_id,
          write_permission_id,
          sort_order,
          is_active,
          parent_code,
          level,
          domain_code,
          show_in_topbar,
          show_in_sidebar,
          inherit_permissions
        )
        VALUES
          (
            'shipping_assist.handoffs.status',
            '交接状态',
            NULL,
            NULL,
            10,
            TRUE,
            'shipping_assist.handoffs',
            3,
            'shipping_assist',
            FALSE,
            FALSE,
            TRUE
          ),
          (
            'shipping_assist.handoffs.payload',
            '交接数据',
            NULL,
            NULL,
            20,
            TRUE,
            'shipping_assist.handoffs',
            3,
            'shipping_assist',
            FALSE,
            FALSE,
            TRUE
          )
        ON CONFLICT (code) DO UPDATE SET
          name = EXCLUDED.name,
          read_permission_id = EXCLUDED.read_permission_id,
          write_permission_id = EXCLUDED.write_permission_id,
          sort_order = EXCLUDED.sort_order,
          is_active = TRUE,
          parent_code = EXCLUDED.parent_code,
          level = EXCLUDED.level,
          domain_code = EXCLUDED.domain_code,
          show_in_topbar = EXCLUDED.show_in_topbar,
          show_in_sidebar = EXCLUDED.show_in_sidebar,
          inherit_permissions = EXCLUDED.inherit_permissions
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
          (
            'shipping_assist.handoffs',
            '/shipping-assist/handoffs',
            10,
            TRUE
          ),
          (
            'shipping_assist.handoffs.status',
            '/shipping-assist/handoffs/status',
            11,
            TRUE
          ),
          (
            'shipping_assist.handoffs.payload',
            '/shipping-assist/handoffs/payload',
            12,
            TRUE
          )
        ON CONFLICT (route_prefix) DO UPDATE SET
          page_code = EXCLUDED.page_code,
          sort_order = EXCLUDED.sort_order,
          is_active = TRUE
        """
    )

    # 发货记录仍为同级菜单项
    op.execute(
        """
        UPDATE page_registry
           SET is_active = TRUE,
               parent_code = 'shipping_assist',
               level = 2,
               domain_code = 'shipping_assist',
               show_in_topbar = FALSE,
               show_in_sidebar = TRUE,
               inherit_permissions = TRUE,
               read_permission_id = NULL,
               write_permission_id = NULL,
               sort_order = 20
         WHERE code = 'shipping_assist.records'
        """
    )

    op.execute(
        """
        UPDATE page_route_prefixes
           SET sort_order = 20,
               is_active = TRUE,
               page_code = 'shipping_assist.records'
         WHERE route_prefix = '/shipping-assist/records'
        """
    )

    # 继续隐藏已退役 Shipping Assist 历史页面/路由
    op.execute(
        """
        UPDATE page_registry
           SET is_active = CASE
                 WHEN code IN (
                   'shipping_assist',
                   'shipping_assist.handoffs',
                   'shipping_assist.handoffs.status',
                   'shipping_assist.handoffs.payload',
                   'shipping_assist.records'
                 )
                 THEN TRUE
                 ELSE FALSE
               END
         WHERE code = 'shipping_assist'
            OR code LIKE 'shipping_assist.%'
        """
    )

    op.execute(
        """
        UPDATE page_route_prefixes
           SET is_active = CASE
                 WHEN route_prefix IN (
                   '/shipping-assist/handoffs',
                   '/shipping-assist/handoffs/status',
                   '/shipping-assist/handoffs/payload',
                   '/shipping-assist/records'
                 )
                 THEN TRUE
                 ELSE FALSE
               END
         WHERE route_prefix LIKE '/shipping-assist/%'
            OR page_code = 'shipping_assist'
            OR page_code LIKE 'shipping_assist.%'
        """
    )


def downgrade() -> None:
    """Remove handoff status/payload subpage route registration."""

    op.execute(
        """
        DELETE FROM page_route_prefixes
         WHERE route_prefix IN (
           '/shipping-assist/handoffs/status',
           '/shipping-assist/handoffs/payload'
         )
        """
    )

    op.execute(
        """
        DELETE FROM page_registry
         WHERE code IN (
           'shipping_assist.handoffs.status',
           'shipping_assist.handoffs.payload'
         )
        """
    )

    op.execute(
        """
        UPDATE page_registry
           SET name = '发货交接',
               is_active = TRUE,
               parent_code = 'shipping_assist',
               level = 2,
               domain_code = 'shipping_assist',
               show_in_topbar = FALSE,
               show_in_sidebar = TRUE,
               inherit_permissions = TRUE,
               read_permission_id = NULL,
               write_permission_id = NULL,
               sort_order = 10
         WHERE code = 'shipping_assist.handoffs'
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
        VALUES (
          'shipping_assist.handoffs',
          '/shipping-assist/handoffs',
          10,
          TRUE
        )
        ON CONFLICT (route_prefix) DO UPDATE SET
          page_code = EXCLUDED.page_code,
          sort_order = EXCLUDED.sort_order,
          is_active = TRUE
        """
    )

    op.execute(
        """
        UPDATE page_route_prefixes
           SET is_active = CASE
                 WHEN route_prefix IN (
                   '/shipping-assist/handoffs',
                   '/shipping-assist/records'
                 )
                 THEN TRUE
                 ELSE FALSE
               END
         WHERE route_prefix LIKE '/shipping-assist/%'
            OR page_code = 'shipping_assist'
            OR page_code LIKE 'shipping_assist.%'
        """
    )
