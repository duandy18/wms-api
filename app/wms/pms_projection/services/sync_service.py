# app/wms/pms_projection/services/sync_service.py
# Split note:
# WMS PMS projection 增量同步入口。
# 本服务不直接读取 PMS owner 表；owner 表读取仍集中在 rebuild_service.py，
# 以保持 PR-7A 的 PMS owner 边界守卫不扩大白名单。
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.wms.pms_projection.services.rebuild_service import (
    WmsPmsProjectionRebuildResult,
    WmsPmsProjectionRebuildService,
)


SOURCE_NAME = "pms_owner_updated_at"


@dataclass(frozen=True, slots=True)
class WmsPmsProjectionSyncResult:
    source_name: str
    initialized: bool
    changed_items: int
    previous_source_updated_at: datetime | None
    last_source_updated_at: datetime
    source_items: int
    source_uoms: int
    source_policies: int
    source_sku_codes: int
    source_barcodes: int
    deleted_items: int
    deleted_uoms: int
    deleted_policies: int
    deleted_sku_codes: int
    deleted_barcodes: int


def _epoch() -> datetime:
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _as_datetime(value: object, *, label: str) -> datetime:
    if not isinstance(value, datetime):
        raise RuntimeError(f"{label} must be datetime, got {type(value)!r}")
    return value


def _zero_rebuild_result() -> WmsPmsProjectionRebuildResult:
    return WmsPmsProjectionRebuildResult(
        source_items=0,
        source_uoms=0,
        source_policies=0,
        source_sku_codes=0,
        source_barcodes=0,
        deleted_items=0,
        deleted_uoms=0,
        deleted_policies=0,
        deleted_sku_codes=0,
        deleted_barcodes=0,
    )


