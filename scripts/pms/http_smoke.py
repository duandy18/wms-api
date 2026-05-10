# scripts/pms/http_smoke.py
from __future__ import annotations

import asyncio
import os

from app.integrations.pms.factory import (
    create_pms_read_client,
    create_sync_pms_read_client,
)


async def main() -> None:
    base_url = (os.getenv("PMS_API_BASE_URL") or "").strip()
    mode = (os.getenv("PMS_CLIENT_MODE") or "").strip()

    if mode != "http":
        raise RuntimeError("PMS_CLIENT_MODE=http is required")

    if not base_url:
        raise RuntimeError("PMS_API_BASE_URL is required")

    client = create_pms_read_client(mode="http")

    item = await client.get_item_basic(item_id=1)
    assert item is not None
    print("item:", item.id, item.sku, item.name)

    basics = await client.get_item_basics(item_ids=[1, 4002, 999999])
    assert 1 in basics
    print("basic ids:", sorted(basics))

    policy = await client.get_item_policy(item_id=1)
    assert policy is not None
    print("policy:", policy.item_id, policy.expiry_policy, policy.lot_source_policy)

    policy_by_sku = await client.get_item_policy_by_sku(sku=item.sku)
    assert policy_by_sku is not None
    print("policy_by_sku:", policy_by_sku.item_id)

    report_ids = await client.search_report_item_ids_by_keyword(keyword=item.sku, limit=10)
    assert 1 in report_ids
    print("report search ids:", report_ids)

    report_meta = await client.get_report_meta_by_item_ids(item_ids=[1, 4002])
    assert 1 in report_meta
    print(
        "report meta item 1:",
        getattr(report_meta[1], "sku"),
        getattr(report_meta[1], "barcode"),
    )

    uoms = await client.list_uoms_by_item_id(item_id=1)
    assert uoms
    print("uoms:", [(u.id, u.uom, u.ratio_to_base) for u in uoms])

    outbound_uom = await client.get_outbound_default_or_base_uom(item_id=1)
    assert outbound_uom is not None
    print("outbound uom:", outbound_uom.id, outbound_uom.uom)

    uom_by_id = await client.get_uom(item_uom_id=outbound_uom.id)
    assert uom_by_id is not None
    print("uom by id:", uom_by_id.id)

    barcodes = await client.list_barcodes_by_item_id(item_id=1)
    assert barcodes
    print("barcodes:", [(b.id, b.barcode) for b in barcodes])

    barcode = await client.get_barcode(barcode_id=barcodes[0].id)
    assert barcode is not None
    print("barcode by id:", barcode.id, barcode.barcode)

    probe = await client.probe_barcode(barcode=barcodes[0].barcode)
    assert probe.item_id == 1
    print("probe:", probe.status, probe.item_id, probe.item_uom_id)

    sku_codes = await client.list_sku_codes_by_item_id(item_id=1)
    assert sku_codes
    print("sku codes:", [(s.id, s.code) for s in sku_codes])

    sku_code = await client.get_sku_code(sku_code_id=sku_codes[0].id)
    assert sku_code is not None
    print("sku code by id:", sku_code.id, sku_code.code)

    resolved = await client.resolve_active_code_for_outbound_default(code=sku_code.code)
    assert resolved is not None
    print("resolved:", resolved.sku_code, resolved.item_id, resolved.item_uom_id)

    sync_client = create_sync_pms_read_client(mode="http")
    sync_resolved = sync_client.resolve_active_code_for_outbound_default(code=sku_code.code)
    assert sync_resolved is not None
    print(
        "sync resolved:",
        sync_resolved.sku_code,
        sync_resolved.item_id,
        sync_resolved.item_uom_id,
    )

    print("HTTP PMS smoke: OK")


if __name__ == "__main__":
    asyncio.run(main())
