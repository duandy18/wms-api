"""inbound_event_lines_source_line_id

Revision ID: 20260513133000_source_line_id
Revises: 737e3e8199df
Create Date: 2026-05-13 13:30:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260513133000_source_line_id"
down_revision: str | Sequence[str] | None = "737e3e8199df"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rename inbound_event_lines.po_line_id to source_line_id and retire local PO FK."""

    op.execute("DROP INDEX IF EXISTS ix_inbound_event_lines_po_line_id;")
    op.execute(
        "ALTER TABLE inbound_event_lines "
        "DROP CONSTRAINT IF EXISTS fk_inbound_event_lines_po_line;"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                  FROM information_schema.columns
                 WHERE table_schema = 'public'
                   AND table_name = 'inbound_event_lines'
                   AND column_name = 'po_line_id'
            )
            AND NOT EXISTS (
                SELECT 1
                  FROM information_schema.columns
                 WHERE table_schema = 'public'
                   AND table_name = 'inbound_event_lines'
                   AND column_name = 'source_line_id'
            ) THEN
                ALTER TABLE inbound_event_lines
                RENAME COLUMN po_line_id TO source_line_id;
            END IF;
        END $$;
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_inbound_event_lines_source_line_id "
        "ON inbound_event_lines (source_line_id);"
    )
    op.execute(
        """
        COMMENT ON COLUMN inbound_event_lines.source_line_id IS
        '外部来源行 ID；采购来源时对应 procurement purchase_order_lines.id，不声明本地 FK';
        """
    )


def downgrade() -> None:
    """Restore inbound_event_lines.po_line_id and local PO FK."""

    op.execute("DROP INDEX IF EXISTS ix_inbound_event_lines_source_line_id;")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                  FROM information_schema.columns
                 WHERE table_schema = 'public'
                   AND table_name = 'inbound_event_lines'
                   AND column_name = 'source_line_id'
            )
            AND NOT EXISTS (
                SELECT 1
                  FROM information_schema.columns
                 WHERE table_schema = 'public'
                   AND table_name = 'inbound_event_lines'
                   AND column_name = 'po_line_id'
            ) THEN
                ALTER TABLE inbound_event_lines
                RENAME COLUMN source_line_id TO po_line_id;
            END IF;
        END $$;
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_inbound_event_lines_po_line_id "
        "ON inbound_event_lines (po_line_id);"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                  FROM pg_constraint
                 WHERE conname = 'fk_inbound_event_lines_po_line'
            ) THEN
                ALTER TABLE inbound_event_lines
                ADD CONSTRAINT fk_inbound_event_lines_po_line
                FOREIGN KEY (po_line_id)
                REFERENCES purchase_order_lines(id)
                ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )
