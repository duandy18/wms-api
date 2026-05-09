# app/pms/export/uoms/services/uom_read_service.py
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.pms.export.uoms.contracts.uom import PmsExportUom
from app.pms.items.models.item_uom import ItemUOM


def _uom_name(uom: str, display_name: str | None) -> str:
    name = str(display_name or "").strip()
    if name:
        return name
    return str(uom or "").strip()


def _to_contract(row: ItemUOM) -> PmsExportUom:
    return PmsExportUom(
        id=int(row.id),
        item_id=int(row.item_id),
        uom=str(row.uom),
        display_name=(
            str(row.display_name).strip()
            if getattr(row, "display_name", None) is not None
            else None
        ),
        uom_name=_uom_name(str(row.uom), getattr(row, "display_name", None)),
        ratio_to_base=int(row.ratio_to_base),
        net_weight_kg=(
            float(row.net_weight_kg)
            if getattr(row, "net_weight_kg", None) is not None
            else None
        ),
        is_base=bool(row.is_base),
        is_purchase_default=bool(row.is_purchase_default),
        is_inbound_default=bool(row.is_inbound_default),
        is_outbound_default=bool(row.is_outbound_default),
    )


def _clean_ids(values: Sequence[int] | None) -> list[int]:
    if not values:
        return []
    return sorted({int(x) for x in values if int(x) > 0})


class PmsExportUomReadService:
    """
    PMS export UOM read service.

    只读服务，不负责 owner 写入、默认单位切换、删除保护等治理动作。
    """

    def __init__(self, db: Session | AsyncSession) -> None:
        self.db = db

    def get_by_id(self, *, item_uom_id: int) -> PmsExportUom | None:
        row = self.db.get(ItemUOM, int(item_uom_id))
        return _to_contract(row) if row is not None else None

    def list_uoms(
        self,
        *,
        item_ids: Sequence[int] | None = None,
        item_uom_ids: Sequence[int] | None = None,
    ) -> list[PmsExportUom]:
        stmt = self._build_list_stmt(item_ids=item_ids, item_uom_ids=item_uom_ids)
        rows = self.db.execute(stmt).scalars().all()
        return [_to_contract(row) for row in rows]

    def list_by_item_id(self, *, item_id: int) -> list[PmsExportUom]:
        return self.list_uoms(item_ids=[int(item_id)])

    async def aget_by_id(self, *, item_uom_id: int) -> PmsExportUom | None:
        row = await self.db.get(ItemUOM, int(item_uom_id))
        return _to_contract(row) if row is not None else None

    async def alist_uoms(
        self,
        *,
        item_ids: Sequence[int] | None = None,
        item_uom_ids: Sequence[int] | None = None,
    ) -> list[PmsExportUom]:
        stmt = self._build_list_stmt(item_ids=item_ids, item_uom_ids=item_uom_ids)
        rows = (await self.db.execute(stmt)).scalars().all()
        return [_to_contract(row) for row in rows]

    async def alist_by_item_id(self, *, item_id: int) -> list[PmsExportUom]:
        return await self.alist_uoms(item_ids=[int(item_id)])

    async def aget_purchase_default_or_base(self, *, item_id: int) -> PmsExportUom | None:
        stmt = (
            select(ItemUOM)
            .where(ItemUOM.item_id == int(item_id))
            .order_by(
                ItemUOM.is_purchase_default.desc(),
                ItemUOM.is_base.desc(),
                ItemUOM.id.asc(),
            )
            .limit(1)
        )
        row = (await self.db.execute(stmt)).scalars().first()
        return _to_contract(row) if row is not None else None

    async def aget_inbound_default_or_base(self, *, item_id: int) -> PmsExportUom | None:
        stmt = (
            select(ItemUOM)
            .where(ItemUOM.item_id == int(item_id))
            .order_by(
                ItemUOM.is_inbound_default.desc(),
                ItemUOM.is_base.desc(),
                ItemUOM.id.asc(),
            )
            .limit(1)
        )
        row = (await self.db.execute(stmt)).scalars().first()
        return _to_contract(row) if row is not None else None

    async def aget_outbound_default_or_base(self, *, item_id: int) -> PmsExportUom | None:
        stmt = (
            select(ItemUOM)
            .where(ItemUOM.item_id == int(item_id))
            .order_by(
                ItemUOM.is_outbound_default.desc(),
                ItemUOM.is_base.desc(),
                ItemUOM.id.asc(),
            )
            .limit(1)
        )
        row = (await self.db.execute(stmt)).scalars().first()
        return _to_contract(row) if row is not None else None

    @staticmethod
    def _build_list_stmt(
        *,
        item_ids: Sequence[int] | None,
        item_uom_ids: Sequence[int] | None,
    ):
        stmt = select(ItemUOM)
        clean_item_ids = _clean_ids(item_ids)
        clean_uom_ids = _clean_ids(item_uom_ids)

        if clean_item_ids:
            stmt = stmt.where(ItemUOM.item_id.in_(clean_item_ids))
        if clean_uom_ids:
            stmt = stmt.where(ItemUOM.id.in_(clean_uom_ids))

        return stmt.order_by(
            ItemUOM.item_id.asc(),
            ItemUOM.ratio_to_base.asc(),
            ItemUOM.id.asc(),
        )


__all__ = ["PmsExportUomReadService"]