class WmsPmsProjectionSyncService:
    """
    WMS PMS projection 增量同步服务。

    第一版语义：
    - 无 cursor：执行 rebuild_all 初始化，然后保存 owner 最大 updated_at；
    - 有 cursor：扫描 owner updated_at > cursor 的 item_id；
    - 对 changed item_id 调用 rebuild_items；
    - 成功后推进 cursor；
    - 失败时 cursor 不前进，只记录 FAILED / last_error / retry_count。
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.rebuild_service = WmsPmsProjectionRebuildService(session)

    async def sync_once(self, *, overlap_seconds: int = 0) -> WmsPmsProjectionSyncResult:
        cursor = await self._load_cursor()
        previous_source_updated_at = (
            _as_datetime(cursor["last_source_updated_at"], label="cursor.last_source_updated_at")
            if cursor is not None
            else None
        )

        try:
            if previous_source_updated_at is None:
                rebuild_result = await self.rebuild_service.rebuild_all()
                latest = await self.rebuild_service.max_owner_source_updated_at()
                last_source_updated_at = latest or _epoch()
                await self._mark_success(last_source_updated_at=last_source_updated_at)
                return self._build_result(
                    initialized=True,
                    changed_items=rebuild_result.source_items,
                    previous_source_updated_at=None,
                    last_source_updated_at=last_source_updated_at,
                    rebuild_result=rebuild_result,
                )

            changed_item_ids = await self.rebuild_service.changed_item_ids_since(
                previous_source_updated_at,
                overlap_seconds=overlap_seconds,
            )
            if not changed_item_ids:
                await self._mark_success(last_source_updated_at=previous_source_updated_at)
                return self._build_result(
                    initialized=False,
                    changed_items=0,
                    previous_source_updated_at=previous_source_updated_at,
                    last_source_updated_at=previous_source_updated_at,
                    rebuild_result=_zero_rebuild_result(),
                )

            rebuild_result = await self.rebuild_service.rebuild_items(changed_item_ids)
            latest = await self.rebuild_service.max_owner_source_updated_at()
            last_source_updated_at = latest or previous_source_updated_at
            if last_source_updated_at < previous_source_updated_at:
                last_source_updated_at = previous_source_updated_at

            await self._mark_success(last_source_updated_at=last_source_updated_at)
            return self._build_result(
                initialized=False,
                changed_items=len(changed_item_ids),
                previous_source_updated_at=previous_source_updated_at,
                last_source_updated_at=last_source_updated_at,
                rebuild_result=rebuild_result,
            )
        except Exception as exc:
            await self._mark_failed(
                last_source_updated_at=previous_source_updated_at or _epoch(),
                error=str(exc),
            )
            raise

    async def _load_cursor(self) -> dict[str, object] | None:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT
                      source_name,
                      last_source_updated_at,
                      last_synced_at,
                      last_status,
                      last_error,
                      retry_count
                    FROM wms_pms_projection_sync_cursors
                    WHERE source_name = :source_name
                    LIMIT 1
                    """
                ),
                {"source_name": SOURCE_NAME},
            )
        ).mappings().first()
        return dict(row) if row is not None else None

    async def _mark_success(self, *, last_source_updated_at: datetime) -> None:
        await self.session.execute(
            text(
                """
                INSERT INTO wms_pms_projection_sync_cursors (
                  source_name,
                  last_source_updated_at,
                  last_synced_at,
                  last_status,
                  last_error,
                  retry_count,
                  created_at,
                  updated_at
                )
                VALUES (
                  :source_name,
                  :last_source_updated_at,
                  now(),
                  'SUCCESS',
                  NULL,
                  0,
                  now(),
                  now()
                )
                ON CONFLICT (source_name) DO UPDATE SET
                  last_source_updated_at = EXCLUDED.last_source_updated_at,
                  last_synced_at = now(),
                  last_status = 'SUCCESS',
                  last_error = NULL,
                  retry_count = 0,
                  updated_at = now()
                """
            ),
            {
                "source_name": SOURCE_NAME,
                "last_source_updated_at": last_source_updated_at,
            },
        )

    async def _mark_failed(self, *, last_source_updated_at: datetime, error: str) -> None:
        await self.session.execute(
            text(
                """
                INSERT INTO wms_pms_projection_sync_cursors (
                  source_name,
                  last_source_updated_at,
                  last_synced_at,
                  last_status,
                  last_error,
                  retry_count,
                  created_at,
                  updated_at
                )
                VALUES (
                  :source_name,
                  :last_source_updated_at,
                  now(),
                  'FAILED',
                  :last_error,
                  1,
                  now(),
                  now()
                )
                ON CONFLICT (source_name) DO UPDATE SET
                  last_synced_at = now(),
                  last_status = 'FAILED',
                  last_error = EXCLUDED.last_error,
                  retry_count = wms_pms_projection_sync_cursors.retry_count + 1,
                  updated_at = now()
                """
            ),
            {
                "source_name": SOURCE_NAME,
                "last_source_updated_at": last_source_updated_at,
                "last_error": error,
            },
        )

    def _build_result(
        self,
        *,
        initialized: bool,
        changed_items: int,
        previous_source_updated_at: datetime | None,
        last_source_updated_at: datetime,
        rebuild_result: WmsPmsProjectionRebuildResult,
    ) -> WmsPmsProjectionSyncResult:
        return WmsPmsProjectionSyncResult(
            source_name=SOURCE_NAME,
            initialized=bool(initialized),
            changed_items=int(changed_items),
            previous_source_updated_at=previous_source_updated_at,
            last_source_updated_at=last_source_updated_at,
            source_items=int(rebuild_result.source_items),
            source_uoms=int(rebuild_result.source_uoms),
            source_policies=int(rebuild_result.source_policies),
            source_sku_codes=int(rebuild_result.source_sku_codes),
            source_barcodes=int(rebuild_result.source_barcodes),
            deleted_items=int(rebuild_result.deleted_items),
            deleted_uoms=int(rebuild_result.deleted_uoms),
            deleted_policies=int(rebuild_result.deleted_policies),
            deleted_sku_codes=int(rebuild_result.deleted_sku_codes),
            deleted_barcodes=int(rebuild_result.deleted_barcodes),
        )
