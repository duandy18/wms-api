"""retire cross-domain PMS physical foreign keys

Revision ID: 9b7f2c1d8e44
Revises: a8c1f4e2d9b0
Create Date: 2026-05-11 17:40:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "9b7f2c1d8e44"
down_revision: str | Sequence[str] | None = "a8c1f4e2d9b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# 第七刀边界：
# - 只退 WMS/OMS/Procurement 等业务表指向 PMS owner tables 的跨域物理 FK。
# - 不退 PMS owner 内部 FK：
#   * item_uoms -> items
#   * item_sku_codes -> items
#   * item_barcodes -> items / item_uoms
#   * item_attribute_values -> items
# - 不删除任何标量字段。
# - 强一致责任切换为：
#   HTTP 写入校验 + snapshot 落账 + projection 查询 + reconciliation 对账。
CROSS_DOMAIN_PMS_FKS: tuple[tuple[str, str], ...] = (
    ("oms_fsku_components", "fk_oms_fsku_components_resolved_sku_code"),
    ("count_doc_lines", "fk_count_doc_lines_counted_item_uom_pair"),
    ("inbound_event_lines", "fk_inbound_event_lines_actual_uom"),
    ("inbound_receipt_lines", "fk_inbound_receipt_lines_item_uom"),
    ("manual_outbound_lines", "fk_manual_outbound_lines_item_uom_id"),
    ("oms_fsku_components", "fk_oms_fsku_components_resolved_uom"),
    ("purchase_order_lines", "fk_po_line_purchase_uom"),
    ("wms_inbound_operation_lines", "fk_wms_inbound_operation_lines_actual_item_uom"),
    ("count_doc_lines", "fk_count_doc_lines_item"),
    ("inbound_event_lines", "fk_inbound_event_lines_item"),
    ("inbound_receipt_lines", "fk_inbound_receipt_lines_item"),
    ("lots", "fk_lots_item"),
    ("manual_outbound_lines", "fk_manual_outbound_lines_item_id"),
    ("oms_fsku_components", "fk_oms_fsku_components_resolved_item"),
    ("order_items", "fk_order_items_item"),
    ("purchase_order_lines", "fk_po_line_item"),
    ("stock_ledger", "fk_stock_ledger_item_id"),
    ("stock_snapshots", "stock_snapshots_item_id_fkey"),
    ("stocks_lot", "fk_stocks_lot_item"),
    ("store_items", "store_items_item_id_fkey"),
    ("wms_inbound_operation_lines", "fk_wms_inbound_operation_lines_item"),
)


DOWNGRADE_FK_SQL: tuple[tuple[str, str], ...] = (
    (
        "oms_fsku_components",
        """
        ALTER TABLE public.oms_fsku_components
        ADD CONSTRAINT fk_oms_fsku_components_resolved_sku_code
        FOREIGN KEY (resolved_item_sku_code_id, resolved_item_id)
        REFERENCES public.item_sku_codes(id, item_id)
        ON DELETE RESTRICT
        NOT VALID
        """,
    ),
    (
        "count_doc_lines",
        """
        ALTER TABLE public.count_doc_lines
        ADD CONSTRAINT fk_count_doc_lines_counted_item_uom_pair
        FOREIGN KEY (counted_item_uom_id, item_id)
        REFERENCES public.item_uoms(id, item_id)
        ON DELETE RESTRICT
        NOT VALID
        """,
    ),
    (
        "inbound_event_lines",
        """
        ALTER TABLE public.inbound_event_lines
        ADD CONSTRAINT fk_inbound_event_lines_actual_uom
        FOREIGN KEY (actual_uom_id)
        REFERENCES public.item_uoms(id)
        ON DELETE RESTRICT
        NOT VALID
        """,
    ),
    (
        "inbound_receipt_lines",
        """
        ALTER TABLE public.inbound_receipt_lines
        ADD CONSTRAINT fk_inbound_receipt_lines_item_uom
        FOREIGN KEY (item_uom_id)
        REFERENCES public.item_uoms(id)
        ON DELETE RESTRICT
        NOT VALID
        """,
    ),
    (
        "manual_outbound_lines",
        """
        ALTER TABLE public.manual_outbound_lines
        ADD CONSTRAINT fk_manual_outbound_lines_item_uom_id
        FOREIGN KEY (item_uom_id)
        REFERENCES public.item_uoms(id)
        ON DELETE RESTRICT
        NOT VALID
        """,
    ),
    (
        "oms_fsku_components",
        """
        ALTER TABLE public.oms_fsku_components
        ADD CONSTRAINT fk_oms_fsku_components_resolved_uom
        FOREIGN KEY (resolved_item_uom_id, resolved_item_id)
        REFERENCES public.item_uoms(id, item_id)
        ON DELETE RESTRICT
        NOT VALID
        """,
    ),
    (
        "purchase_order_lines",
        """
        ALTER TABLE public.purchase_order_lines
        ADD CONSTRAINT fk_po_line_purchase_uom
        FOREIGN KEY (purchase_uom_id_snapshot)
        REFERENCES public.item_uoms(id)
        NOT VALID
        """,
    ),
    (
        "wms_inbound_operation_lines",
        """
        ALTER TABLE public.wms_inbound_operation_lines
        ADD CONSTRAINT fk_wms_inbound_operation_lines_actual_item_uom
        FOREIGN KEY (actual_item_uom_id)
        REFERENCES public.item_uoms(id)
        ON DELETE RESTRICT
        NOT VALID
        """,
    ),
    (
        "count_doc_lines",
        """
        ALTER TABLE public.count_doc_lines
        ADD CONSTRAINT fk_count_doc_lines_item
        FOREIGN KEY (item_id)
        REFERENCES public.items(id)
        ON DELETE RESTRICT
        NOT VALID
        """,
    ),
    (
        "inbound_event_lines",
        """
        ALTER TABLE public.inbound_event_lines
        ADD CONSTRAINT fk_inbound_event_lines_item
        FOREIGN KEY (item_id)
        REFERENCES public.items(id)
        ON DELETE RESTRICT
        NOT VALID
        """,
    ),
    (
        "inbound_receipt_lines",
        """
        ALTER TABLE public.inbound_receipt_lines
        ADD CONSTRAINT fk_inbound_receipt_lines_item
        FOREIGN KEY (item_id)
        REFERENCES public.items(id)
        ON DELETE RESTRICT
        NOT VALID
        """,
    ),
    (
        "lots",
        """
        ALTER TABLE public.lots
        ADD CONSTRAINT fk_lots_item
        FOREIGN KEY (item_id)
        REFERENCES public.items(id)
        ON DELETE RESTRICT
        NOT VALID
        """,
    ),
    (
        "manual_outbound_lines",
        """
        ALTER TABLE public.manual_outbound_lines
        ADD CONSTRAINT fk_manual_outbound_lines_item_id
        FOREIGN KEY (item_id)
        REFERENCES public.items(id)
        ON DELETE RESTRICT
        NOT VALID
        """,
    ),
    (
        "oms_fsku_components",
        """
        ALTER TABLE public.oms_fsku_components
        ADD CONSTRAINT fk_oms_fsku_components_resolved_item
        FOREIGN KEY (resolved_item_id)
        REFERENCES public.items(id)
        ON DELETE RESTRICT
        NOT VALID
        """,
    ),
    (
        "order_items",
        """
        ALTER TABLE public.order_items
        ADD CONSTRAINT fk_order_items_item
        FOREIGN KEY (item_id)
        REFERENCES public.items(id)
        ON DELETE RESTRICT
        NOT VALID
        """,
    ),
    (
        "purchase_order_lines",
        """
        ALTER TABLE public.purchase_order_lines
        ADD CONSTRAINT fk_po_line_item
        FOREIGN KEY (item_id)
        REFERENCES public.items(id)
        ON DELETE RESTRICT
        NOT VALID
        """,
    ),
    (
        "stock_ledger",
        """
        ALTER TABLE public.stock_ledger
        ADD CONSTRAINT fk_stock_ledger_item_id
        FOREIGN KEY (item_id)
        REFERENCES public.items(id)
        ON DELETE RESTRICT
        NOT VALID
        """,
    ),
    (
        "stock_snapshots",
        """
        ALTER TABLE public.stock_snapshots
        ADD CONSTRAINT stock_snapshots_item_id_fkey
        FOREIGN KEY (item_id)
        REFERENCES public.items(id)
        NOT VALID
        """,
    ),
    (
        "stocks_lot",
        """
        ALTER TABLE public.stocks_lot
        ADD CONSTRAINT fk_stocks_lot_item
        FOREIGN KEY (item_id)
        REFERENCES public.items(id)
        ON DELETE RESTRICT
        NOT VALID
        """,
    ),
    (
        "store_items",
        """
        ALTER TABLE public.store_items
        ADD CONSTRAINT store_items_item_id_fkey
        FOREIGN KEY (item_id)
        REFERENCES public.items(id)
        ON DELETE RESTRICT
        NOT VALID
        """,
    ),
    (
        "wms_inbound_operation_lines",
        """
        ALTER TABLE public.wms_inbound_operation_lines
        ADD CONSTRAINT fk_wms_inbound_operation_lines_item
        FOREIGN KEY (item_id)
        REFERENCES public.items(id)
        ON DELETE RESTRICT
        NOT VALID
        """,
    ),
)


def _q(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _drop_fk(table_name: str, constraint_name: str) -> None:
    op.execute(
        f"ALTER TABLE public.{_q(table_name)} "
        f"DROP CONSTRAINT IF EXISTS {_q(constraint_name)}"
    )


def _create_fk_if_missing(table_name: str, constraint_name: str, create_sql: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = '{constraint_name}'
              AND conrelid = 'public.{table_name}'::regclass
          ) THEN
            {create_sql};
          END IF;
        END $$;
        """
    )


def upgrade() -> None:
    for table_name, constraint_name in CROSS_DOMAIN_PMS_FKS:
        _drop_fk(table_name, constraint_name)


def downgrade() -> None:
    for table_name, create_sql in DOWNGRADE_FK_SQL:
        constraint_name = create_sql.split("ADD CONSTRAINT", 1)[1].split()[0]
        _create_fk_if_missing(table_name, constraint_name, create_sql)
