# app/integrations/pms/__init__.py
"""
PMS integration boundary.

wms-api is a PMS consumer. PMS owner runtime lives in pms-api.
Consumers outside PMS should depend on this package instead of importing
legacy PMS owner/export services directly.
"""

from app.integrations.pms.factory import (
    create_pms_read_client,
    create_sync_pms_read_client,
    get_pms_client_mode,
)
from app.integrations.pms.http_client import HttpPmsReadClient
from app.integrations.pms.sync_http_client import SyncHttpPmsReadClient

__all__ = [
    "HttpPmsReadClient",
    "SyncHttpPmsReadClient",
    "create_pms_read_client",
    "create_sync_pms_read_client",
    "get_pms_client_mode",
]
