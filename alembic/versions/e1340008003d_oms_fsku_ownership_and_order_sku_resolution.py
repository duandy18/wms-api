"""oms_fsku_ownership_and_order_sku_resolution

Revision ID: e1340008003d
Revises: 1899ac79faa2
Create Date: 2026-05-05T09:15:30

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "e1340008003d"
down_revision: Union[str, Sequence[str], None] = "1899ac79faa2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _rename_constraint(table_name: str, old_name: str, new_name: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            WHERE t.relname = '{table_name}'
              AND c.conname = '{old_name}'
          ) THEN
            ALTER TABLE {table_name} RENAME CONSTRAINT {old_name} TO {new_name};
          END IF;
        END $$;
        """
    )


def upgrade() -> None:
    """Upgrade schema."""

    # 1. FSKU ownership: PMS -> OMS. This is a hard rename, not a compatibility alias.
    op.execute(
        """
        DO $$
        BEGIN
          IF to_regclass('public.pms_fskus') IS NOT NULL
             AND to_regclass('public.oms_fskus') IS NULL THEN
            ALTER TABLE pms_fskus RENAME TO oms_fskus;
          END IF;

          IF to_regclass('public.pms_fsku_components') IS NOT NULL
             AND to_regclass('public.oms_fsku_components') IS NULL THEN
            ALTER TABLE pms_fsku_components RENAME TO oms_fsku_components;
          END IF;

          IF to_regclass('public.pms_fskus_id_seq') IS NOT NULL THEN
            ALTER SEQUENCE pms_fskus_id_seq RENAME TO oms_fskus_id_seq;
          END IF;

          IF to_regclass('public.pms_fsku_components_id_seq') IS NOT NULL THEN
            ALTER SEQUENCE pms_fsku_components_id_seq RENAME TO oms_fsku_components_id_seq;
          END IF;
        END $$;
        """
    )

    _rename_constraint("oms_fskus", "pms_fskus_pkey", "oms_fskus_pkey")
    _rename_constraint("oms_fskus", "ck_pms_fskus_component_count_nonnegative", "ck_oms_fskus_component_count_nonnegative")
    _rename_constraint("oms_fskus", "ck_pms_fskus_expr_type", "ck_oms_fskus_expr_type")
    _rename_constraint("oms_fskus", "ck_pms_fskus_shape", "ck_oms_fskus_shape")
    _rename_constraint("oms_fskus", "ck_pms_fskus_status", "ck_oms_fskus_status")
    _rename_constraint("oms_fskus", "ux_pms_fskus_code", "ux_oms_fskus_code")

    _rename_constraint("oms_fsku_components", "pms_fsku_components_pkey", "oms_fsku_components_pkey")
    _rename_constraint("oms_fsku_components", "fk_pms_fsku_components_fsku", "fk_oms_fsku_components_fsku")
    _rename_constraint("oms_fsku_components", "fk_pms_fsku_components_resolved_item", "fk_oms_fsku_components_resolved_item")
    _rename_constraint("oms_fsku_components", "fk_pms_fsku_components_resolved_sku_code", "fk_oms_fsku_components_resolved_sku_code")
    _rename_constraint("oms_fsku_components", "fk_pms_fsku_components_resolved_uom", "fk_oms_fsku_components_resolved_uom")
    _rename_constraint("oms_fsku_components", "ck_pms_fsku_components_alloc_unit_price_positive", "ck_oms_fsku_components_alloc_unit_price_positive")
    _rename_constraint("oms_fsku_components", "ck_pms_fsku_components_qty_positive", "ck_oms_fsku_components_qty_positive")
    _rename_constraint("oms_fsku_components", "uq_pms_fsku_components_fsku_component_sku", "uq_oms_fsku_components_fsku_component_sku")
    _rename_constraint("oms_fsku_components", "uq_pms_fsku_components_fsku_sort", "uq_oms_fsku_components_fsku_sort")

    # Unique index backing ux_pms_fskus_code may keep its old name after table rename.
    # Keep DB index names aligned with the OMS model.
    op.execute("ALTER INDEX IF EXISTS ux_pms_fskus_code RENAME TO ux_oms_fskus_code")

    op.execute("ALTER INDEX IF EXISTS ix_pms_fskus_normalized_expr RENAME TO ix_oms_fskus_normalized_expr")
    op.execute("ALTER INDEX IF EXISTS ix_pms_fskus_status RENAME TO ix_oms_fskus_status")
    op.execute("ALTER INDEX IF EXISTS ix_pms_fsku_components_fsku_id RENAME TO ix_oms_fsku_components_fsku_id")
    op.execute("ALTER INDEX IF EXISTS ix_pms_fsku_components_resolved_item_id RENAME TO ix_oms_fsku_components_resolved_item_id")
    op.execute("ALTER INDEX IF EXISTS ix_pms_fsku_components_resolved_sku_code_id RENAME TO ix_oms_fsku_components_resolved_sku_code_id")
    op.execute("ALTER INDEX IF EXISTS ix_pms_fsku_components_resolved_uom_id RENAME TO ix_oms_fsku_components_resolved_uom_id")

    op.execute(
        """
        ALTER TABLE merchant_code_fsku_bindings
        DROP CONSTRAINT IF EXISTS merchant_code_fsku_bindings_pms_fsku_id_fkey
        """
    )
    op.execute(
        """
        ALTER TABLE merchant_code_fsku_bindings
        DROP CONSTRAINT IF EXISTS merchant_code_fsku_bindings_oms_fsku_id_fkey
        """
    )
    op.execute(
        """
        ALTER TABLE merchant_code_fsku_bindings
        ADD CONSTRAINT merchant_code_fsku_bindings_oms_fsku_id_fkey
        FOREIGN KEY (fsku_id) REFERENCES oms_fskus(id) ON DELETE RESTRICT
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM pg_trigger
            WHERE tgname = 'trg_ck_pms_fskus_retire_not_referenced'
          ) THEN
            ALTER TRIGGER trg_ck_pms_fskus_retire_not_referenced
            ON oms_fskus
            RENAME TO trg_ck_oms_fskus_retire_not_referenced;
          END IF;

          IF EXISTS (
            SELECT 1
            FROM pg_proc
            WHERE proname = 'ck_pms_fskus_retire_not_referenced'
          ) THEN
            ALTER FUNCTION ck_pms_fskus_retire_not_referenced()
            RENAME TO ck_oms_fskus_retire_not_referenced;
          END IF;
        END $$;
        """
    )

    # 2. Order line -> warehouse SKU manual resolution.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS oms_order_sku_resolution_decisions (
          id BIGSERIAL PRIMARY KEY,
          platform VARCHAR(32) NOT NULL,
          store_code TEXT NOT NULL,
          mirror_id BIGINT NOT NULL,
          line_id BIGINT NOT NULL,
          collector_order_id BIGINT NOT NULL,
          collector_line_id BIGINT NOT NULL,
          platform_order_no VARCHAR(128) NOT NULL,
          merchant_code VARCHAR(128),
          platform_item_id VARCHAR(128),
          platform_sku_id VARCHAR(128),
          title_snapshot VARCHAR(255),
          quantity_snapshot NUMERIC(14,4) NOT NULL,
          line_amount_snapshot NUMERIC(14,2),
          reason TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT ck_oms_order_sku_resolution_decisions_platform
            CHECK (platform IN ('PDD', 'TAOBAO', 'JD')),
          CONSTRAINT ux_oms_order_sku_resolution_decisions_line
            UNIQUE (platform, mirror_id, line_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS oms_order_sku_resolution_components (
          id BIGSERIAL PRIMARY KEY,
          decision_id BIGINT NOT NULL
            REFERENCES oms_order_sku_resolution_decisions(id) ON DELETE CASCADE,
          resolved_item_id INTEGER NOT NULL
            REFERENCES items(id) ON DELETE RESTRICT,
          resolved_item_sku_code_id INTEGER NOT NULL,
          resolved_item_uom_id INTEGER NOT NULL,
          sku_code_snapshot VARCHAR(128) NOT NULL,
          item_name_snapshot VARCHAR(128) NOT NULL,
          uom_snapshot VARCHAR(32) NOT NULL,
          qty NUMERIC(18,6) NOT NULL,
          alloc_unit_price NUMERIC(18,6) NOT NULL DEFAULT 1,
          sort_order INTEGER NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT ck_oms_order_sku_resolution_components_qty_positive
            CHECK (qty > 0),
          CONSTRAINT ck_oms_order_sku_resolution_components_alloc_unit_price_positive
            CHECK (alloc_unit_price > 0),
          CONSTRAINT uq_oms_order_sku_resolution_components_sort
            UNIQUE (decision_id, sort_order),
          CONSTRAINT uq_oms_order_sku_resolution_components_sku
            UNIQUE (decision_id, resolved_item_sku_code_id),
          CONSTRAINT fk_oms_order_sku_resolution_components_sku_code
            FOREIGN KEY (resolved_item_sku_code_id, resolved_item_id)
            REFERENCES item_sku_codes(id, item_id) ON DELETE RESTRICT,
          CONSTRAINT fk_oms_order_sku_resolution_components_uom
            FOREIGN KEY (resolved_item_uom_id, resolved_item_id)
            REFERENCES item_uoms(id, item_id) ON DELETE RESTRICT
        )
        """
    )

    op.execute("CREATE INDEX IF NOT EXISTS ix_oms_order_sku_resolution_decisions_mirror ON oms_order_sku_resolution_decisions(platform, mirror_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_oms_order_sku_resolution_decisions_store ON oms_order_sku_resolution_decisions(platform, store_code)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_oms_order_sku_resolution_components_decision ON oms_order_sku_resolution_components(decision_id)")

    # 3. Page ownership: FSKU rules move from PMS to OMS.
    # page_route_prefixes.page_code has FK to page_registry.code, so do not update
    # page_registry.code in place. Insert the new OMS page first, move route prefixes,
    # then delete the old PMS page.
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
        SELECT
          'oms.fsku_rules',
          'FSKU 组合规则',
          'oms',
          2,
          'oms',
          FALSE,
          TRUE,
          TRUE,
          NULL,
          NULL,
          5,
          TRUE
        WHERE EXISTS (
          SELECT 1 FROM page_registry WHERE code = 'oms'
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
        DELETE FROM page_route_prefixes
        WHERE route_prefix = '/oms/fskus'
          AND page_code <> 'pms.fsku_rules'
        """
    )

    op.execute(
        """
        UPDATE page_route_prefixes
           SET page_code = 'oms.fsku_rules',
               route_prefix = '/oms/fskus',
               sort_order = 10,
               is_active = TRUE
         WHERE page_code = 'pms.fsku_rules'
            OR route_prefix = '/pms/fskus'
        """
    )

    op.execute(
        """
        INSERT INTO page_route_prefixes (page_code, route_prefix, sort_order, is_active)
        SELECT 'oms.fsku_rules', '/oms/fskus', 10, TRUE
        WHERE EXISTS (
          SELECT 1 FROM page_registry WHERE code = 'oms.fsku_rules'
        )
          AND NOT EXISTS (
            SELECT 1 FROM page_route_prefixes WHERE route_prefix = '/oms/fskus'
          )
        """
    )

    op.execute(
        """
        DELETE FROM page_registry
        WHERE code = 'pms.fsku_rules'
        """
    )

    # 4. OMS navigation cleanup:
    #    - FSKU rules is the first OMS child page.
    #    - Platform fsku_mapping page is renamed to platform code mapping.
    #    - Retire old fulfillment-order-conversion pages because fulfillment conversion
    #      is no longer an independent business page.
    op.execute(
        """
        UPDATE page_registry
           SET sort_order = 5
         WHERE code = 'oms.fsku_rules'
        """
    )

    op.execute(
        """
        UPDATE page_route_prefixes
           SET sort_order = 5
         WHERE page_code = 'oms.fsku_rules'
           AND route_prefix = '/oms/fskus'
        """
    )

    op.execute(
        """
        UPDATE page_registry
           SET name = '平台编码映射'
         WHERE code IN (
           'oms.pdd.fsku_mapping',
           'oms.taobao.fsku_mapping',
           'oms.jd.fsku_mapping'
         )
        """
    )

    op.execute(
        """
        DELETE FROM page_route_prefixes
        WHERE page_code IN (
          'oms.pdd.fulfillment_order_conversion',
          'oms.taobao.fulfillment_order_conversion',
          'oms.jd.fulfillment_order_conversion'
        )
           OR route_prefix IN (
          '/oms/pdd/fulfillment-order-conversion',
          '/oms/taobao/fulfillment-order-conversion',
          '/oms/jd/fulfillment-order-conversion'
        )
        """
    )

    op.execute(
        """
        DELETE FROM page_registry
        WHERE code IN (
          'oms.pdd.fulfillment_order_conversion',
          'oms.taobao.fulfillment_order_conversion',
          'oms.jd.fulfillment_order_conversion'
        )
        """
    )

    # 5. Rename platform FSKU mapping pages to platform code mapping pages.
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
        VALUES
          ('oms.pdd.code_mapping', '平台编码映射', 'oms.pdd', 3, 'oms', FALSE, TRUE, TRUE, NULL, NULL, 20, TRUE),
          ('oms.taobao.code_mapping', '平台编码映射', 'oms.taobao', 3, 'oms', FALSE, TRUE, TRUE, NULL, NULL, 20, TRUE),
          ('oms.jd.code_mapping', '平台编码映射', 'oms.jd', 3, 'oms', FALSE, TRUE, TRUE, NULL, NULL, 20, TRUE)
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
        DELETE FROM page_route_prefixes
        WHERE route_prefix IN (
          '/oms/pdd/code-mapping',
          '/oms/taobao/code-mapping',
          '/oms/jd/code-mapping'
        )
        """
    )

    op.execute(
        """
        UPDATE page_route_prefixes
           SET page_code = CASE page_code
             WHEN 'oms.pdd.fsku_mapping' THEN 'oms.pdd.code_mapping'
             WHEN 'oms.taobao.fsku_mapping' THEN 'oms.taobao.code_mapping'
             WHEN 'oms.jd.fsku_mapping' THEN 'oms.jd.code_mapping'
             ELSE page_code
           END,
           route_prefix = CASE route_prefix
             WHEN '/oms/pdd/fsku-mapping' THEN '/oms/pdd/code-mapping'
             WHEN '/oms/taobao/fsku-mapping' THEN '/oms/taobao/code-mapping'
             WHEN '/oms/jd/fsku-mapping' THEN '/oms/jd/code-mapping'
             ELSE route_prefix
           END,
           sort_order = CASE route_prefix
             WHEN '/oms/pdd/fsku-mapping' THEN 22
             WHEN '/oms/taobao/fsku-mapping' THEN 32
             WHEN '/oms/jd/fsku-mapping' THEN 42
             ELSE sort_order
           END,
           is_active = TRUE
         WHERE page_code IN (
           'oms.pdd.fsku_mapping',
           'oms.taobao.fsku_mapping',
           'oms.jd.fsku_mapping'
         )
            OR route_prefix IN (
           '/oms/pdd/fsku-mapping',
           '/oms/taobao/fsku-mapping',
           '/oms/jd/fsku-mapping'
         )
        """
    )

    op.execute(
        """
        DELETE FROM page_registry
        WHERE code IN (
          'oms.pdd.fsku_mapping',
          'oms.taobao.fsku_mapping',
          'oms.jd.fsku_mapping'
        )
        """
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.execute("DROP TABLE IF EXISTS oms_order_sku_resolution_components")
    op.execute("DROP TABLE IF EXISTS oms_order_sku_resolution_decisions")

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
        SELECT
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
        WHERE EXISTS (
          SELECT 1 FROM page_registry WHERE code = 'pms'
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
        DELETE FROM page_route_prefixes
        WHERE route_prefix = '/pms/fskus'
          AND page_code <> 'oms.fsku_rules'
        """
    )

    op.execute(
        """
        UPDATE page_route_prefixes
           SET page_code = 'pms.fsku_rules',
               route_prefix = '/pms/fskus',
               sort_order = 10,
               is_active = TRUE
         WHERE page_code = 'oms.fsku_rules'
            OR route_prefix = '/oms/fskus'
        """
    )

    op.execute(
        """
        INSERT INTO page_route_prefixes (page_code, route_prefix, sort_order, is_active)
        SELECT 'pms.fsku_rules', '/pms/fskus', 10, TRUE
        WHERE EXISTS (
          SELECT 1 FROM page_registry WHERE code = 'pms.fsku_rules'
        )
          AND NOT EXISTS (
            SELECT 1 FROM page_route_prefixes WHERE route_prefix = '/pms/fskus'
          )
        """
    )

    op.execute(
        """
        DELETE FROM page_registry
        WHERE code = 'oms.fsku_rules'
        """
    )

    op.execute(
        """
        ALTER TABLE merchant_code_fsku_bindings
        DROP CONSTRAINT IF EXISTS merchant_code_fsku_bindings_oms_fsku_id_fkey
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
          IF to_regclass('public.oms_fsku_components') IS NOT NULL
             AND to_regclass('public.pms_fsku_components') IS NULL THEN
            ALTER TABLE oms_fsku_components RENAME TO pms_fsku_components;
          END IF;

          IF to_regclass('public.oms_fskus') IS NOT NULL
             AND to_regclass('public.pms_fskus') IS NULL THEN
            ALTER TABLE oms_fskus RENAME TO pms_fskus;
          END IF;

          IF to_regclass('public.oms_fskus_id_seq') IS NOT NULL THEN
            ALTER SEQUENCE oms_fskus_id_seq RENAME TO pms_fskus_id_seq;
          END IF;

          IF to_regclass('public.oms_fsku_components_id_seq') IS NOT NULL THEN
            ALTER SEQUENCE oms_fsku_components_id_seq RENAME TO pms_fsku_components_id_seq;
          END IF;
        END $$;
        """
    )

    op.execute(
        """
        ALTER TABLE merchant_code_fsku_bindings
        ADD CONSTRAINT merchant_code_fsku_bindings_pms_fsku_id_fkey
        FOREIGN KEY (fsku_id) REFERENCES pms_fskus(id) ON DELETE RESTRICT
        """
    )
