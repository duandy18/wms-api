# tests/services/test_pms_export_read_services.py
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.pms.export.barcodes.services.barcode_read_service import PmsExportBarcodeReadService
from app.pms.export.items.contracts.barcode_probe import BarcodeProbeStatus
from app.pms.export.items.services.barcode_probe_service import BarcodeProbeService
from app.pms.export.sku_codes.services.sku_code_read_service import PmsExportSkuCodeReadService
from app.pms.export.uoms.services.uom_read_service import PmsExportUomReadService

pytestmark = pytest.mark.asyncio


def _uom_name(uom: object, display_name: object) -> str:
    name = str(display_name or "").strip()
    return name or str(uom or "").strip()


async def _pick_export_capable_row(session: AsyncSession) -> dict:
    row = (
        await session.execute(
            text(
                """
                SELECT
                  i.id AS item_id,
                  i.sku AS item_sku,
                  i.name AS item_name,
                  i.enabled AS item_enabled,
                  u.id AS item_uom_id,
                  u.uom,
                  u.display_name,
                  u.ratio_to_base,
                  u.is_base,
                  u.is_purchase_default,
                  u.is_inbound_default,
                  u.is_outbound_default,
                  u.net_weight_kg,
                  b.id AS barcode_id,
                  b.barcode,
                  b.symbology,
                  b.active AS barcode_active,
                  b.is_primary AS barcode_primary,
                  sc.id AS sku_code_id,
                  sc.code AS sku_code,
                  sc.code_type,
                  sc.is_primary AS sku_code_primary,
                  sc.is_active AS sku_code_active
                FROM items i
                JOIN item_uoms u
                  ON u.item_id = i.id
                 AND (u.is_outbound_default IS TRUE OR u.is_base IS TRUE)
                JOIN item_barcodes b
                  ON b.item_id = i.id
                 AND b.item_uom_id = u.id
                 AND b.active IS TRUE
                JOIN item_sku_codes sc
                  ON sc.item_id = i.id
                 AND sc.is_active IS TRUE
                WHERE i.enabled IS TRUE
                ORDER BY
                  i.id ASC,
                  u.is_outbound_default DESC,
                  u.is_base DESC,
                  u.id ASC,
                  b.is_primary DESC,
                  b.id ASC,
                  sc.is_primary DESC,
                  sc.id ASC
                LIMIT 1
                """
            )
        )
    ).mappings().first()

    assert row is not None, "test baseline must contain export-capable PMS item/uom/barcode/sku-code rows"
    return dict(row)


async def _expected_default_uom_id(
    session: AsyncSession,
    *,
    item_id: int,
    default_flag: str,
) -> int:
    assert default_flag in {
        "is_purchase_default",
        "is_inbound_default",
        "is_outbound_default",
    }

    row = (
        await session.execute(
            text(
                f"""
                SELECT id
                FROM item_uoms
                WHERE item_id = :item_id
                ORDER BY {default_flag} DESC, is_base DESC, id ASC
                LIMIT 1
                """
            ),
            {"item_id": int(item_id)},
        )
    ).scalar_one_or_none()

    assert row is not None, {"msg": "item has no item_uoms", "item_id": int(item_id)}
    return int(row)


async def test_pms_export_uom_read_service_returns_contract_rows(session: AsyncSession) -> None:
    seed = await _pick_export_capable_row(session)

    svc = PmsExportUomReadService(session)
    got = await svc.aget_by_id(item_uom_id=int(seed["item_uom_id"]))

    assert got is not None
    assert got.id == int(seed["item_uom_id"])
    assert got.item_id == int(seed["item_id"])
    assert got.uom == str(seed["uom"])
    assert got.display_name == (
        str(seed["display_name"]).strip() if seed["display_name"] is not None else None
    )
    assert got.uom_name == _uom_name(seed["uom"], seed["display_name"])
    assert got.ratio_to_base == int(seed["ratio_to_base"])
    assert got.net_weight_kg == (
        float(seed["net_weight_kg"]) if seed["net_weight_kg"] is not None else None
    )
    assert got.is_base is bool(seed["is_base"])
    assert got.is_purchase_default is bool(seed["is_purchase_default"])
    assert got.is_inbound_default is bool(seed["is_inbound_default"])
    assert got.is_outbound_default is bool(seed["is_outbound_default"])

    rows = await svc.alist_uoms(
        item_ids=[int(seed["item_id"])],
        item_uom_ids=[int(seed["item_uom_id"])],
    )
    assert [x.id for x in rows] == [int(seed["item_uom_id"])]

    by_item = await svc.alist_by_item_id(item_id=int(seed["item_id"]))
    assert any(x.id == int(seed["item_uom_id"]) for x in by_item)


async def test_pms_export_uom_read_service_default_or_base_selection(session: AsyncSession) -> None:
    seed = await _pick_export_capable_row(session)

    svc = PmsExportUomReadService(session)
    item_id = int(seed["item_id"])

    purchase = await svc.aget_purchase_default_or_base(item_id=item_id)
    inbound = await svc.aget_inbound_default_or_base(item_id=item_id)
    outbound = await svc.aget_outbound_default_or_base(item_id=item_id)

    assert purchase is not None
    assert inbound is not None
    assert outbound is not None

    assert purchase.id == await _expected_default_uom_id(
        session,
        item_id=item_id,
        default_flag="is_purchase_default",
    )
    assert inbound.id == await _expected_default_uom_id(
        session,
        item_id=item_id,
        default_flag="is_inbound_default",
    )
    assert outbound.id == await _expected_default_uom_id(
        session,
        item_id=item_id,
        default_flag="is_outbound_default",
    )


