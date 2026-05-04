"""register pms fsku rules page

Revision ID: 1899ac79faa2
Revises: 58fbca440761
Create Date: 2026-05-04

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "1899ac79faa2"
down_revision: Union[str, Sequence[str], None] = "58fbca440761"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Register PMS FSKU expression rules page and route prefix."""

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
          'pms.fsku_rules',
          'FSKU 组合规则',
          'pms',
          2,
          'pms',
          FALSE,
          TRUE,
          TRUE,
          NULL,
          NULL,
          55,
          TRUE
        )
        ON CONFLICT (code) DO UPDATE
           SET name = EXCLUDED.name,
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
          route_prefix,
          page_code,
          sort_order,
          is_active
        )
        VALUES (
          '/pms/fskus',
          'pms.fsku_rules',
          10,
          TRUE
        )
        ON CONFLICT (route_prefix) DO UPDATE
           SET page_code = EXCLUDED.page_code,
               sort_order = EXCLUDED.sort_order,
               is_active = EXCLUDED.is_active
        """
    )


def downgrade() -> None:
    """Remove PMS FSKU expression rules page and route prefix."""

    op.execute(
        """
        DELETE FROM page_route_prefixes
         WHERE route_prefix = '/pms/fskus'
            OR page_code = 'pms.fsku_rules'
        """
    )
    op.execute(
        """
        DELETE FROM page_registry
         WHERE code = 'pms.fsku_rules'
        """
    )
