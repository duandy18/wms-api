# app/oms/fulfillment_projection/services/fulfillment_projection_service.py
from __future__ import annotations

import os
import time
from collections.abc import Callable, Coroutine
from typing import Any

from sqlalchemy.orm import Session

from app.db.session import AsyncSessionLocal
from app.integrations.oms.projection_sync import (
    SYNC_VERSION,
    OmsFulfillmentProjectionSyncResult,
    sync_oms_fulfillment_projection_once,
)
from app.oms.fulfillment_projection.contracts.fulfillment_projection import (
    OmsProjectionPlatform,
    OmsProjectionResource,
)
from app.oms.fulfillment_projection.repos.fulfillment_projection_repo import (
    RESOURCE_ORDER,
    SYNC_RESOURCE,
    OmsFulfillmentProjectionRepo,
)

SyncCallable = Callable[..., Coroutine[Any, Any, OmsFulfillmentProjectionSyncResult]]


class OmsFulfillmentProjectionService:
    """
    WMS-local operations for OMS fulfillment projection.

    Boundary:
    - Reads WMS-owned OMS projection tables and WMS sync-run logs only.
    - Triggers projection_sync, which reads oms-api read-v1 HTTP output.
    - Does not manage OMS authorization clients or secrets.
    - Must not read or write OMS owner tables.
    """

    def __init__(
        self,
        db: Session,
        *,
        sync_callable: SyncCallable = sync_oms_fulfillment_projection_once,
    ) -> None:
        self.db = db
        self.repo = OmsFulfillmentProjectionRepo(db)
        self._sync_callable = sync_callable

    @staticmethod
    def _safe_limit(value: int, *, default: int = 50, max_value: int = 500) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = default
        return max(1, min(number, max_value))

    @staticmethod
    def _safe_offset(value: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = 0
        return max(0, number)

    @staticmethod
    def _oms_api_base_url_snapshot() -> str | None:
        value = (os.getenv("OMS_API_BASE_URL") or "").strip().rstrip("/")
        return value or None

    @staticmethod
    def _oms_api_token_configured() -> bool:
        return bool((os.getenv("OMS_API_TOKEN") or "").strip())

    def get_status(self) -> dict[str, Any]:
        latest_run = self.repo.latest_sync_run()
        resources: list[dict[str, Any]] = []

        for resource in RESOURCE_ORDER:
            cfg = self.repo.config(resource)
            stats = self.repo.resource_stats(cfg)
            resources.append(
                {
                    "resource": resource,
                    "table_name": cfg.table_name,
                    "row_count": stats["row_count"],
                    "max_synced_at": stats["max_synced_at"],
                    "last_sync_run": latest_run,
                }
            )

        return {
            "oms_api_base_url_configured": self._oms_api_base_url_snapshot() is not None,
            "oms_api_token_configured": self._oms_api_token_configured(),
            "resources": resources,
        }

    def list_projection(
        self,
        *,
        resource: OmsProjectionResource,
        limit: int,
        offset: int,
        q: str | None = None,
    ) -> dict[str, Any]:
        cfg = self.repo.config(resource)
        safe_limit = self._safe_limit(limit)
        safe_offset = self._safe_offset(offset)

        return self.repo.list_projection_rows(
            cfg=cfg,
            limit=safe_limit,
            offset=safe_offset,
            q=q,
        )

    async def sync_fulfillment_ready_orders(
        self,
        *,
        platform: OmsProjectionPlatform | None,
        store_code: str | None,
        limit: int,
        triggered_by_user_id: int | None,
    ) -> dict[str, Any]:
        safe_limit = self._safe_limit(limit, default=200, max_value=500)
        normalized_store_code = (store_code or "").strip() or None
        started_monotonic = time.monotonic()

        run_id = self.repo.create_sync_run(
            platform=platform,
            store_code=normalized_store_code,
            triggered_by_user_id=triggered_by_user_id,
            oms_api_base_url_snapshot=self._oms_api_base_url_snapshot(),
            sync_version=SYNC_VERSION,
        )

        try:
            async with AsyncSessionLocal() as async_session:
                result = await self._sync_callable(
                    async_session,
                    platform=platform,
                    store_code=normalized_store_code,
                    limit=safe_limit,
                )
                await async_session.commit()

            duration_ms = int((time.monotonic() - started_monotonic) * 1000)
            return self.repo.finish_sync_run(
                run_id=run_id,
                status="SUCCESS",
                duration_ms=duration_ms,
                fetched=result.fetched,
                upserted_orders=result.upserted_orders,
                upserted_lines=result.upserted_lines,
                upserted_components=result.upserted_components,
                pages=result.pages,
                error_message=None,
            )
        except Exception as exc:
            duration_ms = int((time.monotonic() - started_monotonic) * 1000)
            self.repo.finish_sync_run(
                run_id=run_id,
                status="FAILED",
                duration_ms=duration_ms,
                error_message=str(exc),
            )
            raise

    def list_sync_runs(
        self,
        *,
        platform: OmsProjectionPlatform | None,
        limit: int,
    ) -> dict[str, Any]:
        safe_limit = self._safe_limit(limit, default=20, max_value=100)

        return {
            "resource": SYNC_RESOURCE,
            "platform": platform,
            "limit": safe_limit,
            "runs": self.repo.list_sync_runs(platform=platform, limit=safe_limit),
        }

    def check_projection(
        self,
        *,
        resource: OmsProjectionResource,
        limit: int = 200,
    ) -> dict[str, Any]:
        self.repo.config(resource)
        safe_limit = self._safe_limit(limit, default=200, max_value=1000)

        if resource == "orders":
            rows = self.repo.check_orders(safe_limit)
        elif resource == "lines":
            rows = self.repo.check_lines(safe_limit)
        elif resource == "components":
            rows = self.repo.check_components(safe_limit)
        else:
            raise ValueError(f"unsupported OMS projection resource: {resource}")

        return {
            "resource": resource,
            "ok": len(rows) == 0,
            "issue_count": len(rows),
            "issues": rows,
        }


__all__ = ["OmsFulfillmentProjectionService"]