async def test_pms_export_barcode_read_service_returns_contract_rows(session: AsyncSession) -> None:
    seed = await _pick_export_capable_row(session)

    svc = PmsExportBarcodeReadService(session)
    got = await svc.aget_by_id(barcode_id=int(seed["barcode_id"]))

    assert got is not None
    assert got.id == int(seed["barcode_id"])
    assert got.item_id == int(seed["item_id"])
    assert got.item_uom_id == int(seed["item_uom_id"])
    assert got.barcode == str(seed["barcode"])
    assert got.symbology == str(seed["symbology"])
    assert got.active is bool(seed["barcode_active"])
    assert got.is_primary is bool(seed["barcode_primary"])
    assert got.uom == str(seed["uom"])
    assert got.uom_name == _uom_name(seed["uom"], seed["display_name"])
    assert got.ratio_to_base == int(seed["ratio_to_base"])

    rows = await svc.alist_barcodes(
        item_ids=[int(seed["item_id"])],
        item_uom_ids=[int(seed["item_uom_id"])],
        barcode=f"  {seed['barcode']}  ",
        active=True,
        primary_only=bool(seed["barcode_primary"]),
    )
    assert any(x.id == int(seed["barcode_id"]) for x in rows)

    by_item = await svc.alist_by_item_id(item_id=int(seed["item_id"]), active=True)
    assert any(x.id == int(seed["barcode_id"]) for x in by_item)


async def test_pms_export_barcode_probe_service_bound_unbound_and_empty(
    session: AsyncSession,
) -> None:
    seed = await _pick_export_capable_row(session)

    svc = BarcodeProbeService(session)

    bound = await svc.aprobe(barcode=f"  {seed['barcode']}  ")
    assert bound.ok is True
    assert bound.status is BarcodeProbeStatus.BOUND
    assert bound.barcode == str(seed["barcode"])
    assert bound.item_id == int(seed["item_id"])
    assert bound.item_uom_id == int(seed["item_uom_id"])
    assert bound.ratio_to_base == int(seed["ratio_to_base"])
    assert bound.symbology == str(seed["symbology"])
    assert bound.active is bool(seed["barcode_active"])
    assert bound.item_basic is not None
    assert bound.item_basic.id == int(seed["item_id"])
    assert bound.item_basic.sku == str(seed["item_sku"])
    assert bound.item_basic.name == str(seed["item_name"])
    assert bound.errors == []

    unbound = await svc.aprobe(barcode="UT-PMS-EXPORT-NOT-BOUND-BARCODE")
    assert unbound.ok is True
    assert unbound.status is BarcodeProbeStatus.UNBOUND
    assert unbound.barcode == "UT-PMS-EXPORT-NOT-BOUND-BARCODE"
    assert unbound.item_id is None
    assert unbound.item_uom_id is None
    assert unbound.ratio_to_base is None
    assert unbound.item_basic is None
    assert unbound.errors == []

    empty = await svc.aprobe(barcode="   ")
    assert empty.ok is False
    assert empty.status is BarcodeProbeStatus.ERROR
    assert empty.barcode == ""
    assert len(empty.errors) == 1
    assert empty.errors[0].stage == "probe"
    assert empty.errors[0].error == "barcode is required"


async def test_pms_export_sku_code_read_service_returns_contract_rows(session: AsyncSession) -> None:
    seed = await _pick_export_capable_row(session)

    svc = PmsExportSkuCodeReadService(session)
    got = await svc.aget_by_id(sku_code_id=int(seed["sku_code_id"]))

    assert got is not None
    assert got.id == int(seed["sku_code_id"])
    assert got.item_id == int(seed["item_id"])
    assert got.code == str(seed["sku_code"])
    assert got.code_type == str(seed["code_type"])
    assert got.is_primary is bool(seed["sku_code_primary"])
    assert got.is_active is bool(seed["sku_code_active"])
    assert got.item_sku == str(seed["item_sku"])
    assert got.item_name == str(seed["item_name"])
    assert got.item_enabled is bool(seed["item_enabled"])

    rows = await svc.alist_sku_codes(
        item_ids=[int(seed["item_id"])],
        sku_code_ids=[int(seed["sku_code_id"])],
        code=str(seed["sku_code"]).lower(),
        active=True,
        primary_only=bool(seed["sku_code_primary"]),
    )
    assert any(x.id == int(seed["sku_code_id"]) for x in rows)

    by_item = await svc.alist_by_item_id(item_id=int(seed["item_id"]), active=True)
    assert any(x.id == int(seed["sku_code_id"]) for x in by_item)


async def test_pms_export_sku_code_resolution_uses_outbound_default_or_base_uom(
    session: AsyncSession,
) -> None:
    seed = await _pick_export_capable_row(session)

    svc = PmsExportSkuCodeReadService(session)

    got = await svc.aresolve_active_code_for_outbound_default(
        code=f"  {str(seed['sku_code']).lower()}  ",
        enabled_only=True,
    )

    assert got is not None
    assert got.sku_code_id == int(seed["sku_code_id"])
    assert got.item_id == int(seed["item_id"])
    assert got.sku_code == str(seed["sku_code"])
    assert got.code_type == str(seed["code_type"])
    assert got.is_primary is bool(seed["sku_code_primary"])
    assert got.item_sku == str(seed["item_sku"])
    assert got.item_name == str(seed["item_name"])
    assert got.item_uom_id == int(seed["item_uom_id"])
    assert got.uom == str(seed["uom"])
    assert got.uom_name == _uom_name(seed["uom"], seed["display_name"])
    assert got.ratio_to_base == int(seed["ratio_to_base"])

    missing = await svc.aresolve_active_code_for_outbound_default(
        code="UT-PMS-EXPORT-SKU-CODE-NOT-FOUND",
        enabled_only=True,
    )
    assert missing is None
