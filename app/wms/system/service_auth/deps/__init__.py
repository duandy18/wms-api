# app/wms/system/service_auth/deps/__init__.py
from __future__ import annotations

from app.wms.system.service_auth.deps.wms_service_permission_deps import (
    WMS_SERVICE_CLIENT_HEADER,
    get_wms_service_permission_service,
    require_wms_service_capability,
)

__all__ = [
    "WMS_SERVICE_CLIENT_HEADER",
    "get_wms_service_permission_service",
    "require_wms_service_capability",
]
