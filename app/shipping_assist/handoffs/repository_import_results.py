
# app/shipping_assist/handoffs/repository_import_results.py
#
# 分拆说明：
# - 本文件承载独立 Logistics 导入结果回写；
# - 写入对象是 wms_logistics_export_records；
# - 这是跨系统交接资源状态，不再归属 WMS outbound router。
from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


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
