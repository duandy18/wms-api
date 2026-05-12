# tests/services/test_pms_projection_sync.py
from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pms.projection_sync import (
    SYNC_VERSION,
    sync_pms_read_projection_once,
)

pytestmark = pytest.mark.asyncio


async def _clear_projection_tables(session: AsyncSession) -> None:
    for table_name in (
        "wms_pms_barcode_projection",
        "wms_pms_sku_code_projection",
        "wms_pms_uom_projection",
        "wms_pms_item_projection",
        "wms_pms_supplier_projection",
    ):
        await session.execute(text(f"DELETE FROM {table_name}"))


def _transport(calls: list[tuple[str, str]]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        offset = int(request.url.params.get("offset", 0))
        limit = int(request.url.params.get("limit", 500))
        calls.append((path, str(request.url.query.decode("utf-8"))))

        if path == "/pms/read/v1/projection-feed/items":
            rows: list[dict[str, Any]] = [
                {
                    "item_id": 9001,
                    "sku": "SYNC-ITEM-1",
                    "name": "同步商品1",
                    "spec": None,
                    "enabled": True,
                    "supplier_id": None,
                    "brand": None,
                    "category": None,
                    "expiry_policy": "NONE",
                    "shelf_life_value": None,
                    "shelf_life_unit": None,
                    "lot_source_policy": "INTERNAL_ONLY",
                    "derivation_allowed": True,
                    "uom_governance_enabled": False,
                    "pms_updated_at": "2026-01-01T00:00:00Z",
                },
                {
                    "item_id": 9002,
                    "sku": "SYNC-ITEM-2",
                    "name": "同步商品2",
                    "spec": "规格2",
                    "enabled": False,
                    "supplier_id": 12,
                    "brand": "品牌2",
                    "category": "分类2",
                    "expiry_policy": "REQUIRED",
                    "shelf_life_value": 12,
                    "shelf_life_unit": "MONTH",
                    "lot_source_policy": "SUPPLIER_ONLY",
                    "derivation_allowed": False,
                    "uom_governance_enabled": True,
                    "pms_updated_at": "2026-01-02T00:00:00Z",
                },
            ]
            page = rows[offset : offset + limit]
            has_more = offset + limit < len(rows)
            return httpx.Response(
                200,
                json={
                    "rows": page,
                    "limit": limit,
                    "offset": offset,
                    "next_offset": offset + limit if has_more else None,
                    "has_more": has_more,
                },
            )


        if path == "/pms/read/v1/projection-feed/suppliers":
            rows = [
                {
                    "supplier_id": 7001,
                    "supplier_code": "SYNC-SUP-1",
                    "supplier_name": "同步供应商1",
                    "active": True,
                    "website": None,
                    "source_updated_at": "2026-01-02T08:00:00Z",
                },
                {
                    "supplier_id": 7002,
                    "supplier_code": "SYNC-SUP-2",
                    "supplier_name": "同步供应商2",
                    "active": False,
                    "website": "https://supplier.example",
                    "source_updated_at": "2026-01-02T09:00:00Z",
                },
            ]
            page = rows[offset : offset + limit]
            has_more = offset + limit < len(rows)
            return httpx.Response(
                200,
                json={
                    "rows": page,
                    "limit": limit,
                    "offset": offset,
                    "next_offset": offset + limit if has_more else None,
                    "has_more": has_more,
                },
            )

        if path == "/pms/read/v1/projection-feed/uoms":
            return httpx.Response(
                200,
                json={
                    "rows": [
                        {
                            "item_uom_id": 9101,
                            "item_id": 9001,
                            "uom": "PCS",
                            "display_name": "件",
                            "uom_name": "件",
                            "ratio_to_base": 1,
                            "net_weight_kg": 0.5,
                            "is_base": True,
                            "is_purchase_default": True,
                            "is_inbound_default": True,
                            "is_outbound_default": True,
                            "pms_updated_at": "2026-01-03T00:00:00Z",
                        }
                    ],
                    "limit": limit,
                    "offset": offset,
                    "next_offset": None,
                    "has_more": False,
                },
            )

        if path == "/pms/read/v1/projection-feed/sku-codes":
            return httpx.Response(
                200,
                json={
                    "rows": [
                        {
                            "sku_code_id": 9201,
                            "item_id": 9001,
                            "sku_code": "SYNC-ITEM-1",
                            "code_type": "PRIMARY",
                            "is_primary": True,
                            "is_active": True,
                            "effective_from": None,
                            "effective_to": None,
                            "pms_updated_at": "2026-01-04T00:00:00Z",
                        }
                    ],
                    "limit": limit,
                    "offset": offset,
                    "next_offset": None,
                    "has_more": False,
                },
            )

        if path == "/pms/read/v1/projection-feed/barcodes":
            return httpx.Response(
                200,
                json={
                    "rows": [
                        {
                            "barcode_id": 9301,
                            "item_id": 9001,
                            "item_uom_id": 9101,
                            "barcode": "SYNC-BARCODE-1",
                            "symbology": "CUSTOM",
                            "active": True,
                            "is_primary": True,
                            "pms_updated_at": "2026-01-05T00:00:00Z",
                        }
                    ],
                    "limit": limit,
                    "offset": offset,
                    "next_offset": None,
                    "has_more": False,
                },
            )

        return httpx.Response(404, json={"detail": f"unexpected path: {path}"})

    return httpx.MockTransport(handler)


async def test_sync_pms_read_projection_upserts_feed_rows(session: AsyncSession) -> None:
    await _clear_projection_tables(session)

    calls: list[tuple[str, str]] = []
    result = await sync_pms_read_projection_once(
        session,
        pms_api_base_url="http://pms-api.test",
        limit=1,
        transport=_transport(calls),
    )
    await session.flush()

    assert result.fetched == 7
    assert result.upserted == 7
    assert result.resources["items"].pages == 2
    assert result.resources["items"].fetched == 2
    assert result.resources["suppliers"].pages == 2
    assert result.resources["suppliers"].fetched == 2

    item = (
        await session.execute(
            text(
                """
                SELECT
                    item_id,
                    sku,
                    name,
                    enabled,
                    expiry_policy,
                    shelf_life_value,
                    shelf_life_unit,
                    lot_source_policy,
                    source_hash,
                    sync_version
                FROM wms_pms_item_projection
                WHERE item_id = 9002
                """
            )
        )
    ).mappings().one()
    assert item["sku"] == "SYNC-ITEM-2"
    assert item["enabled"] is False
    assert item["expiry_policy"] == "REQUIRED"
    assert item["shelf_life_value"] == 12
    assert item["shelf_life_unit"] == "MONTH"
    assert item["lot_source_policy"] == "SUPPLIER_ONLY"
    assert item["source_hash"]
    assert item["sync_version"] == SYNC_VERSION


    supplier = (
        await session.execute(
            text(
                """
                SELECT supplier_id, supplier_code, supplier_name, active, website, source_hash, sync_version
                FROM wms_pms_supplier_projection
                WHERE supplier_id = 7002
                """
            )
        )
    ).mappings().one()
    assert supplier["supplier_code"] == "SYNC-SUP-2"
    assert supplier["supplier_name"] == "同步供应商2"
    assert supplier["active"] is False
    assert supplier["website"] == "https://supplier.example"
    assert supplier["source_hash"]
    assert supplier["sync_version"] == SYNC_VERSION

    uom = (
        await session.execute(
            text(
                """
                SELECT item_uom_id, item_id, uom, uom_name, ratio_to_base, net_weight_kg
                FROM wms_pms_uom_projection
                WHERE item_uom_id = 9101
                """
            )
        )
    ).mappings().one()
    assert uom["item_id"] == 9001
    assert uom["uom"] == "PCS"
    assert uom["uom_name"] == "件"
    assert uom["ratio_to_base"] == 1

    sku_code = (
        await session.execute(
            text(
                """
                SELECT sku_code_id, item_id, sku_code, code_type, is_primary, is_active
                FROM wms_pms_sku_code_projection
                WHERE sku_code_id = 9201
                """
            )
        )
    ).mappings().one()
    assert sku_code["sku_code"] == "SYNC-ITEM-1"
    assert sku_code["code_type"] == "PRIMARY"
    assert sku_code["is_primary"] is True
    assert sku_code["is_active"] is True

    barcode = (
        await session.execute(
            text(
                """
                SELECT barcode_id, item_id, item_uom_id, barcode, symbology, active, is_primary
                FROM wms_pms_barcode_projection
                WHERE barcode_id = 9301
                """
            )
        )
    ).mappings().one()
    assert barcode["barcode"] == "SYNC-BARCODE-1"
    assert barcode["symbology"] == "CUSTOM"
    assert barcode["active"] is True
    assert barcode["is_primary"] is True

    called_paths = [path for path, _ in calls]
    assert called_paths == [
        "/pms/read/v1/projection-feed/items",
        "/pms/read/v1/projection-feed/items",
        "/pms/read/v1/projection-feed/suppliers",
        "/pms/read/v1/projection-feed/suppliers",
        "/pms/read/v1/projection-feed/uoms",
        "/pms/read/v1/projection-feed/sku-codes",
        "/pms/read/v1/projection-feed/barcodes",
    ]


async def test_sync_pms_read_projection_can_limit_resources(session: AsyncSession) -> None:
    await _clear_projection_tables(session)

    calls: list[tuple[str, str]] = []
    result = await sync_pms_read_projection_once(
        session,
        pms_api_base_url="http://pms-api.test",
        limit=500,
        resources=["barcodes"],
        transport=_transport(calls),
    )
    await session.flush()

    assert sorted(result.resources) == ["barcodes"]
    assert result.fetched == 1

    called_paths = [path for path, _ in calls]
    assert called_paths == ["/pms/read/v1/projection-feed/barcodes"]
