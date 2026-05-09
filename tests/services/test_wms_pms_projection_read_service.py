from __future__ import annotations

from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.wms.pms_projection.services.read_service import WmsPmsProjectionReadService
from app.wms.pms_projection.services.rebuild_service import WmsPmsProjectionRebuildService
from app.wms.scan.services.scan_orchestrator_item_resolver import (
    probe_item_from_barcode,
    resolve_item_id_from_sku,
)


async def _rebuild(session: AsyncSession) -> None:
    await WmsPmsProjectionRebuildService(session).rebuild_all()
    await session.flush()


async def test_wms_pms_projection_read_service_resolves_barcode_and_sku_code(
    session: AsyncSession,
) -> None:
    await _rebuild(session)

    barcode_row = (
        await session.execute(
            text(
                """
                SELECT
                  b.barcode,
                  b.item_id,
                  b.item_uom_id,
                  b.symbology,
                  u.ratio_to_base,
                  COALESCE(NULLIF(u.display_name, ''), u.uom) AS uom_name
                FROM item_barcodes b
                JOIN item_uoms u
                  ON u.id = b.item_uom_id
                 AND u.item_id = b.item_id
                WHERE b.active = true
                ORDER BY b.id ASC
                LIMIT 1
                """
            )
        )
    ).mappings().one()

    svc = WmsPmsProjectionReadService(session)
    resolved = await svc.aprobe_barcode(barcode=str(barcode_row["barcode"]))

    assert resolved is not None
    assert resolved.item_id == int(barcode_row["item_id"])
    assert resolved.item_uom_id == int(barcode_row["item_uom_id"])
    assert resolved.ratio_to_base == int(barcode_row["ratio_to_base"])
    assert resolved.symbology == str(barcode_row["symbology"])
    assert resolved.active is True
    assert resolved.uom_name == str(barcode_row["uom_name"])

    sku_row = (
        await session.execute(
            text(
                """
                SELECT
                  id,
                  item_id,
                  code
                FROM item_sku_codes
                WHERE is_active = true
                ORDER BY id ASC
                LIMIT 1
                """
            )
        )
    ).mappings().one()

    item_id = await svc.aresolve_active_sku_code_item_id(code=str(sku_row["code"]).lower())
    assert item_id == int(sku_row["item_id"])


async def test_scan_resolver_uses_wms_projection_not_pms_owner_tables(
    session: AsyncSession,
) -> None:
    await _rebuild(session)

    suffix = uuid4().hex[:10]
    barcode = f"PRJ4-BAR-{suffix}"
    sku_code = f"PRJ4-SKU-{suffix}"

    barcode_projection = (
        await session.execute(
            text(
                """
                SELECT
                  b.barcode_id,
                  b.item_id,
                  b.item_uom_id,
                  u.ratio_to_base
                FROM wms_pms_item_barcode_projection b
                JOIN wms_pms_item_uom_projection u
                  ON u.item_uom_id = b.item_uom_id
                 AND u.item_id = b.item_id
                ORDER BY b.barcode_id ASC
                LIMIT 1
                """
            )
        )
    ).mappings().one()

    sku_projection = (
        await session.execute(
            text(
                """
                SELECT
                  sku_code_id,
                  item_id
                FROM wms_pms_item_sku_code_projection
                ORDER BY sku_code_id ASC
                LIMIT 1
                """
            )
        )
    ).mappings().one()

    await session.execute(
        text(
            """
            UPDATE wms_pms_item_barcode_projection
            SET
              barcode = :barcode,
              updated_at = now()
            WHERE barcode_id = :barcode_id
            """
        ),
        {
            "barcode": barcode,
            "barcode_id": int(barcode_projection["barcode_id"]),
        },
    )

    await session.execute(
        text(
            """
            UPDATE wms_pms_item_sku_code_projection
            SET
              code = :code,
              updated_at = now()
            WHERE sku_code_id = :sku_code_id
            """
        ),
        {
            "code": sku_code,
            "sku_code_id": int(sku_projection["sku_code_id"]),
        },
    )

    resolved_barcode = await probe_item_from_barcode(session, barcode)
    assert resolved_barcode is not None
    assert resolved_barcode.item_id == int(barcode_projection["item_id"])
    assert resolved_barcode.item_uom_id == int(barcode_projection["item_uom_id"])
    assert resolved_barcode.ratio_to_base == int(barcode_projection["ratio_to_base"])

    resolved_sku_item_id = await resolve_item_id_from_sku(session, sku_code.lower())
    assert resolved_sku_item_id == int(sku_projection["item_id"])
