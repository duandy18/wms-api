# app/pms/fsku/services/fsku_service.py
from __future__ import annotations

from sqlalchemy.orm import Session

from app.pms.fsku.contracts.fsku import FskuDetailOut, FskuListOut
from app.pms.fsku.services.fsku_service_errors import FskuBadInput, FskuConflict, FskuNotFound
from app.pms.fsku.services.fsku_service_read import get_detail as _get_detail
from app.pms.fsku.services.fsku_service_read import list_fskus as _list_fskus
from app.pms.fsku.services.fsku_service_write import (
    create_draft as _create_draft,
)
from app.pms.fsku.services.fsku_service_write import (
    publish as _publish,
)
from app.pms.fsku.services.fsku_service_write import (
    replace_expression_draft as _replace_expression_draft,
)
from app.pms.fsku.services.fsku_service_write import (
    retire as _retire,
)
from app.pms.fsku.services.fsku_service_write import (
    unretire as _unretire,
)
from app.pms.fsku.services.fsku_service_write import (
    update_name as _update_name,
)


class FskuService:
    BadInput = FskuBadInput
    Conflict = FskuConflict
    NotFound = FskuNotFound

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_draft(self, *, name: str, code: str | None, shape: str | None, fsku_expr: str) -> FskuDetailOut:
        return _create_draft(self.db, name=name, code=code, shape=shape, fsku_expr=fsku_expr)

    def list_fskus(
        self,
        *,
        query: str | None = None,
        status: str | None = None,
        store_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> FskuListOut:
        return _list_fskus(self.db, query=query, status=status, store_id=store_id, limit=limit, offset=offset)

    def get_detail(self, fsku_id: int) -> FskuDetailOut | None:
        return _get_detail(self.db, int(fsku_id))

    def update_name(self, *, fsku_id: int, name: str) -> FskuDetailOut:
        return _update_name(self.db, fsku_id=int(fsku_id), name=name)

    def replace_expression_draft(self, *, fsku_id: int, fsku_expr: str) -> FskuDetailOut:
        return _replace_expression_draft(self.db, fsku_id=int(fsku_id), fsku_expr=fsku_expr)

    def publish(self, fsku_id: int) -> FskuDetailOut:
        return _publish(self.db, int(fsku_id))

    def retire(self, fsku_id: int) -> FskuDetailOut:
        return _retire(self.db, int(fsku_id))

    def unretire(self, fsku_id: int) -> FskuDetailOut:
        return _unretire(self.db, int(fsku_id))
