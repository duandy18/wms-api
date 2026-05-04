"""move fsku master data to pms expression rules

Revision ID: 58fbca440761
Revises: 00352ddf8c0c
Create Date: 2026-05-04 21:08:25.113760

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "58fbca440761"
down_revision: Union[str, Sequence[str], None] = "00352ddf8c0c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Move FSKU master data from OMS-owned tables to PMS expression-rule tables."""

    op.execute("DROP TRIGGER IF EXISTS trg_ck_fskus_retire_not_referenced ON fskus")
    op.execute("DROP FUNCTION IF EXISTS ck_fskus_retire_not_referenced()")

    op.execute(
        """
        ALTER TABLE merchant_code_fsku_bindings
        DROP CONSTRAINT IF EXISTS merchant_code_fsku_bindings_fsku_id_fkey
        """
    )
    op.execute(
        """
        ALTER TABLE fsku_components
        DROP CONSTRAINT IF EXISTS fsku_components_fsku_id_fkey
        """
    )
    op.execute(
        """
        ALTER TABLE fsku_components
        DROP CONSTRAINT IF EXISTS fsku_components_item_id_fkey
        """
    )

    op.rename_table("fskus", "pms_fskus")
    op.rename_table("fsku_components", "pms_fsku_components")

    op.execute("ALTER SEQUENCE IF EXISTS fskus_id_seq RENAME TO pms_fskus_id_seq")
    op.execute("ALTER SEQUENCE IF EXISTS fsku_components_id_seq RENAME TO pms_fsku_components_id_seq")
    op.execute("ALTER TABLE pms_fskus ALTER COLUMN id SET DEFAULT nextval('pms_fskus_id_seq'::regclass)")
    op.execute("ALTER TABLE pms_fsku_components ALTER COLUMN id SET DEFAULT nextval('pms_fsku_components_id_seq'::regclass)")

    op.execute("ALTER INDEX IF EXISTS fskus_pkey RENAME TO pms_fskus_pkey")
    op.execute("ALTER INDEX IF EXISTS ix_fskus_status RENAME TO ix_pms_fskus_status")
    op.execute("ALTER INDEX IF EXISTS ux_fskus_code RENAME TO ux_pms_fskus_code")
    op.execute("ALTER INDEX IF EXISTS fsku_components_pkey RENAME TO pms_fsku_components_pkey")
    op.execute("ALTER INDEX IF EXISTS ix_fsku_components_fsku_id RENAME TO ix_pms_fsku_components_fsku_id")
    op.execute("ALTER INDEX IF EXISTS ix_fsku_components_item_id RENAME TO ix_pms_fsku_components_resolved_item_id")

    op.execute("ALTER TABLE pms_fskus ADD COLUMN IF NOT EXISTS fsku_expr TEXT")
    op.execute("ALTER TABLE pms_fskus ADD COLUMN IF NOT EXISTS normalized_expr TEXT")
    op.execute("ALTER TABLE pms_fskus ADD COLUMN IF NOT EXISTS expr_type VARCHAR(32)")
    op.execute("ALTER TABLE pms_fskus ADD COLUMN IF NOT EXISTS component_count INTEGER")

    op.execute("ALTER TABLE pms_fsku_components RENAME COLUMN item_id TO resolved_item_id")
    op.execute("ALTER TABLE pms_fsku_components RENAME COLUMN qty TO qty_per_fsku")

    op.execute("ALTER TABLE pms_fsku_components ADD COLUMN IF NOT EXISTS component_sku_code VARCHAR(128)")
    op.execute("ALTER TABLE pms_fsku_components ADD COLUMN IF NOT EXISTS alloc_unit_price NUMERIC(18,6) NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE pms_fsku_components ADD COLUMN IF NOT EXISTS resolved_item_sku_code_id INTEGER")
    op.execute("ALTER TABLE pms_fsku_components ADD COLUMN IF NOT EXISTS resolved_item_uom_id INTEGER")
    op.execute("ALTER TABLE pms_fsku_components ADD COLUMN IF NOT EXISTS sku_code_snapshot VARCHAR(128)")
    op.execute("ALTER TABLE pms_fsku_components ADD COLUMN IF NOT EXISTS item_name_snapshot VARCHAR(128)")
    op.execute("ALTER TABLE pms_fsku_components ADD COLUMN IF NOT EXISTS uom_snapshot VARCHAR(32)")
    op.execute("ALTER TABLE pms_fsku_components ADD COLUMN IF NOT EXISTS sort_order INTEGER")

    op.execute(
        """
        UPDATE pms_fsku_components c
           SET sort_order = ranked.rn
          FROM (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY fsku_id ORDER BY id ASC)::int AS rn
              FROM pms_fsku_components
          ) ranked
         WHERE ranked.id = c.id
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
              FROM pg_constraint
             WHERE conname = 'uq_item_sku_codes_id_item_id'
          ) THEN
            ALTER TABLE item_sku_codes
            ADD CONSTRAINT uq_item_sku_codes_id_item_id UNIQUE (id, item_id);
          END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
              FROM pg_constraint
             WHERE conname = 'uq_item_uoms_id_item_id'
          ) THEN
            ALTER TABLE item_uoms
            ADD CONSTRAINT uq_item_uoms_id_item_id UNIQUE (id, item_id);
          END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        WITH code_rows AS (
          SELECT DISTINCT ON (c.item_id)
                 c.id AS sku_code_id,
                 c.item_id,
                 c.code AS sku_code
            FROM item_sku_codes c
           WHERE c.is_active = TRUE
           ORDER BY c.item_id, c.is_primary DESC, c.id ASC
        ),
        uom_rows AS (
          SELECT DISTINCT ON (u.item_id)
                 u.id AS item_uom_id,
                 u.item_id,
                 COALESCE(NULLIF(u.display_name, ''), NULLIF(u.uom, ''), u.uom) AS uom_name
            FROM item_uoms u
           WHERE u.is_outbound_default = TRUE OR u.is_base = TRUE
           ORDER BY u.item_id, u.is_outbound_default DESC, u.is_base DESC, u.id ASC
        )
        UPDATE pms_fsku_components c
           SET component_sku_code = cr.sku_code,
               resolved_item_sku_code_id = cr.sku_code_id,
               resolved_item_uom_id = ur.item_uom_id,
               sku_code_snapshot = cr.sku_code,
               item_name_snapshot = i.name,
               uom_snapshot = ur.uom_name
          FROM code_rows cr
          JOIN items i
            ON i.id = cr.item_id
          JOIN uom_rows ur
            ON ur.item_id = cr.item_id
         WHERE c.resolved_item_id = cr.item_id
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
              FROM pms_fsku_components
             WHERE component_sku_code IS NULL
                OR resolved_item_sku_code_id IS NULL
                OR resolved_item_uom_id IS NULL
                OR sku_code_snapshot IS NULL
                OR item_name_snapshot IS NULL
                OR uom_snapshot IS NULL
                OR sort_order IS NULL
          ) THEN
            RAISE EXCEPTION 'pms_fsku_components backfill failed: unresolved component_sku_code/item_sku_code/uom/snapshot';
          END IF;
        END
        $$;
        """
    )

    op.execute("ALTER TABLE pms_fsku_components ALTER COLUMN component_sku_code SET NOT NULL")
    op.execute("ALTER TABLE pms_fsku_components ALTER COLUMN resolved_item_sku_code_id SET NOT NULL")
    op.execute("ALTER TABLE pms_fsku_components ALTER COLUMN resolved_item_uom_id SET NOT NULL")
    op.execute("ALTER TABLE pms_fsku_components ALTER COLUMN sku_code_snapshot SET NOT NULL")
    op.execute("ALTER TABLE pms_fsku_components ALTER COLUMN item_name_snapshot SET NOT NULL")
    op.execute("ALTER TABLE pms_fsku_components ALTER COLUMN uom_snapshot SET NOT NULL")
    op.execute("ALTER TABLE pms_fsku_components ALTER COLUMN sort_order SET NOT NULL")

    op.execute("ALTER TABLE pms_fsku_components DROP COLUMN IF EXISTS role")

    op.execute(
        """
        WITH component_expr AS (
          SELECT
            c.fsku_id,
            COUNT(*)::int AS component_count,
            STRING_AGG(
              c.component_sku_code
              || '*'
              || CASE
                   WHEN c.qty_per_fsku = TRUNC(c.qty_per_fsku)
                     THEN (c.qty_per_fsku::bigint)::text
                   ELSE regexp_replace(regexp_replace(c.qty_per_fsku::text, '0+$', ''), '\\.$', '')
                 END
              || '*'
              || CASE
                   WHEN c.alloc_unit_price = TRUNC(c.alloc_unit_price)
                     THEN (c.alloc_unit_price::bigint)::text
                   ELSE regexp_replace(regexp_replace(c.alloc_unit_price::text, '0+$', ''), '\\.$', '')
                 END,
              '+'
              ORDER BY c.sort_order ASC
            ) AS expr
          FROM pms_fsku_components c
          GROUP BY c.fsku_id
        )
        UPDATE pms_fskus f
           SET fsku_expr = COALESCE(component_expr.expr, f.code),
               normalized_expr = UPPER(COALESCE(component_expr.expr, f.code)),
               expr_type = 'DIRECT',
               component_count = COALESCE(component_expr.component_count, 0)
          FROM component_expr
         WHERE component_expr.fsku_id = f.id
        """
    )

    op.execute(
        """
        UPDATE pms_fskus
           SET fsku_expr = COALESCE(fsku_expr, code),
               normalized_expr = COALESCE(normalized_expr, UPPER(code)),
               expr_type = COALESCE(expr_type, 'DIRECT'),
               component_count = COALESCE(component_count, 0)
        """
    )

    op.execute("ALTER TABLE pms_fskus ALTER COLUMN fsku_expr SET NOT NULL")
    op.execute("ALTER TABLE pms_fskus ALTER COLUMN normalized_expr SET NOT NULL")
    op.execute("ALTER TABLE pms_fskus ALTER COLUMN expr_type SET NOT NULL")
    op.execute("ALTER TABLE pms_fskus ALTER COLUMN component_count SET NOT NULL")

    op.execute("ALTER TABLE pms_fskus DROP CONSTRAINT IF EXISTS ck_fskus_shape")
    op.execute("ALTER TABLE pms_fskus DROP CONSTRAINT IF EXISTS ck_pms_fskus_shape")
    op.execute("ALTER TABLE pms_fskus DROP CONSTRAINT IF EXISTS ck_pms_fskus_status")
    op.execute("ALTER TABLE pms_fskus DROP CONSTRAINT IF EXISTS ck_pms_fskus_expr_type")
    op.execute("ALTER TABLE pms_fskus DROP CONSTRAINT IF EXISTS ck_pms_fskus_component_count_nonnegative")

    op.execute(
        """
        ALTER TABLE pms_fskus
        ADD CONSTRAINT ck_pms_fskus_shape
        CHECK (shape IN ('single', 'bundle'))
        """
    )
    op.execute(
        """
        ALTER TABLE pms_fskus
        ADD CONSTRAINT ck_pms_fskus_status
        CHECK (status IN ('draft', 'published', 'retired'))
        """
    )
    op.execute(
        """
        ALTER TABLE pms_fskus
        ADD CONSTRAINT ck_pms_fskus_expr_type
        CHECK (expr_type IN ('DIRECT', 'SEGMENT_GROUP'))
        """
    )
    op.execute(
        """
        ALTER TABLE pms_fskus
        ADD CONSTRAINT ck_pms_fskus_component_count_nonnegative
        CHECK (component_count >= 0)
        """
    )

    op.execute("ALTER TABLE pms_fsku_components DROP CONSTRAINT IF EXISTS ck_pms_fsku_components_qty_positive")
    op.execute("ALTER TABLE pms_fsku_components DROP CONSTRAINT IF EXISTS ck_pms_fsku_components_alloc_unit_price_positive")
    op.execute("ALTER TABLE pms_fsku_components DROP CONSTRAINT IF EXISTS fk_pms_fsku_components_fsku")
    op.execute("ALTER TABLE pms_fsku_components DROP CONSTRAINT IF EXISTS fk_pms_fsku_components_resolved_item")
    op.execute("ALTER TABLE pms_fsku_components DROP CONSTRAINT IF EXISTS fk_pms_fsku_components_resolved_sku_code")
    op.execute("ALTER TABLE pms_fsku_components DROP CONSTRAINT IF EXISTS fk_pms_fsku_components_resolved_uom")
    op.execute("ALTER TABLE pms_fsku_components DROP CONSTRAINT IF EXISTS uq_pms_fsku_components_fsku_component_sku")
    op.execute("ALTER TABLE pms_fsku_components DROP CONSTRAINT IF EXISTS uq_pms_fsku_components_fsku_sort")

    op.execute(
        """
        ALTER TABLE pms_fsku_components
        ADD CONSTRAINT ck_pms_fsku_components_qty_positive
        CHECK (qty_per_fsku > 0)
        """
    )
    op.execute(
        """
        ALTER TABLE pms_fsku_components
        ADD CONSTRAINT ck_pms_fsku_components_alloc_unit_price_positive
        CHECK (alloc_unit_price > 0)
        """
    )

    op.execute(
        """
        ALTER TABLE pms_fsku_components
        ADD CONSTRAINT fk_pms_fsku_components_fsku
        FOREIGN KEY (fsku_id) REFERENCES pms_fskus(id) ON DELETE CASCADE
        """
    )
    op.execute(
        """
        ALTER TABLE pms_fsku_components
        ADD CONSTRAINT fk_pms_fsku_components_resolved_item
        FOREIGN KEY (resolved_item_id) REFERENCES items(id) ON DELETE RESTRICT
        """
    )
    op.execute(
        """
        ALTER TABLE pms_fsku_components
        ADD CONSTRAINT fk_pms_fsku_components_resolved_sku_code
        FOREIGN KEY (resolved_item_sku_code_id, resolved_item_id)
        REFERENCES item_sku_codes(id, item_id) ON DELETE RESTRICT
        """
    )
    op.execute(
        """
        ALTER TABLE pms_fsku_components
        ADD CONSTRAINT fk_pms_fsku_components_resolved_uom
        FOREIGN KEY (resolved_item_uom_id, resolved_item_id)
        REFERENCES item_uoms(id, item_id) ON DELETE RESTRICT
        """
    )

    op.execute(
        """
        ALTER TABLE pms_fsku_components
        ADD CONSTRAINT uq_pms_fsku_components_fsku_component_sku
        UNIQUE (fsku_id, component_sku_code)
        """
    )
    op.execute(
        """
        ALTER TABLE pms_fsku_components
        ADD CONSTRAINT uq_pms_fsku_components_fsku_sort
        UNIQUE (fsku_id, sort_order)
        """
    )

    op.execute("CREATE INDEX IF NOT EXISTS ix_pms_fsku_components_resolved_sku_code_id ON pms_fsku_components(resolved_item_sku_code_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pms_fsku_components_resolved_uom_id ON pms_fsku_components(resolved_item_uom_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pms_fskus_normalized_expr ON pms_fskus(normalized_expr)")

    op.execute(
        """
        ALTER TABLE merchant_code_fsku_bindings
        ADD CONSTRAINT merchant_code_fsku_bindings_pms_fsku_id_fkey
        FOREIGN KEY (fsku_id) REFERENCES pms_fskus(id) ON DELETE RESTRICT
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION ck_pms_fskus_retire_not_referenced()
        RETURNS trigger AS $$
        BEGIN
          IF NEW.status = 'retired'
             AND OLD.status IS DISTINCT FROM NEW.status
             AND EXISTS (
               SELECT 1
                 FROM merchant_code_fsku_bindings b
                WHERE b.fsku_id = NEW.id
             )
          THEN
            RAISE EXCEPTION 'PMS FSKU % is referenced by merchant_code_fsku_bindings; cannot retire', NEW.id;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_ck_pms_fskus_retire_not_referenced
        BEFORE UPDATE OF status ON pms_fskus
        FOR EACH ROW
        EXECUTE FUNCTION ck_pms_fskus_retire_not_referenced();
        """
    )


def downgrade() -> None:
    """Hard-cut migration: downgrade is intentionally not supported."""

    raise RuntimeError("pms fsku expression-rule hard cut does not support downgrade")
