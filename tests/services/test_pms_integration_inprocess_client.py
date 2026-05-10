# tests/services/test_pms_integration_inprocess_client.py
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pms.contracts import BarcodeProbeStatus
from app.integrations.pms.inprocess_client import InProcessPmsReadClient

pytestmark = pytest.mark.asyncio


async def _pick_export_capable_row(session: AsyncSession) -> dict:
    row = (
        await session.execute(
            text(
                """
                SELECT
                  i.id AS item_id,
                  i.sku AS item_sku,
                  i.name AS item_name,
                  u.id AS item_uom_id,
                  b.id AS barcode_id,
                  b.barcode,
                  sc.id AS sku_code_id,
                  sc.code AS sku_code
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

    assert row is not None, "test baseline must contain PMS item/uom/barcode/sku-code seed row"
    return dict(row)


async def test_inprocess_pms_read_client_reads_basic_uom_barcode_and_sku(
    session: AsyncSession,
) -> None:
    seed = await _pick_export_capable_row(session)
    client = InProcessPmsReadClient(session)

    item = await client.get_item_basic(item_id=int(seed["item_id"]))
    assert item is not None
    assert item.id == int(seed["item_id"])
    assert item.sku == str(seed["item_sku"])
    assert item.name == str(seed["item_name"])

    uom = await client.get_uom(item_uom_id=int(seed["item_uom_id"]))
    assert uom is not None
    assert uom.id == int(seed["item_uom_id"])
    assert uom.item_id == int(seed["item_id"])

    probe = await client.probe_barcode(barcode=f"  {seed['barcode']}  ")
    assert probe.status is BarcodeProbeStatus.BOUND
    assert probe.item_id == int(seed["item_id"])
    assert probe.item_uom_id == int(seed["item_uom_id"])

    sku_rows = await client.list_sku_codes(
        code=str(seed["sku_code"]).lower(),
        active=True,
    )
    assert any(row.id == int(seed["sku_code_id"]) for row in sku_rows)
    assert any(row.item_id == int(seed["item_id"]) for row in sku_rows)
