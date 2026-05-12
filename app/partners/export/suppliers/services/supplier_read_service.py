# app/partners/export/suppliers/services/supplier_read_service.py
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.partners.export.suppliers.contracts.supplier_basic import SupplierBasic


class SupplierReadService:
    """
    Partners export supplier read service.

    Boundary:
    - Read WMS local PMS supplier projection only.
    - Do not read legacy suppliers owner table.
    - Do not carry supplier_contacts / owner write semantics.
    - Sync and async APIs are both kept because routers use Session and procurement uses AsyncSession.
    """

    def __init__(self, db: Session | AsyncSession) -> None:
        self.db = db

    def _require_sync_db(self) -> Session:
        if isinstance(self.db, AsyncSession):
            raise TypeError("SupplierReadService sync API requires Session, got AsyncSession")
        if not isinstance(self.db, Session):
            raise TypeError(f"SupplierReadService expected Session, got {type(self.db)!r}")
        return self.db

    def _require_async_db(self) -> AsyncSession:
        if not isinstance(self.db, AsyncSession):
            raise TypeError("SupplierReadService async API requires AsyncSession")
        return self.db

    @staticmethod
    def _query_sql(*, active: Optional[bool], q: Optional[str]) -> tuple[str, dict[str, object]]:
        where: list[str] = []
        params: dict[str, object] = {}

        if active is not None:
            where.append("active = :active")
            params["active"] = bool(active)

        qv = (q or "").strip()
        if qv:
            where.append("(supplier_name ILIKE :q_like OR supplier_code ILIKE :q_like)")
            params["q_like"] = f"%{qv}%"

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""

        return (
            f"""
            SELECT
              supplier_id AS id,
              supplier_name AS name,
              supplier_code AS code,
              active
            FROM wms_pms_supplier_projection
            {where_sql}
            ORDER BY supplier_id ASC
            """,
            params,
        )

    @staticmethod
    def _get_sql() -> str:
        return """
        SELECT
          supplier_id AS id,
          supplier_name AS name,
          supplier_code AS code,
          active
        FROM wms_pms_supplier_projection
        WHERE supplier_id = :supplier_id
        LIMIT 1
        """

    @staticmethod
    def _to_basic(row) -> SupplierBasic:
        return SupplierBasic(
            id=int(row["id"]),
            name=str(row["name"]),
            code=str(row["code"]) if row["code"] is not None else None,
            active=bool(row["active"]),
        )

    def list_basic(
        self,
        *,
        active: Optional[bool] = True,
        q: Optional[str] = None,
    ) -> list[SupplierBasic]:
        db = self._require_sync_db()
        sql, params = self._query_sql(active=active, q=q)
        rows = db.execute(text(sql), params).mappings().all()
        return [self._to_basic(row) for row in rows]

    async def alist_basic(
        self,
        *,
        active: Optional[bool] = True,
        q: Optional[str] = None,
    ) -> list[SupplierBasic]:
        db = self._require_async_db()
        sql, params = self._query_sql(active=active, q=q)
        rows = (await db.execute(text(sql), params)).mappings().all()
        return [self._to_basic(row) for row in rows]

    async def aget_basic_by_id(self, *, supplier_id: int) -> SupplierBasic | None:
        db = self._require_async_db()
        row = (
            await db.execute(
                text(self._get_sql()),
                {"supplier_id": int(supplier_id)},
            )
        ).mappings().first()

        if row is None:
            return None
        return self._to_basic(row)
