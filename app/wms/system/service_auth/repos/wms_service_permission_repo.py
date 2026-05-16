# app/wms/system/service_auth/repos/wms_service_permission_repo.py
from __future__ import annotations

from sqlalchemy.orm import Session

from app.wms.system.service_auth.models import (
    WmsServiceCapability,
    WmsServiceClient,
    WmsServicePermission,
)


class WmsServicePermissionRepo:
    """
    WMS 系统间调用权限仓储。

    Boundary:
    - 只读取 wms_service_* 表。
    - 不读取 users / permissions / user_permissions。
    - 不做 HTTP header 解析；header 解析由 deps 层负责。
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def exists_active_permission(
        self,
        *,
        client_code: str,
        capability_code: str,
    ) -> bool:
        row = (
            self.db.query(WmsServicePermission.id)
            .join(WmsServiceClient, WmsServiceClient.id == WmsServicePermission.client_id)
            .join(
                WmsServiceCapability,
                WmsServiceCapability.capability_code == WmsServicePermission.capability_code,
            )
            .filter(WmsServiceClient.client_code == client_code)
            .filter(WmsServiceClient.is_active.is_(True))
            .filter(WmsServiceCapability.is_active.is_(True))
            .filter(WmsServicePermission.capability_code == capability_code)
            .filter(WmsServicePermission.is_active.is_(True))
            .first()
        )
        return row is not None


__all__ = ["WmsServicePermissionRepo"]
