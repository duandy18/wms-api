# app/pms/export/sku_codes/services/sku_code_read_service.py
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.pms.export.sku_codes.contracts.sku_code import (
    PmsExportSkuCode,
    PmsExportSkuCodeResolution,
)
from app.pms.items.models.item import Item
from app.pms.items.models.item_sku_code import ItemSkuCode
from app.pms.items.models.item_uom import ItemUOM


def _clean_ids(values: Sequence[int] | None) -> list[int]:
    if not values:
        return []
    return sorted({int(x) for x in values if int(x) > 0})


def _norm_code(v: object) -> str | None:
    s = str(v or "").strip()
    return s or None


def _uom_name(uom: str, display_name: str | None) -> str:
    name = str(display_name or "").strip()
    if name:
        return name
    return str(uom or "").strip()


def _to_contract(code: ItemSkuCode, item: Item) -> PmsExportSkuCode:
    return PmsExportSkuCode(
        id=int(code.id),
        item_id=int(code.item_id),
        code=str(code.code),
        code_type=str(code.code_type),
        is_primary=bool(code.is_primary),
        is_active=bool(code.is_active),
        effective_from=code.effective_from,
        effective_to=code.effective_to,
        remark=str(code.remark).strip() if getattr(code, "remark", None) is not None else None,
        item_sku=str(item.sku),
        item_name=str(item.name),
        item_enabled=bool(item.enabled),
    )


def _to_resolution(
    *,
    code: ItemSkuCode,
    item: Item,
    uom: ItemUOM,
) -> PmsExportSkuCodeResolution:
    return PmsExportSkuCodeResolution(
        sku_code_id=int(code.id),
        item_id=int(code.item_id),
        sku_code=str(code.code),
        code_type=str(code.code_type),
        is_primary=bool(code.is_primary),
        item_sku=str(item.sku),
        item_name=str(item.name),
        item_uom_id=int(uom.id),
        uom=str(uom.uom),
        display_name=(
            str(uom.display_name).strip()
            if getattr(uom, "display_name", None) is not None
            else None
        ),
        uom_name=_uom_name(str(uom.uom), getattr(uom, "display_name", None)),
        ratio_to_base=int(uom.ratio_to_base),
    )


