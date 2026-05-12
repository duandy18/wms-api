"""retire_wms_partners_supplier_owner

Revision ID: 7c9d1a2e4b6f
Revises: 4f8c2a19d6b3
Create Date: 2026-05-12 10:55:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "7c9d1a2e4b6f"
down_revision: Union[str, Sequence[str], None] = "4f8c2a19d6b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Retire WMS legacy supplier owner UI/API registration.
    # Keep /partners/export/suppliers as read-only projection-backed export surface.
    op.execute(
        """
        DELETE FROM page_route_prefixes
        WHERE route_prefix = '/partners/suppliers'
        """
    )

    op.execute(
        """
        DELETE FROM page_registry
        WHERE code = 'partners.suppliers'
        """
    )

    op.execute(
        """
        DELETE FROM page_registry
        WHERE code = 'partners'
          AND NOT EXISTS (
            SELECT 1
            FROM page_registry child
            WHERE child.parent_code = 'partners'
          )
        """
    )

    op.execute(
        """
        DELETE FROM permissions p
        WHERE p.name IN ('page.partners.read', 'page.partners.write')
          AND NOT EXISTS (
            SELECT 1
            FROM page_registry pr
            WHERE pr.read_permission_id = p.id
               OR pr.write_permission_id = p.id
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        INSERT INTO permissions (name)
        VALUES
          ('page.partners.read'),
          ('page.partners.write')
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
        VALUES (
          'partners',
          '往来单位',
          NULL,
          1,
          'partners',
          TRUE,
          TRUE,
          FALSE,
          (SELECT id FROM permissions WHERE name = 'page.partners.read'),
          (SELECT id FROM permissions WHERE name = 'page.partners.write'),
          80,
          TRUE
        )
        ON CONFLICT (code) DO UPDATE SET
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
        ON CONFLICT (code) DO UPDATE SET
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
        VALUES ('/partners/suppliers', 'partners.suppliers', 10, TRUE)
        ON CONFLICT (route_prefix) DO UPDATE SET
          page_code = EXCLUDED.page_code,
          sort_order = EXCLUDED.sort_order,
          is_active = EXCLUDED.is_active
        """
    )
