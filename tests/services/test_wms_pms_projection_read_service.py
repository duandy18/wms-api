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


async def test_wms_pms_projection_read_service_returns_item_uom_policy_snapshots(
    session: AsyncSession,
) -> None:
    await _rebuild(session)

    source = (
        await session.execute(
            text(
                """
                SELECT
                  p.item_id,
                  p.sku,
                  p.name,
                  p.spec,
                  p.enabled,
                  p.brand_id,
                  p.category_id,
                  bu.item_uom_id AS base_item_uom_id,
                  bu.uom AS base_uom,
                  bu.display_name AS base_display_name,
                  COALESCE(NULLIF(bu.display_name, ''), bu.uom) AS base_uom_name,
                  bu.ratio_to_base AS base_ratio_to_base,
                  bu.net_weight_kg AS base_net_weight_kg,
                  iu.item_uom_id AS inbound_item_uom_id,
                  iu.uom AS inbound_uom,
                  iu.display_name AS inbound_display_name,
                  COALESCE(NULLIF(iu.display_name, ''), iu.uom) AS inbound_uom_name,
                  iu.ratio_to_base AS inbound_ratio_to_base,
                  pol.lot_source_policy::text AS lot_source_policy,
                  pol.expiry_policy::text AS expiry_policy,
                  pol.shelf_life_value,
                  pol.shelf_life_unit,
                  pol.derivation_allowed,
                  pol.uom_governance_enabled
                FROM wms_pms_item_projection p
                JOIN wms_pms_item_uom_projection bu
                  ON bu.item_id = p.item_id
                 AND bu.is_base IS TRUE
                JOIN wms_pms_item_uom_projection iu
                  ON iu.item_id = p.item_id
                 AND iu.is_inbound_default IS TRUE
                JOIN wms_pms_item_policy_projection pol
                  ON pol.item_id = p.item_id
                WHERE p.enabled IS TRUE
                ORDER BY p.item_id ASC
                LIMIT 1
                """
            )
        )
    ).mappings().one()

    svc = WmsPmsProjectionReadService(session)
    item_id = int(source["item_id"])

    item_snapshot = await svc.aget_item_snapshot(item_id=item_id)
    assert item_snapshot is not None
    assert item_snapshot.item_id == item_id
    assert item_snapshot.sku == str(source["sku"])
    assert item_snapshot.name == str(source["name"])
    assert item_snapshot.spec == source["spec"]
    assert item_snapshot.enabled is True
    assert item_snapshot.brand_id == (
        int(source["brand_id"]) if source["brand_id"] is not None else None
    )
    assert item_snapshot.category_id == (
        int(source["category_id"]) if source["category_id"] is not None else None
    )

    enabled_item_snapshot = await svc.aget_item_snapshot(
        item_id=item_id,
        enabled_only=True,
    )
    assert enabled_item_snapshot is not None
    assert enabled_item_snapshot.item_id == item_id

    base_uom = await svc.aget_uom_snapshot(
        item_id=item_id,
        item_uom_id=int(source["base_item_uom_id"]),
    )
    assert base_uom is not None
    assert base_uom.item_uom_id == int(source["base_item_uom_id"])
    assert base_uom.item_id == item_id
    assert base_uom.uom == str(source["base_uom"])
    assert base_uom.display_name == source["base_display_name"]
    assert base_uom.uom_name == str(source["base_uom_name"])
    assert base_uom.ratio_to_base == int(source["base_ratio_to_base"])
    assert base_uom.is_base is True
    assert base_uom.net_weight_kg == source["base_net_weight_kg"]

    base_uom_by_default = await svc.aget_base_uom_snapshot(item_id=item_id)
    assert base_uom_by_default is not None
    assert base_uom_by_default.item_uom_id == int(source["base_item_uom_id"])

    inbound_uom = await svc.aget_inbound_default_uom_snapshot(item_id=item_id)
    assert inbound_uom is not None
    assert inbound_uom.item_uom_id == int(source["inbound_item_uom_id"])
    assert inbound_uom.uom == str(source["inbound_uom"])
    assert inbound_uom.display_name == source["inbound_display_name"]
    assert inbound_uom.uom_name == str(source["inbound_uom_name"])
    assert inbound_uom.ratio_to_base == int(source["inbound_ratio_to_base"])
    assert inbound_uom.is_inbound_default is True

    uom_name = await svc.aget_uom_name(
        item_id=item_id,
        item_uom_id=int(source["base_item_uom_id"]),
    )
    assert uom_name == str(source["base_uom_name"])

    policy = await svc.aget_policy_snapshot(item_id=item_id)
    assert policy is not None
    assert policy.item_id == item_id
    assert policy.lot_source_policy == str(source["lot_source_policy"])
    assert policy.expiry_policy == str(source["expiry_policy"])
    assert policy.shelf_life_value == (
        int(source["shelf_life_value"])
        if source["shelf_life_value"] is not None
        else None
    )
    assert policy.shelf_life_unit == source["shelf_life_unit"]
    assert policy.derivation_allowed is bool(source["derivation_allowed"])
    assert policy.uom_governance_enabled is bool(source["uom_governance_enabled"])

    await session.execute(
        text(
            """
            UPDATE wms_pms_item_projection
            SET enabled = false
            WHERE item_id = :item_id
            """
        ),
        {"item_id": item_id},
    )
    assert await svc.aget_item_snapshot(item_id=item_id, enabled_only=True) is None
    assert await svc.aget_item_snapshot(item_id=item_id, enabled_only=False) is not None

    missing_item_id = 999_999_991
    assert await svc.aget_item_snapshot(item_id=missing_item_id) is None
    assert await svc.aget_uom_snapshot(item_id=missing_item_id, item_uom_id=1) is None
    assert await svc.aget_base_uom_snapshot(item_id=missing_item_id) is None
    assert await svc.aget_inbound_default_uom_snapshot(item_id=missing_item_id) is None
    assert await svc.aget_policy_snapshot(item_id=missing_item_id) is None
    assert await svc.aget_uom_name(item_id=missing_item_id, item_uom_id=1) is None


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
