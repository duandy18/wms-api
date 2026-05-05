from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.oms.fsku.models.fsku import Fsku
from app.oms.fsku.models.platform_code_fsku_mapping import PlatformCodeFskuMapping


VALID_IDENTITY_KINDS = {"merchant_code", "platform_sku_id", "platform_item_sku"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_identity_kind(value: str | None) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if s not in VALID_IDENTITY_KINDS:
        return None
    return s


def normalize_identity_value(value: str | None) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def normalize_store_code(value: str | int | None) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


class PlatformCodeMappingService:
    class NotFound(Exception):
        pass

    class Conflict(Exception):
        pass

    @dataclass
    class BadInput(Exception):
        message: str

    def __init__(self, session: AsyncSession):
        self.session = session

    async def bind_upsert(
        self,
        *,
        platform: str,
        store_code: str,
        identity_kind: str,
        identity_value: str,
        fsku_id: int,
        reason: Optional[str],
    ) -> PlatformCodeFskuMapping:
        sid = normalize_store_code(store_code)
        if sid is None:
            raise self.BadInput("store_code 不能为空")

        kind = normalize_identity_kind(identity_kind)
        if kind is None:
            raise self.BadInput("identity_kind 非法")

        value = normalize_identity_value(identity_value)
        if value is None:
            raise self.BadInput("identity_value 不能为空")

        fsku = await self.session.get(Fsku, int(fsku_id))
        if fsku is None:
            raise self.NotFound("FSKU 不存在")
        if fsku.status != "published":
            raise self.Conflict("仅 published OMS FSKU 允许映射")

        now = _utc_now()
        rsn = reason.strip() if reason else None

        row = (
            await self.session.execute(
                select(PlatformCodeFskuMapping).where(
                    PlatformCodeFskuMapping.platform == platform,
                    PlatformCodeFskuMapping.store_code == sid,
                    PlatformCodeFskuMapping.identity_kind == kind,
                    PlatformCodeFskuMapping.identity_value == value,
                )
            )
        ).scalars().first()

        if row is None:
            obj = PlatformCodeFskuMapping(
                platform=platform,
                store_code=sid,
                identity_kind=kind,
                identity_value=value,
                fsku_id=int(fsku_id),
                reason=rsn,
                created_at=now,
                updated_at=now,
            )
            self.session.add(obj)
            await self.session.flush()
            return obj

        await self.session.execute(
            update(PlatformCodeFskuMapping)
            .where(PlatformCodeFskuMapping.id == int(row.id))
            .values(fsku_id=int(fsku_id), reason=rsn, updated_at=now)
        )
        await self.session.flush()

        refreshed = await self.session.get(PlatformCodeFskuMapping, int(row.id))
        if refreshed is None:
            raise self.NotFound("映射更新后未找到")
        return refreshed

    async def delete_mapping(
        self,
        *,
        platform: str,
        store_code: str,
        identity_kind: str,
        identity_value: str,
    ) -> PlatformCodeFskuMapping:
        sid = normalize_store_code(store_code)
        if sid is None:
            raise self.BadInput("store_code 不能为空")

        kind = normalize_identity_kind(identity_kind)
        if kind is None:
            raise self.BadInput("identity_kind 非法")

        value = normalize_identity_value(identity_value)
        if value is None:
            raise self.BadInput("identity_value 不能为空")

        row = (
            await self.session.execute(
                select(PlatformCodeFskuMapping).where(
                    PlatformCodeFskuMapping.platform == platform,
                    PlatformCodeFskuMapping.store_code == sid,
                    PlatformCodeFskuMapping.identity_kind == kind,
                    PlatformCodeFskuMapping.identity_value == value,
                )
            )
        ).scalars().first()

        if row is None:
            raise self.NotFound("未找到可删除的映射")

        await self.session.execute(delete(PlatformCodeFskuMapping).where(PlatformCodeFskuMapping.id == int(row.id)))
        await self.session.flush()
        return row
