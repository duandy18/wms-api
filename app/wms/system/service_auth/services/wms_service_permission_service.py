# app/wms/system/service_auth/services/wms_service_permission_service.py
from __future__ import annotations

from sqlalchemy.orm import Session

from app.wms.system.service_auth.repos import WmsServicePermissionRepo


class WmsServicePermissionService:
    """
    WMS 本地系统间调用权限校验服务。

    Boundary:
    - 只判断 service client 是否拥有某个 WMS capability。
    - 不读取 users / permissions / user_permissions。
    - 不负责 service client 身份认证；身份认证后续由网关、service token 或签名机制承接。
    """

    def __init__(
        self,
        db: Session,
        repo: WmsServicePermissionRepo | None = None,
    ) -> None:
        self.repo = repo or WmsServicePermissionRepo(db)

    @staticmethod
    def _normalize(value: str | None) -> str:
        return (value or "").strip()

    def is_allowed(self, *, client_code: str | None, capability_code: str | None) -> bool:
        normalized_client_code = self._normalize(client_code)
        normalized_capability_code = self._normalize(capability_code)

        if not normalized_client_code or not normalized_capability_code:
            return False

        return self.repo.exists_active_permission(
            client_code=normalized_client_code,
            capability_code=normalized_capability_code,
        )


__all__ = ["WmsServicePermissionService"]
