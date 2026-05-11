# tests/helpers/pms_read_client_fake.py
from __future__ import annotations

from collections.abc import Iterable, Sequence
from types import SimpleNamespace
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pms.contracts import (
    ItemBasic,
    ItemPolicy,
    PmsExportUom,
)


def _clean_ids(values: Iterable[int]) -> list[int]:
    return sorted({int(value) for value in values if int(value) > 0})


class ProjectionBackedFakePmsReadClient:
    """
    Test-only fake PMS read client backed by WMS local PMS projection tables.

    Boundary:
    - tests only;
    - reads wms_pms_*_projection tables only;
    - never reads legacy PMS owner tables;
    - never replaces runtime HttpPmsReadClient.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_item_basic(self, *, item_id: int) -> ItemBasic | None:
        rows = await self.get_item_basics(item_ids=[int(item_id)])
        return rows.get(int(item_id))

    async def get_item_basics(
        self,
        *,
        item_ids: Iterable[int],
    ) -> dict[int, ItemBasic]:
        ids = _clean_ids(item_ids)
        if not ids:
            return {}

        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT
                        item_id AS id,
                        sku,
                        name,
                        spec,
                        enabled,
                        supplier_id,
                        brand,
                        category
                    FROM wms_pms_item_projection
                    WHERE item_id = ANY(:item_ids)
                    """
                ),
                {"item_ids": ids},
            )
        ).mappings().all()

        return {
            int(row["id"]): ItemBasic.model_validate(dict(row))
            for row in rows
        }

    async def get_item_policy(self, *, item_id: int) -> ItemPolicy | None:
        rows = await self.get_item_policies(item_ids=[int(item_id)])
        return rows.get(int(item_id))

    async def get_item_policies(
        self,
        *,
        item_ids: Iterable[int],
    ) -> dict[int, ItemPolicy]:
        ids = _clean_ids(item_ids)
        if not ids:
            return {}

        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT
                        item_id,
                        expiry_policy,
                        shelf_life_value,
                        shelf_life_unit,
                        lot_source_policy,
                        derivation_allowed,
                        uom_governance_enabled
                    FROM wms_pms_item_projection
                    WHERE item_id = ANY(:item_ids)
                    """
                ),
                {"item_ids": ids},
            )
        ).mappings().all()

        return {
            int(row["item_id"]): ItemPolicy.model_validate(dict(row))
            for row in rows
        }

    async def get_item_policy_by_sku(self, *, sku: str) -> ItemPolicy | None:
        sku_value = str(sku or "").strip()
        if not sku_value:
            return None

        row = (
            await self.session.execute(
                text(
                    """
                    SELECT
                        item_id,
                        expiry_policy,
                        shelf_life_value,
                        shelf_life_unit,
                        lot_source_policy,
                        derivation_allowed,
                        uom_governance_enabled
                    FROM wms_pms_item_projection
                    WHERE sku = :sku
                    LIMIT 1
                    """
                ),
                {"sku": sku_value},
            )
        ).mappings().first()

        if row is None:
            return None
        return ItemPolicy.model_validate(dict(row))

    async def get_uom(self, *, item_uom_id: int) -> PmsExportUom | None:
        rows = await self.list_uoms(item_uom_ids=[int(item_uom_id)])
        return rows[0] if rows else None

    async def list_uoms(
        self,
        *,
        item_ids: Sequence[int] | None = None,
        item_uom_ids: Sequence[int] | None = None,
    ) -> list[PmsExportUom]:
        item_ids_clean = _clean_ids(item_ids or [])
        item_uom_ids_clean = _clean_ids(item_uom_ids or [])

        conditions: list[str] = []
        params: dict[str, Any] = {}

        if item_ids_clean:
            conditions.append("item_id = ANY(:item_ids)")
            params["item_ids"] = item_ids_clean

        if item_uom_ids_clean:
            conditions.append("item_uom_id = ANY(:item_uom_ids)")
            params["item_uom_ids"] = item_uom_ids_clean

        if not conditions:
            return []

        rows = (
            await self.session.execute(
                text(
                    f"""
                    SELECT
                        item_uom_id AS id,
                        item_id,
                        uom,
                        display_name,
                        uom_name,
                        ratio_to_base,
                        net_weight_kg,
                        is_base,
                        is_purchase_default,
                        is_inbound_default,
                        is_outbound_default
                    FROM wms_pms_uom_projection
                    WHERE {" OR ".join(conditions)}
                    ORDER BY item_id ASC, is_base DESC, item_uom_id ASC
                    """
                ),
                params,
            )
        ).mappings().all()

        return [PmsExportUom.model_validate(dict(row)) for row in rows]

    async def list_uoms_by_item_id(self, *, item_id: int) -> list[PmsExportUom]:
        return await self.list_uoms(item_ids=[int(item_id)])

    async def get_purchase_default_or_base_uom(self, *, item_id: int) -> PmsExportUom | None:
        return await self._get_default_or_base_uom(item_id=int(item_id), field="is_purchase_default")

    async def get_inbound_default_or_base_uom(self, *, item_id: int) -> PmsExportUom | None:
        return await self._get_default_or_base_uom(item_id=int(item_id), field="is_inbound_default")

    async def get_outbound_default_or_base_uom(self, *, item_id: int) -> PmsExportUom | None:
        return await self._get_default_or_base_uom(item_id=int(item_id), field="is_outbound_default")

    async def _get_default_or_base_uom(self, *, item_id: int, field: str) -> PmsExportUom | None:
        if field not in {"is_purchase_default", "is_inbound_default", "is_outbound_default"}:
            raise ValueError(f"unsupported default uom field: {field}")

        row = (
            await self.session.execute(
                text(
                    f"""
                    SELECT
                        item_uom_id AS id,
                        item_id,
                        uom,
                        display_name,
                        uom_name,
                        ratio_to_base,
                        net_weight_kg,
                        is_base,
                        is_purchase_default,
                        is_inbound_default,
                        is_outbound_default
                    FROM wms_pms_uom_projection
                    WHERE item_id = :item_id
                    ORDER BY
                        CASE WHEN {field} IS TRUE THEN 0 ELSE 1 END,
                        CASE WHEN is_base IS TRUE THEN 0 ELSE 1 END,
                        item_uom_id ASC
                    LIMIT 1
                    """
                ),
                {"item_id": int(item_id)},
            )
        ).mappings().first()

        if row is None:
            return None
        return PmsExportUom.model_validate(dict(row))


def projection_backed_pms_read_client_factory(session: AsyncSession):
    """
    Return a create_pms_read_client-compatible test factory.

    Usage:
        monkeypatch.setattr(module, "create_pms_read_client", factory)
    """

    def _factory(*, session: AsyncSession | None = None, **_: object):
        if session is None:
            raise RuntimeError("test fake PMS client requires session")
        return ProjectionBackedFakePmsReadClient(session)

    return _factory


__all__ = [
    "ProjectionBackedFakePmsReadClient",
    "projection_backed_pms_read_client_factory",
]