class PmsExportSkuCodeReadService:
    """
    PMS export SKU code read service.

    只读服务，不负责：
    - 新增 SKU code；
    - 停用/启用 SKU code；
    - 切换主 SKU code。
    """

    def __init__(self, db: Session | AsyncSession) -> None:
        self.db = db

    def get_by_id(self, *, sku_code_id: int) -> PmsExportSkuCode | None:
        row = self.db.execute(
            self._build_base_stmt().where(ItemSkuCode.id == int(sku_code_id))
        ).first()
        if row is None:
            return None
        code, item = row
        return _to_contract(code, item)

    def list_sku_codes(
        self,
        *,
        item_ids: Sequence[int] | None = None,
        sku_code_ids: Sequence[int] | None = None,
        code: str | None = None,
        active: bool | None = True,
        primary_only: bool = False,
    ) -> list[PmsExportSkuCode]:
        rows = self.db.execute(
            self._build_list_stmt(
                item_ids=item_ids,
                sku_code_ids=sku_code_ids,
                code=code,
                active=active,
                primary_only=primary_only,
            )
        ).all()
        return [_to_contract(sku_code, item) for sku_code, item in rows]

    def list_by_item_id(
        self,
        *,
        item_id: int,
        active: bool | None = True,
        primary_only: bool = False,
    ) -> list[PmsExportSkuCode]:
        return self.list_sku_codes(
            item_ids=[int(item_id)],
            active=active,
            primary_only=primary_only,
        )

    def resolve_active_code_for_outbound_default(
        self,
        *,
        code: str,
        enabled_only: bool = True,
    ) -> PmsExportSkuCodeResolution | None:
        code_row = self._get_active_code_row(code=code, enabled_only=enabled_only)
        if code_row is None:
            return None

        sku_code, item = code_row
        uom = self._get_outbound_default_or_base_uom(item_id=int(sku_code.item_id))
        if uom is None:
            return None

        return _to_resolution(code=sku_code, item=item, uom=uom)

    async def aget_by_id(self, *, sku_code_id: int) -> PmsExportSkuCode | None:
        row = (
            await self.db.execute(
                self._build_base_stmt().where(ItemSkuCode.id == int(sku_code_id))
            )
        ).first()
        if row is None:
            return None
        code, item = row
        return _to_contract(code, item)

    async def alist_sku_codes(
        self,
        *,
        item_ids: Sequence[int] | None = None,
        sku_code_ids: Sequence[int] | None = None,
        code: str | None = None,
        active: bool | None = True,
        primary_only: bool = False,
    ) -> list[PmsExportSkuCode]:
        rows = (
            await self.db.execute(
                self._build_list_stmt(
                    item_ids=item_ids,
                    sku_code_ids=sku_code_ids,
                    code=code,
                    active=active,
                    primary_only=primary_only,
                )
            )
        ).all()
        return [_to_contract(sku_code, item) for sku_code, item in rows]

    async def alist_by_item_id(
        self,
        *,
        item_id: int,
        active: bool | None = True,
        primary_only: bool = False,
    ) -> list[PmsExportSkuCode]:
        return await self.alist_sku_codes(
            item_ids=[int(item_id)],
            active=active,
            primary_only=primary_only,
        )

    async def aresolve_active_code_for_outbound_default(
        self,
        *,
        code: str,
        enabled_only: bool = True,
    ) -> PmsExportSkuCodeResolution | None:
        code_row = await self._aget_active_code_row(code=code, enabled_only=enabled_only)
        if code_row is None:
            return None

        sku_code, item = code_row
        uom = await self._aget_outbound_default_or_base_uom(item_id=int(sku_code.item_id))
        if uom is None:
            return None

        return _to_resolution(code=sku_code, item=item, uom=uom)

    @staticmethod
    def _build_base_stmt():
        return select(ItemSkuCode, Item).join(Item, Item.id == ItemSkuCode.item_id)

    @classmethod
    def _build_list_stmt(
        cls,
        *,
        item_ids: Sequence[int] | None,
        sku_code_ids: Sequence[int] | None,
        code: str | None,
        active: bool | None,
        primary_only: bool,
    ):
        stmt = cls._build_base_stmt()

        clean_item_ids = _clean_ids(item_ids)
        clean_code_ids = _clean_ids(sku_code_ids)
        code_norm = _norm_code(code)

        if clean_item_ids:
            stmt = stmt.where(ItemSkuCode.item_id.in_(clean_item_ids))
        if clean_code_ids:
            stmt = stmt.where(ItemSkuCode.id.in_(clean_code_ids))
        if code_norm:
            stmt = stmt.where(func.lower(ItemSkuCode.code) == code_norm.lower())
        if active is not None:
            stmt = stmt.where(ItemSkuCode.is_active.is_(bool(active)))
        if primary_only:
            stmt = stmt.where(ItemSkuCode.is_primary.is_(True))

        return stmt.order_by(
            ItemSkuCode.item_id.asc(),
            ItemSkuCode.is_primary.desc(),
            ItemSkuCode.is_active.desc(),
            ItemSkuCode.id.asc(),
        )

    def _get_active_code_row(
        self,
        *,
        code: str,
        enabled_only: bool,
    ):
        code_norm = _norm_code(code)
        if code_norm is None:
            return None

        stmt = (
            self._build_base_stmt()
            .where(func.lower(ItemSkuCode.code) == code_norm.lower())
            .where(ItemSkuCode.is_active.is_(True))
            .order_by(ItemSkuCode.is_primary.desc(), ItemSkuCode.id.asc())
            .limit(1)
        )
        if enabled_only:
            stmt = stmt.where(Item.enabled.is_(True))

        return self.db.execute(stmt).first()

    async def _aget_active_code_row(
        self,
        *,
        code: str,
        enabled_only: bool,
    ):
        code_norm = _norm_code(code)
        if code_norm is None:
            return None

        stmt = (
            self._build_base_stmt()
            .where(func.lower(ItemSkuCode.code) == code_norm.lower())
            .where(ItemSkuCode.is_active.is_(True))
            .order_by(ItemSkuCode.is_primary.desc(), ItemSkuCode.id.asc())
            .limit(1)
        )
        if enabled_only:
            stmt = stmt.where(Item.enabled.is_(True))

        return (await self.db.execute(stmt)).first()

    def _get_outbound_default_or_base_uom(self, *, item_id: int) -> ItemUOM | None:
        stmt = (
            select(ItemUOM)
            .where(ItemUOM.item_id == int(item_id))
            .where((ItemUOM.is_outbound_default.is_(True)) | (ItemUOM.is_base.is_(True)))
            .order_by(
                ItemUOM.is_outbound_default.desc(),
                ItemUOM.is_base.desc(),
                ItemUOM.id.asc(),
            )
            .limit(1)
        )
        return self.db.execute(stmt).scalars().first()

    async def _aget_outbound_default_or_base_uom(self, *, item_id: int) -> ItemUOM | None:
        stmt = (
            select(ItemUOM)
            .where(ItemUOM.item_id == int(item_id))
            .where((ItemUOM.is_outbound_default.is_(True)) | (ItemUOM.is_base.is_(True)))
            .order_by(
                ItemUOM.is_outbound_default.desc(),
                ItemUOM.is_base.desc(),
                ItemUOM.id.asc(),
            )
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalars().first()


__all__ = ["PmsExportSkuCodeReadService"]
