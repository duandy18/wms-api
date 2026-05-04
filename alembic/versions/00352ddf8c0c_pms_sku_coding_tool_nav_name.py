"""pms sku coding tool nav name

Revision ID: 00352ddf8c0c
Revises: efbbba76f264
Create Date: 2026-05-04 16:57:01.604285

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "00352ddf8c0c"
down_revision: Union[str, Sequence[str], None] = "efbbba76f264"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename PMS SKU coding navigation node to tool semantics."""

    op.execute(
        """
        UPDATE page_registry
           SET name = 'SKU 编码工具'
         WHERE code = 'pms.sku_coding'
        """
    )


def downgrade() -> None:
    """Restore previous PMS SKU coding navigation node name."""

    op.execute(
        """
        UPDATE page_registry
           SET name = 'SKU 编码'
         WHERE code = 'pms.sku_coding'
        """
    )
