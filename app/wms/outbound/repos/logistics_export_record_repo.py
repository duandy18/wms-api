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


async def _load_export_record_for_update(
    session: AsyncSession,
    *,
    source_ref: str,
) -> dict[str, Any] | None:
    row = (
        await session.execute(
            text(
                """
                SELECT
                  id,
                  source_ref,
                  export_status,
                  logistics_status,
                  logistics_request_id,
                  logistics_request_no,
                  exported_at,
                  last_attempt_at,
                  last_error,
                  updated_at
                FROM wms_logistics_export_records
                WHERE source_ref = :source_ref
                FOR UPDATE
                """
            ),
            {"source_ref": str(source_ref).strip()},
        )
    ).mappings().first()

    return dict(row) if row else None


def _same_logistics_request(
    record: Mapping[str, Any],
    *,
    logistics_request_id: int,
    logistics_request_no: str,
) -> bool:
    return (
        record.get("logistics_request_id") is not None
        and int(record["logistics_request_id"]) == int(logistics_request_id)
        and str(record.get("logistics_request_no") or "") == str(logistics_request_no)
    )


async def apply_logistics_import_success(
    session: AsyncSession,
    *,
    source_ref: str,
    logistics_request_id: int,
    logistics_request_no: str,
) -> dict[str, Any] | None:
    """
    Logistics 成功导入后的 WMS 交接状态回写。

    幂等规则：
    - 未导入：PENDING / FAILED -> EXPORTED / IMPORTED
    - 已导入且 request_id/request_no 相同：允许重复回写
    - 已导入但 request_id/request_no 不同：拒绝，避免错绑
    - CANCELLED：拒绝
    """

    current = await _load_export_record_for_update(session, source_ref=source_ref)
    if current is None:
        return None

    export_status = str(current["export_status"])
    logistics_status = str(current["logistics_status"])

    if export_status == "CANCELLED":
        raise ValueError("logistics_export_record_cancelled")

    if export_status == "EXPORTED":
        if _same_logistics_request(
            current,
            logistics_request_id=int(logistics_request_id),
            logistics_request_no=str(logistics_request_no),
        ):
            row = (
                await session.execute(
                    text(
                        """
                        UPDATE wms_logistics_export_records
                           SET last_attempt_at = now(),
                               updated_at = now()
                         WHERE source_ref = :source_ref
                         RETURNING
                           source_ref,
                           export_status,
                           logistics_status,
                           logistics_request_id,
                           logistics_request_no,
                           exported_at,
                           last_attempt_at,
                           last_error,
                           updated_at
                        """
                    ),
                    {"source_ref": str(source_ref).strip()},
                )
            ).mappings().first()
            return dict(row) if row else None

        raise ValueError("logistics_export_record_already_exported")

    if logistics_status in ("IMPORTED", "IN_PROGRESS", "COMPLETED"):
        raise ValueError("logistics_export_record_invalid_import_transition")

    row = (
        await session.execute(
            text(
                """
                UPDATE wms_logistics_export_records
                   SET export_status = 'EXPORTED',
                       logistics_status = 'IMPORTED',
                       logistics_request_id = :logistics_request_id,
                       logistics_request_no = :logistics_request_no,
                       exported_at = COALESCE(exported_at, now()),
                       last_attempt_at = now(),
                       last_error = NULL,
                       updated_at = now()
                 WHERE source_ref = :source_ref
                 RETURNING
                   source_ref,
                   export_status,
                   logistics_status,
                   logistics_request_id,
                   logistics_request_no,
                   exported_at,
                   last_attempt_at,
                   last_error,
                   updated_at
                """
            ),
            {
                "source_ref": str(source_ref).strip(),
                "logistics_request_id": int(logistics_request_id),
                "logistics_request_no": str(logistics_request_no).strip(),
            },
        )
    ).mappings().first()

    return dict(row) if row else None


async def apply_logistics_import_failure(
    session: AsyncSession,
    *,
    source_ref: str,
    error_message: str,
) -> dict[str, Any] | None:
    """
    Logistics 导入失败后的 WMS 交接状态回写。

    失败只允许发生在尚未成功导入前；
    已 EXPORTED / IMPORTED / IN_PROGRESS / COMPLETED 的记录不允许被失败回写降级。
    """

    current = await _load_export_record_for_update(session, source_ref=source_ref)
    if current is None:
        return None

    export_status = str(current["export_status"])
    logistics_status = str(current["logistics_status"])

    if export_status == "CANCELLED":
        raise ValueError("logistics_export_record_cancelled")

    if export_status == "EXPORTED" or logistics_status in (
        "IMPORTED",
        "IN_PROGRESS",
        "COMPLETED",
    ):
        raise ValueError("logistics_export_record_already_imported")

    row = (
        await session.execute(
            text(
                """
                UPDATE wms_logistics_export_records
                   SET export_status = 'FAILED',
                       logistics_status = 'FAILED',
                       logistics_request_id = NULL,
                       logistics_request_no = NULL,
                       last_attempt_at = now(),
                       last_error = :last_error,
                       updated_at = now()
                 WHERE source_ref = :source_ref
                 RETURNING
                   source_ref,
                   export_status,
                   logistics_status,
                   logistics_request_id,
                   logistics_request_no,
                   exported_at,
                   last_attempt_at,
                   last_error,
                   updated_at
                """
            ),
            {
                "source_ref": str(source_ref).strip(),
                "last_error": str(error_message).strip(),
            },
        )
    ).mappings().first()

    return dict(row) if row else None
