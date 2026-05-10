# app/integrations/pms/sync_client.py
"""
Synchronous in-process PMS read client.

Current use case:
- legacy synchronous service paths that still use sqlalchemy.orm.Session
- keeps non-PMS domains from importing app.pms.export services directly

Future deployment mode:
- replace this implementation with a synchronous HTTP PMS client behind the
  same consumer-side boundary.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.integrations.pms.contracts import PmsExportSkuCodeResolution
from app.pms.export.sku_codes.services.sku_code_read_service import (
    PmsExportSkuCodeReadService,
)


class SyncInProcessPmsReadClient:
    def __init__(self, session: Session) -> None:
        self.session = session

    def resolve_active_code_for_outbound_default(
        self,
        *,
        code: str,
        enabled_only: bool = True,
    ) -> PmsExportSkuCodeResolution | None:
        return PmsExportSkuCodeReadService(
            self.session
        ).resolve_active_code_for_outbound_default(
            code=str(code),
            enabled_only=bool(enabled_only),
        )


__all__ = ["SyncInProcessPmsReadClient"]
