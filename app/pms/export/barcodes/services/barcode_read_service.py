# app/pms/export/barcodes/services/barcode_read_service.py
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.pms.export.barcodes.contracts.barcode import PmsExportBarcode
from app.pms.items.models.item_barcode import ItemBarcode
from app.pms.items.models.item_uom import ItemUOM


def _clean_ids(values: Sequence[int] | None) -> list[int]:
    if not values:
        return []
    return sorted({int(x) for x in values if int(x) > 0})


def _uom_name(uom: str, display_name: str | None) -> str:
    name = str(display_name or "").strip()
    if name:
        return name
    return str(uom or "").strip()


def _to_contract(barcode: ItemBarcode, uom: ItemUOM) -> PmsExportBarcode:
    return PmsExportBarcode(
        id=int(barcode.id),
        item_id=int(barcode.item_id),
        item_uom_id=int(barcode.item_uom_id),
        barcode=str(barcode.barcode),
        symbology=str(barcode.symbology),
        active=bool(barcode.active),
        is_primary=bool(barcode.is_primary),
        uom=str(uom.uom),
        display_name=(
            str(uom.display_name).strip()
            if getattr(uom, "display_name", None) is not None
            else None
        ),
        uom_name=_uom_name(str(uom.uom), getattr(uom, "display_name", None)),
        ratio_to_base=int(uom.ratio_to_base),
    )


class PmsExportBarcodeReadService:
    """
    PMS export barcode read service.

    只读服务，不负责：
    - 创建条码；
    - 修改条码；
    - 改绑包装；
    - 设置主条码。
    """

    def __init__(self, db: Session | AsyncSession) -> None:
        self.db = db

    def get_by_id(self, *, barcode_id: int) -> PmsExportBarcode | None:
        stmt = self._build_base_stmt().where(ItemBarcode.id == int(barcode_id))
        row = self.db.execute(stmt).first()
        if row is None:
            return None
        barcode, uom = row
        return _to_contract(barcode, uom)

    def list_barcodes(
        self,
        *,
        item_ids: Sequence[int] | None = None,
        item_uom_ids: Sequence[int] | None = None,
        barcode: str | None = None,
        active: bool | None = True,
        primary_only: bool = False,
    ) -> list[PmsExportBarcode]:
        stmt = self._build_list_stmt(
            item_ids=item_ids,
            item_uom_ids=item_uom_ids,
            barcode=barcode,
            active=active,
            primary_only=primary_only,
        )
        rows = self.db.execute(stmt).all()
        return [_to_contract(bc, uom) for bc, uom in rows]

    def list_by_item_id(
        self,
        *,
        item_id: int,
        active: bool | None = True,
        primary_only: bool = False,
    ) -> list[PmsExportBarcode]:
        return self.list_barcodes(
            item_ids=[int(item_id)],
            active=active,
            primary_only=primary_only,
        )

    async def aget_by_id(self, *, barcode_id: int) -> PmsExportBarcode | None:
        stmt = self._build_base_stmt().where(ItemBarcode.id == int(barcode_id))
        row = (await self.db.execute(stmt)).first()
        if row is None:
            return None
        barcode, uom = row
        return _to_contract(barcode, uom)

    async def alist_barcodes(
        self,
        *,
        item_ids: Sequence[int] | None = None,
        item_uom_ids: Sequence[int] | None = None,
        barcode: str | None = None,
        active: bool | None = True,
        primary_only: bool = False,
    ) -> list[PmsExportBarcode]:
        stmt = self._build_list_stmt(
            item_ids=item_ids,
            item_uom_ids=item_uom_ids,
            barcode=barcode,
            active=active,
            primary_only=primary_only,
        )
        rows = (await self.db.execute(stmt)).all()
        return [_to_contract(bc, uom) for bc, uom in rows]

    async def alist_by_item_id(
        self,
        *,
        item_id: int,
        active: bool | None = True,
        primary_only: bool = False,
    ) -> list[PmsExportBarcode]:
        return await self.alist_barcodes(
            item_ids=[int(item_id)],
            active=active,
            primary_only=primary_only,
        )

    @staticmethod
    def _build_base_stmt():
        return select(ItemBarcode, ItemUOM).join(
            ItemUOM,
            (ItemUOM.id == ItemBarcode.item_uom_id)
            & (ItemUOM.item_id == ItemBarcode.item_id),
        )

    @classmethod
    def _build_list_stmt(
        cls,
        *,
        item_ids: Sequence[int] | None,
        item_uom_ids: Sequence[int] | None,
        barcode: str | None,
        active: bool | None,
        primary_only: bool,
    ):
        stmt = cls._build_base_stmt()

        clean_item_ids = _clean_ids(item_ids)
        clean_uom_ids = _clean_ids(item_uom_ids)
        code = str(barcode or "").strip()

        if clean_item_ids:
            stmt = stmt.where(ItemBarcode.item_id.in_(clean_item_ids))
        if clean_uom_ids:
            stmt = stmt.where(ItemBarcode.item_uom_id.in_(clean_uom_ids))
        if code:
            stmt = stmt.where(ItemBarcode.barcode == code)
        if active is not None:
            stmt = stmt.where(ItemBarcode.active.is_(bool(active)))
        if primary_only:
            stmt = stmt.where(ItemBarcode.is_primary.is_(True))

        return stmt.order_by(
            ItemBarcode.item_id.asc(),
            ItemBarcode.is_primary.desc(),
            ItemBarcode.active.desc(),
            ItemBarcode.id.asc(),
        )


__all__ = ["PmsExportBarcodeReadService"]
