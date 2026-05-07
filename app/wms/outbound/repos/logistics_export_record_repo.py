# app/wms/outbound/repos/logistics_export_record_repo.py
from __future__ import annotations

import json
from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _json_snapshot(value: Mapping[str, Any] | None) -> str:
    if not value:
        return "{}"
    return json.dumps(value, ensure_ascii=False, default=str)


async def upsert_pending_logistics_export_record(
    session: AsyncSession,
    *,
    source_doc_type: str,
    source_doc_id: int,
    source_doc_no: str,
    source_ref: str,
    source_snapshot: Mapping[str, Any] | None = None,
) -> None:
    """
    幂等写入 WMS -> Logistics 待交接记录。

    已进入 EXPORTED / IMPORTED / IN_PROGRESS / COMPLETED 的记录不被回退；
    FAILED / CANCELLED 以外的未完成状态可回到 PENDING，供后续导入接口读取。
    """

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
              source_snapshot,
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
              CAST(:source_snapshot AS jsonb),
              NULL,
              now(),
              now()
            )
            ON CONFLICT (source_doc_type, source_doc_id) DO UPDATE
               SET source_doc_no = EXCLUDED.source_doc_no,
                   source_ref = EXCLUDED.source_ref,
                   source_snapshot = EXCLUDED.source_snapshot,
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
            """
        ),
        {
            "source_doc_type": str(source_doc_type),
            "source_doc_id": int(source_doc_id),
            "source_doc_no": str(source_doc_no).strip(),
            "source_ref": str(source_ref).strip(),
            "source_snapshot": _json_snapshot(source_snapshot),
        },
    )
