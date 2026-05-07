"""add wms logistics handoff payloads

Revision ID: bf9a287b97de
Revises: 7abe99f04b00
Create Date: 2026-05-07 21:49:22.376521

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "bf9a287b97de"
down_revision: Union[str, Sequence[str], None] = "7abe99f04b00"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PAYLOAD_TABLE = "wms_logistics_handoff_payloads"
EXPORT_TABLE = "wms_logistics_export_records"


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        PAYLOAD_TABLE,
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("export_record_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "source_system",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'WMS'"),
            comment="来源系统，当前固定 WMS",
        ),
        sa.Column(
            "request_source",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'API_IMPORT'"),
            comment="Logistics 请求来源，当前固定 API_IMPORT",
        ),
        sa.Column(
            "source_doc_type",
            sa.String(length=32),
            nullable=False,
            comment="WMS 来源单据类型：ORDER_OUTBOUND / MANUAL_OUTBOUND",
        ),
        sa.Column(
            "source_doc_id",
            sa.BigInteger(),
            nullable=False,
            comment="WMS 来源单据主键：orders.id 或 manual_outbound_docs.id",
        ),
        sa.Column(
            "source_doc_no",
            sa.String(length=128),
            nullable=False,
            comment="WMS 来源单据展示号：平台订单号或手工出库单号",
        ),
        sa.Column(
            "source_ref",
            sa.String(length=192),
            nullable=False,
            comment="WMS 到 Logistics 的稳定幂等键",
        ),
        sa.Column(
            "platform",
            sa.String(length=32),
            nullable=True,
            comment="平台：PDD / TAOBAO / JD；手工出库为空",
        ),
        sa.Column(
            "store_code",
            sa.String(length=64),
            nullable=True,
            comment="店铺编码；手工出库为空",
        ),
        sa.Column(
            "order_ref",
            sa.String(length=128),
            nullable=True,
            comment="订单物流引用，如 ORD:PDD:STORE:EXT_ORDER_NO；手工出库可为空",
        ),
        sa.Column(
            "ext_order_no",
            sa.String(length=128),
            nullable=True,
            comment="平台外部订单号；手工出库为空",
        ),
        sa.Column(
            "warehouse_id",
            sa.Integer(),
            nullable=True,
            comment="WMS 出库仓库 ID 快照",
        ),
        sa.Column(
            "warehouse_name_snapshot",
            sa.String(length=100),
            nullable=True,
            comment="WMS 出库仓库名称快照",
        ),
        sa.Column(
            "receiver_name",
            sa.String(length=128),
            nullable=True,
            comment="收件人姓名快照",
        ),
        sa.Column(
            "receiver_phone",
            sa.String(length=64),
            nullable=True,
            comment="收件人电话快照",
        ),
        sa.Column(
            "receiver_province",
            sa.String(length=64),
            nullable=True,
            comment="收件省份快照",
        ),
        sa.Column(
            "receiver_city",
            sa.String(length=64),
            nullable=True,
            comment="收件城市快照",
        ),
        sa.Column(
            "receiver_district",
            sa.String(length=64),
            nullable=True,
            comment="收件区县快照",
        ),
        sa.Column(
            "receiver_address",
            sa.String(length=255),
            nullable=True,
            comment="收件详细地址快照",
        ),
        sa.Column(
            "receiver_postcode",
            sa.String(length=32),
            nullable=True,
            comment="收件邮编快照",
        ),
        sa.Column(
            "outbound_event_id",
            sa.Integer(),
            nullable=True,
            comment="触发本次交接的 WMS OUTBOUND COMMIT 事件 ID",
        ),
        sa.Column(
            "outbound_source_ref",
            sa.String(length=128),
            nullable=True,
            comment="WMS 出库事件 source_ref",
        ),
        sa.Column(
            "outbound_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="WMS 库存出库完成时间，非物流发货完成时间",
        ),
        sa.Column(
            "shipment_items",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="WMS 已出库商品行快照，供 Logistics 创建发货请求与人工规划包裹使用",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_wms_logistics_handoff_payloads"),
        sa.ForeignKeyConstraint(
            ["export_record_id"],
            [f"{EXPORT_TABLE}.id"],
            name="fk_wms_logistics_handoff_payloads_export_record",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "export_record_id",
            name="uq_wms_logistics_handoff_payloads_export_record_id",
        ),
        sa.UniqueConstraint(
            "source_ref",
            name="uq_wms_logistics_handoff_payloads_source_ref",
        ),
        sa.CheckConstraint(
            "source_system = 'WMS'",
            name="ck_wms_logistics_handoff_payloads_source_system",
        ),
        sa.CheckConstraint(
            "request_source = 'API_IMPORT'",
            name="ck_wms_logistics_handoff_payloads_request_source",
        ),
        sa.CheckConstraint(
            "source_doc_type IN ('ORDER_OUTBOUND', 'MANUAL_OUTBOUND')",
            name="ck_wms_logistics_handoff_payloads_doc_type",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(shipment_items) = 'array'",
            name="ck_wms_logistics_handoff_payloads_shipment_items_array",
        ),
    )

    op.create_index(
        "ix_wms_logistics_handoff_payloads_doc",
        PAYLOAD_TABLE,
        ["source_doc_type", "source_doc_id"],
    )
    op.create_index(
        "ix_wms_logistics_handoff_payloads_platform_store",
        PAYLOAD_TABLE,
        ["platform", "store_code"],
    )
    op.create_index(
        "ix_wms_logistics_handoff_payloads_warehouse_id",
        PAYLOAD_TABLE,
        ["warehouse_id"],
    )
    op.create_index(
        "ix_wms_logistics_handoff_payloads_outbound_event_id",
        PAYLOAD_TABLE,
        ["outbound_event_id"],
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_wms_logistics_handoff_payloads_touch_updated_at()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          NEW.updated_at := now();
          RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_wms_logistics_handoff_payloads_updated_at
        BEFORE UPDATE ON wms_logistics_handoff_payloads
        FOR EACH ROW
        EXECUTE FUNCTION trg_wms_logistics_handoff_payloads_touch_updated_at()
        """
    )

    # 一次性历史迁移：
    # - 旧 source_snapshot 只用于本 migration 的历史数据搬迁；
    # - 正式运行合同从本迁移完成后改为 payload 表；
    # - 搬迁完成后立即删除 source_snapshot，避免形成长期灰色合同。
    op.execute(
        """
        WITH base AS (
          SELECT
            r.id AS export_record_id,
            r.source_doc_type,
            r.source_doc_id,
            r.source_doc_no,
            r.source_ref,
            r.created_at,
            r.updated_at,
            r.source_snapshot,

            o.platform,
            o.store_code,
            o.ext_order_no,
            o.buyer_name,
            o.buyer_phone,

            oa.receiver_name AS order_receiver_name,
            oa.receiver_phone AS order_receiver_phone,
            oa.province AS order_receiver_province,
            oa.city AS order_receiver_city,
            oa.district AS order_receiver_district,
            oa.detail AS order_receiver_address,
            oa.zipcode AS order_receiver_postcode,

            ofu.actual_warehouse_id AS order_actual_warehouse_id,
            ofu.planned_warehouse_id AS order_planned_warehouse_id,
            ofu.outbound_completed_at AS order_outbound_completed_at,

            md.warehouse_id AS manual_warehouse_id,
            md.doc_no AS manual_doc_no,
            md.recipient_name AS manual_recipient_name,

            COALESCE(
              CASE
                WHEN (r.source_snapshot ->> 'wms_event_id') ~ '^[0-9]+$'
                  THEN (r.source_snapshot ->> 'wms_event_id')::integer
                ELSE NULL
              END,
              latest_event.id
            ) AS outbound_event_id
          FROM wms_logistics_export_records r
          LEFT JOIN orders o
            ON r.source_doc_type = 'ORDER_OUTBOUND'
           AND o.id = r.source_doc_id
          LEFT JOIN order_address oa
            ON oa.order_id = o.id
          LEFT JOIN order_fulfillment ofu
            ON ofu.order_id = o.id
          LEFT JOIN manual_outbound_docs md
            ON r.source_doc_type = 'MANUAL_OUTBOUND'
           AND md.id = r.source_doc_id
          LEFT JOIN LATERAL (
            SELECT e.id
            FROM wms_events e
            WHERE e.event_type = 'OUTBOUND'
              AND e.event_kind = 'COMMIT'
              AND e.status = 'COMMITTED'
              AND (
                (
                  r.source_doc_type = 'ORDER_OUTBOUND'
                  AND o.id IS NOT NULL
                  AND e.source_type = 'ORDER'
                  AND e.source_ref = ('ORD:' || UPPER(o.platform) || ':' || o.store_code || ':' || o.ext_order_no)
                )
                OR
                (
                  r.source_doc_type = 'MANUAL_OUTBOUND'
                  AND md.id IS NOT NULL
                  AND e.source_type = 'MANUAL'
                  AND e.source_ref = md.doc_no
                )
              )
            ORDER BY e.occurred_at DESC, e.id DESC
            LIMIT 1
          ) latest_event ON TRUE
        ),
        enriched AS (
          SELECT
            b.*,
            e.source_ref AS outbound_source_ref,
            e.occurred_at AS event_occurred_at,
            e.warehouse_id AS event_warehouse_id,

            COALESCE(
              e.warehouse_id,
              b.order_actual_warehouse_id,
              b.order_planned_warehouse_id,
              b.manual_warehouse_id,
              CASE
                WHEN (b.source_snapshot ->> 'warehouse_id') ~ '^[0-9]+$'
                  THEN (b.source_snapshot ->> 'warehouse_id')::integer
                ELSE NULL
              END
            ) AS resolved_warehouse_id,

            COALESCE(
              e.occurred_at,
              b.order_outbound_completed_at,
              CASE
                WHEN NULLIF(b.source_snapshot ->> 'occurred_at', '') IS NOT NULL
                  THEN NULLIF(b.source_snapshot ->> 'occurred_at', '')::timestamptz
                ELSE NULL
              END
            ) AS resolved_outbound_completed_at
          FROM base b
          LEFT JOIN wms_events e
            ON e.id = b.outbound_event_id
        ),
        shipment_item_rows AS (
          SELECT
            e.export_record_id,
            COALESCE(
              jsonb_agg(
                jsonb_build_object(
                  'source_line_type',
                    CASE
                      WHEN l.order_line_id IS NOT NULL THEN 'ORDER_LINE'
                      WHEN l.manual_doc_line_id IS NOT NULL THEN 'MANUAL_OUTBOUND_LINE'
                      ELSE 'UNKNOWN'
                    END,
                  'source_line_id', COALESCE(l.order_line_id, l.manual_doc_line_id),
                  'source_line_no', l.ref_line,
                  'item_id', l.item_id,
                  'item_sku_snapshot', l.item_sku_snapshot,
                  'item_name_snapshot', l.item_name_snapshot,
                  'item_spec_snapshot', l.item_spec_snapshot,
                  'qty_outbound', l.qty_outbound
                )
                ORDER BY l.ref_line ASC, l.id ASC
              ) FILTER (WHERE l.id IS NOT NULL),
              '[]'::jsonb
            ) AS shipment_items
          FROM enriched e
          LEFT JOIN outbound_event_lines l
            ON l.event_id = e.outbound_event_id
          GROUP BY e.export_record_id
        )
        INSERT INTO wms_logistics_handoff_payloads (
          export_record_id,
          source_system,
          request_source,
          source_doc_type,
          source_doc_id,
          source_doc_no,
          source_ref,
          platform,
          store_code,
          order_ref,
          ext_order_no,
          warehouse_id,
          warehouse_name_snapshot,
          receiver_name,
          receiver_phone,
          receiver_province,
          receiver_city,
          receiver_district,
          receiver_address,
          receiver_postcode,
          outbound_event_id,
          outbound_source_ref,
          outbound_completed_at,
          shipment_items,
          created_at,
          updated_at
        )
        SELECT
          e.export_record_id,
          'WMS',
          'API_IMPORT',
          e.source_doc_type,
          e.source_doc_id,
          e.source_doc_no,
          e.source_ref,
          CASE
            WHEN e.source_doc_type = 'ORDER_OUTBOUND' THEN e.platform
            ELSE NULL
          END AS platform,
          CASE
            WHEN e.source_doc_type = 'ORDER_OUTBOUND' THEN e.store_code
            ELSE NULL
          END AS store_code,
          CASE
            WHEN e.source_doc_type = 'ORDER_OUTBOUND'
             AND e.platform IS NOT NULL
             AND e.store_code IS NOT NULL
             AND e.ext_order_no IS NOT NULL
            THEN 'ORD:' || UPPER(e.platform) || ':' || e.store_code || ':' || e.ext_order_no
            ELSE NULL
          END AS order_ref,
          CASE
            WHEN e.source_doc_type = 'ORDER_OUTBOUND' THEN e.ext_order_no
            ELSE NULL
          END AS ext_order_no,
          e.resolved_warehouse_id,
          w.name AS warehouse_name_snapshot,
          CASE
            WHEN e.source_doc_type = 'ORDER_OUTBOUND'
              THEN COALESCE(e.order_receiver_name, e.buyer_name)
            ELSE e.manual_recipient_name
          END AS receiver_name,
          CASE
            WHEN e.source_doc_type = 'ORDER_OUTBOUND'
              THEN COALESCE(e.order_receiver_phone, e.buyer_phone)
            ELSE NULL
          END AS receiver_phone,
          CASE
            WHEN e.source_doc_type = 'ORDER_OUTBOUND' THEN e.order_receiver_province
            ELSE NULL
          END AS receiver_province,
          CASE
            WHEN e.source_doc_type = 'ORDER_OUTBOUND' THEN e.order_receiver_city
            ELSE NULL
          END AS receiver_city,
          CASE
            WHEN e.source_doc_type = 'ORDER_OUTBOUND' THEN e.order_receiver_district
            ELSE NULL
          END AS receiver_district,
          CASE
            WHEN e.source_doc_type = 'ORDER_OUTBOUND' THEN e.order_receiver_address
            ELSE NULL
          END AS receiver_address,
          CASE
            WHEN e.source_doc_type = 'ORDER_OUTBOUND' THEN e.order_receiver_postcode
            ELSE NULL
          END AS receiver_postcode,
          e.outbound_event_id,
          e.outbound_source_ref,
          e.resolved_outbound_completed_at,
          COALESCE(sir.shipment_items, '[]'::jsonb),
          e.created_at,
          e.updated_at
        FROM enriched e
        LEFT JOIN warehouses w
          ON w.id = e.resolved_warehouse_id
        LEFT JOIN shipment_item_rows sir
          ON sir.export_record_id = e.export_record_id
        ON CONFLICT (export_record_id) DO NOTHING
        """
    )

    op.drop_column(EXPORT_TABLE, "source_snapshot")


