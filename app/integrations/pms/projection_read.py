# app/integrations/pms/projection_read.py
"""
Read helpers for WMS-owned PMS projection tables.

Boundary:
- These helpers read WMS local projection tables only.
- They must not call pms-api HTTP.
- They must not read PMS owner tables directly.
- They are for read/probe/display paths only, not write validation authority.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class ProjectionBarcodeResolved:
    item_id: int
    item_uom_id: int | None
    ratio_to_base: int | None
    symbology: str | None
    active: bool | None


async def resolve_projection_barcode(
    session: AsyncSession,
    *,
    barcode: str,
) -> ProjectionBarcodeResolved | None:
    code = str(barcode or "").strip()
    if not code:
        return None

    row = (
        await session.execute(
            text(
                """
                SELECT
                    b.item_id,
                    b.item_uom_id,
                    u.ratio_to_base,
                    b.symbology,
                    b.active
                FROM wms_pms_barcode_projection AS b
                LEFT JOIN wms_pms_uom_projection AS u
                  ON u.item_uom_id = b.item_uom_id
                 AND u.item_id = b.item_id
                WHERE b.barcode = :barcode
                LIMIT 1
                """
            ),
            {"barcode": code},
        )
    ).mappings().first()

    if row is None:
        return None
    if bool(row["active"]) is not True:
        return None

    return ProjectionBarcodeResolved(
        item_id=int(row["item_id"]),
        item_uom_id=(
            int(row["item_uom_id"]) if row["item_uom_id"] is not None else None
        ),
        ratio_to_base=(
            int(row["ratio_to_base"]) if row["ratio_to_base"] is not None else None
        ),
        symbology=(str(row["symbology"]) if row["symbology"] is not None else None),
        active=bool(row["active"]),
    )


async def resolve_projection_sku_code_item_id(
    session: AsyncSession,
    *,
    sku_code: str,
    active_only: bool = True,
) -> int | None:
    code = str(sku_code or "").strip().upper()
    if not code:
        return None

    cond = ["UPPER(s.sku_code) = :sku_code"]
    params: dict[str, object] = {"sku_code": code}

    if active_only:
        cond.append("s.is_active IS TRUE")

    row = (
        await session.execute(
            text(
                f"""
                SELECT
                    s.item_id
                FROM wms_pms_sku_code_projection AS s
                WHERE {" AND ".join(cond)}
                ORDER BY s.is_primary DESC, s.sku_code_id ASC
                LIMIT 1
                """
            ),
            params,
        )
    ).first()

    if row is None:
        return None
    return int(row[0])


__all__ = [
    "ProjectionBarcodeResolved",
    "resolve_projection_barcode",
    "resolve_projection_sku_code_item_id",
]
