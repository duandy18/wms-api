# scripts/pms/http_business_smoke.py
from __future__ import annotations

import asyncio
import os
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.wms.inbound.repos.barcode_resolve_repo import resolve_inbound_barcode
from app.wms.scan.services.scan_orchestrator_item_resolver import (
    probe_item_from_barcode,
    resolve_item_id_from_barcode,
    resolve_item_id_from_sku,
)


async def main() -> None:
    mode = (os.getenv("PMS_CLIENT_MODE") or "").strip()
    base_url = (os.getenv("PMS_API_BASE_URL") or "").strip()

    if mode != "http":
        raise RuntimeError("PMS_CLIENT_MODE=http is required")

    if not base_url:
        raise RuntimeError("PMS_API_BASE_URL is required")

    # In HTTP mode the PMS factory ignores the SQLAlchemy session.
    # We still pass a casted placeholder because the WMS business function
    # signatures have not been widened.
    session = cast(AsyncSession, None)

    barcode = (os.getenv("PMS_HTTP_SMOKE_BARCODE") or "6921734948311").strip()
    sku = (os.getenv("PMS_HTTP_SMOKE_SKU") or "SKU-0001").strip()

    scan_probe = await probe_item_from_barcode(session, barcode)
    assert scan_probe is not None
    assert scan_probe.item_id == 1
    assert scan_probe.item_uom_id == 7
    print(
        "scan probe:",
        scan_probe.item_id,
        scan_probe.item_uom_id,
        scan_probe.ratio_to_base,
        scan_probe.symbology,
    )

    item_id_from_barcode = await resolve_item_id_from_barcode(session, barcode)
    assert item_id_from_barcode == 1
    print("scan barcode item:", item_id_from_barcode)

    item_id_from_sku = await resolve_item_id_from_sku(session, sku)
    assert item_id_from_sku == 1
    print("scan sku item:", item_id_from_sku)

    inbound_probe = await resolve_inbound_barcode(session, barcode=barcode)
    assert inbound_probe is not None
    assert inbound_probe.item_id == 1
    assert inbound_probe.item_uom_id == 7
    print(
        "inbound barcode:",
        inbound_probe.item_id,
        inbound_probe.item_uom_id,
        inbound_probe.ratio_to_base,
        inbound_probe.symbology,
    )

    empty_scan = await probe_item_from_barcode(session, "")
    assert empty_scan is None

    missing_scan = await resolve_item_id_from_barcode(session, "NO-SUCH-BARCODE")
    assert missing_scan is None

    missing_sku = await resolve_item_id_from_sku(session, "NO-SUCH-SKU")
    assert missing_sku is None

    print("HTTP PMS business smoke: OK")


if __name__ == "__main__":
    asyncio.run(main())
