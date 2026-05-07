# app/wms/outbound/repos/logistics_export_record_repo.py
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Mapping, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _json_array(value: Sequence[Mapping[str, Any]] | None) -> str:
    if not value:
        return "[]"
    return json.dumps(list(value), ensure_ascii=False, default=str)


async def upsert_pending_logistics_export_record(
    session: AsyncSession,
    *,
    source_doc_type: str,
    source_doc_id: int,
    source_doc_no: str,
    source_ref: str,
) -> int:
    """
    幂等写入 WMS -> Logistics 待交接状态记录。

    本函数只写状态表 wms_logistics_export_records。
    发货请求结构化数据必须写入 wms_logistics_handoff_payloads。

    已进入 EXPORTED / IMPORTED / IN_PROGRESS / COMPLETED 的记录不被回退；
    FAILED / CANCELLED 以外的未完成状态可回到 PENDING，供后续导入接口读取。
    """

    row = (
        await session.execute(
            text(
                """
                INSERT INTO wms_logistics_export_records (
                  source_doc_type,
                  source_doc_id,
                  source_doc_no,
                  source_ref,
                  export_status,
                  logistics_status,
                  last_error,
                  created_at,
                  updated_at
                )
                VALUES (
                  :source_doc_type,
                  :source_doc_id,
                  :source_doc_no,
                  :source_ref,
                  'PENDING',
                  'NOT_IMPORTED',
                  NULL,
                  now(),
                  now()
                )
                ON CONFLICT (source_doc_type, source_doc_id) DO UPDATE
                   SET source_doc_no = EXCLUDED.source_doc_no,
                       source_ref = EXCLUDED.source_ref,
                       export_status = CASE
                           WHEN wms_logistics_export_records.export_status = 'EXPORTED'
                             THEN wms_logistics_export_records.export_status
                           ELSE 'PENDING'
                       END,
                       logistics_status = CASE
                           WHEN wms_logistics_export_records.logistics_status IN ('IMPORTED', 'IN_PROGRESS', 'COMPLETED')
                             THEN wms_logistics_export_records.logistics_status
                           ELSE 'NOT_IMPORTED'
                       END,
                       last_error = CASE
                           WHEN wms_logistics_export_records.export_status = 'EXPORTED'
                             THEN wms_logistics_export_records.last_error
                           ELSE NULL
                       END,
                       updated_at = now()
                RETURNING id
                """
            ),
            {
                "source_doc_type": str(source_doc_type),
                "source_doc_id": int(source_doc_id),
                "source_doc_no": str(source_doc_no).strip(),
                "source_ref": str(source_ref).strip(),
            },
        )
    ).scalar_one()

    return int(row)


async def upsert_logistics_handoff_payload(
    session: AsyncSession,
    *,
    export_record_id: int,
    source_doc_type: str,
    source_doc_id: int,
    source_doc_no: str,
    source_ref: str,
    platform: str | None,
    store_code: str | None,
    order_ref: str | None,
    ext_order_no: str | None,
    warehouse_id: int | None,
    warehouse_name_snapshot: str | None,
    receiver_name: str | None,
    receiver_phone: str | None,
    receiver_province: str | None,
    receiver_city: str | None,
    receiver_district: str | None,
    receiver_address: str | None,
    receiver_postcode: str | None,
    outbound_event_id: int | None,
    outbound_source_ref: str | None,
    outbound_completed_at: datetime | None,
    shipment_items: Sequence[Mapping[str, Any]] | None,
) -> None:
    """
    幂等写入 WMS -> Logistics 交接数据 payload。

    本表是 Logistics 创建发货请求的数据源。
    不使用旧快照字段，不做 JSON 内部私有字段兜底。
    """

    await session.execute(
        text(
            """
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
            VALUES (
              :export_record_id,
              'WMS',
              'API_IMPORT',
              :source_doc_type,
              :source_doc_id,
              :source_doc_no,
              :source_ref,
              :platform,
              :store_code,
              :order_ref,
              :ext_order_no,
              :warehouse_id,
              :warehouse_name_snapshot,
              :receiver_name,
              :receiver_phone,
              :receiver_province,
              :receiver_city,
              :receiver_district,
              :receiver_address,
              :receiver_postcode,
              :outbound_event_id,
              :outbound_source_ref,
              :outbound_completed_at,
              CAST(:shipment_items AS jsonb),
              now(),
              now()
            )
            ON CONFLICT (export_record_id) DO UPDATE
               SET source_doc_type = EXCLUDED.source_doc_type,
                   source_doc_id = EXCLUDED.source_doc_id,
                   source_doc_no = EXCLUDED.source_doc_no,
                   source_ref = EXCLUDED.source_ref,
                   platform = EXCLUDED.platform,
                   store_code = EXCLUDED.store_code,
                   order_ref = EXCLUDED.order_ref,
                   ext_order_no = EXCLUDED.ext_order_no,
                   warehouse_id = EXCLUDED.warehouse_id,
                   warehouse_name_snapshot = EXCLUDED.warehouse_name_snapshot,
                   receiver_name = EXCLUDED.receiver_name,
                   receiver_phone = EXCLUDED.receiver_phone,
                   receiver_province = EXCLUDED.receiver_province,
                   receiver_city = EXCLUDED.receiver_city,
                   receiver_district = EXCLUDED.receiver_district,
                   receiver_address = EXCLUDED.receiver_address,
                   receiver_postcode = EXCLUDED.receiver_postcode,
                   outbound_event_id = EXCLUDED.outbound_event_id,
                   outbound_source_ref = EXCLUDED.outbound_source_ref,
                   outbound_completed_at = EXCLUDED.outbound_completed_at,
                   shipment_items = EXCLUDED.shipment_items,
                   updated_at = now()
            """
        ),
        {
            "export_record_id": int(export_record_id),
            "source_doc_type": str(source_doc_type),
            "source_doc_id": int(source_doc_id),
            "source_doc_no": str(source_doc_no).strip(),
            "source_ref": str(source_ref).strip(),
            "platform": platform,
            "store_code": store_code,
            "order_ref": order_ref,
            "ext_order_no": ext_order_no,
            "warehouse_id": int(warehouse_id) if warehouse_id is not None else None,
            "warehouse_name_snapshot": warehouse_name_snapshot,
            "receiver_name": receiver_name,
            "receiver_phone": receiver_phone,
            "receiver_province": receiver_province,
            "receiver_city": receiver_city,
            "receiver_district": receiver_district,
            "receiver_address": receiver_address,
            "receiver_postcode": receiver_postcode,
            "outbound_event_id": int(outbound_event_id) if outbound_event_id is not None else None,
            "outbound_source_ref": outbound_source_ref,
            "outbound_completed_at": outbound_completed_at,
            "shipment_items": _json_array(shipment_items),
        },
    )
