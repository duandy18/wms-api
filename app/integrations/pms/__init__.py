# app/integrations/pms/__init__.py
"""
PMS integration boundary.

Consumers outside PMS should depend on this package instead of importing
PMS export services directly.
"""

from app.integrations.pms.factory import (
    create_pms_read_client,
    get_pms_client_mode,
)
from app.integrations.pms.http_client import HttpPmsReadClient
from app.integrations.pms.inprocess_client import InProcessPmsReadClient

__all__ = [
    "HttpPmsReadClient",
    "InProcessPmsReadClient",
    "create_pms_read_client",
    "get_pms_client_mode",
]
