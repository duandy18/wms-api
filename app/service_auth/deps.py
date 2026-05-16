# app/service_auth/deps.py
from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.service_auth.services import WmsServicePermissionService

WMS_SERVICE_CLIENT_HEADER = "X-Service-Client"


def get_wms_service_permission_service(
    db: Session = Depends(get_db),
) -> WmsServicePermissionService:
    return WmsServicePermissionService(db)


def require_wms_service_capability(
    capability_code: str,
) -> Callable[[str | None, WmsServicePermissionService], None]:
    """
    Build a FastAPI dependency for WMS service-to-service capability checks.

    Usage example:
        Depends(require_wms_service_capability("wms.read.warehouses"))

    Boundary:
    - capability_code 由 WMS 路由自己声明，不能由调用方传入。
    - 调用方只通过 X-Service-Client 声明自己是谁。
    - 这不是用户权限校验。
    """

    normalized_capability_code = (capability_code or "").strip()

    def dependency(
        x_service_client: str | None = Header(default=None, alias=WMS_SERVICE_CLIENT_HEADER),
        service: WmsServicePermissionService = Depends(get_wms_service_permission_service),
    ) -> None:
        client_code = (x_service_client or "").strip()
        if not client_code:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="wms_service_client_required",
            )

        if not service.is_allowed(
            client_code=client_code,
            capability_code=normalized_capability_code,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="wms_service_permission_denied",
            )

    return dependency


__all__ = [
    "WMS_SERVICE_CLIENT_HEADER",
    "get_wms_service_permission_service",
    "require_wms_service_capability",
]