def downgrade() -> None:
    """Downgrade schema."""

    op.add_column(
        EXPORT_TABLE,
        sa.Column(
            "source_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="创建交接记录时的 WMS 来源快照",
        ),
    )

    op.execute(
        """
        UPDATE wms_logistics_export_records r
           SET source_snapshot = jsonb_build_object(
                 'source_system', p.source_system,
                 'request_source', p.request_source,
                 'wms_event_id', p.outbound_event_id,
                 'wms_source_ref', p.outbound_source_ref,
                 'warehouse_id', p.warehouse_id,
                 'occurred_at', p.outbound_completed_at,
                 'lines', p.shipment_items
               )
          FROM wms_logistics_handoff_payloads p
         WHERE p.export_record_id = r.id
        """
    )

    op.execute(
        "DROP TRIGGER IF EXISTS trg_wms_logistics_handoff_payloads_updated_at "
        "ON wms_logistics_handoff_payloads"
    )
    op.execute("DROP FUNCTION IF EXISTS trg_wms_logistics_handoff_payloads_touch_updated_at")

    op.drop_index("ix_wms_logistics_handoff_payloads_outbound_event_id", table_name=PAYLOAD_TABLE)
    op.drop_index("ix_wms_logistics_handoff_payloads_warehouse_id", table_name=PAYLOAD_TABLE)
    op.drop_index("ix_wms_logistics_handoff_payloads_platform_store", table_name=PAYLOAD_TABLE)
    op.drop_index("ix_wms_logistics_handoff_payloads_doc", table_name=PAYLOAD_TABLE)
    op.drop_table(PAYLOAD_TABLE)
