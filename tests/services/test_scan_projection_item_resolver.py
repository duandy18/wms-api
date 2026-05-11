# tests/services/test_scan_projection_item_resolver.py
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.wms.scan.services.scan_orchestrator_ingest import ingest
from app.wms.scan.services.scan_orchestrator_parse import parse_scan
from app.wms.scan.services.scan_orchestrator_item_resolver import (
    probe_item_from_barcode,
    resolve_item_id_from_barcode,
    resolve_item_id_from_sku,
)

pytestmark = pytest.mark.asyncio


async def _seed_projection(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            INSERT INTO wms_pms_item_projection (
                item_id,
                sku,
                name,
                spec,
                enabled,
                supplier_id,
                brand,
                category,
                expiry_policy,
                shelf_life_value,
                shelf_life_unit,
                lot_source_policy,
                derivation_allowed,
                uom_governance_enabled,
                pms_updated_at,
                source_hash,
                sync_version,
                synced_at
            )
            VALUES (
                991001,
                'UT-SCAN-SKU-991001',
                '扫码Projection商品991001',
                NULL,
                TRUE,
                NULL,
                NULL,
                NULL,
                'NONE',
                NULL,
                NULL,
                'INTERNAL_ONLY',
                TRUE,
                FALSE,
                now(),
                'ut-scan-item-991001',
                'ut-scan-projection',
                now()
            )
            ON CONFLICT (item_id) DO UPDATE SET
                sku = EXCLUDED.sku,
                name = EXCLUDED.name,
                enabled = EXCLUDED.enabled,
                pms_updated_at = EXCLUDED.pms_updated_at,
                source_hash = EXCLUDED.source_hash,
                sync_version = EXCLUDED.sync_version,
                synced_at = now()
            """
        )
    )

    await session.execute(
        text(
            """
            INSERT INTO wms_pms_uom_projection (
                item_uom_id,
                item_id,
                uom,
                display_name,
                uom_name,
                ratio_to_base,
                net_weight_kg,
                is_base,
                is_purchase_default,
                is_inbound_default,
                is_outbound_default,
                pms_updated_at,
                source_hash,
                sync_version,
                synced_at
            )
            VALUES (
                991011,
                991001,
                'PCS',
                '件',
                '件',
                1,
                NULL,
                TRUE,
                TRUE,
                TRUE,
                TRUE,
                now(),
                'ut-scan-uom-991011',
                'ut-scan-projection',
                now()
            )
            ON CONFLICT (item_uom_id) DO UPDATE SET
                item_id = EXCLUDED.item_id,
                uom = EXCLUDED.uom,
                display_name = EXCLUDED.display_name,
                uom_name = EXCLUDED.uom_name,
                ratio_to_base = EXCLUDED.ratio_to_base,
                is_base = EXCLUDED.is_base,
                is_purchase_default = EXCLUDED.is_purchase_default,
                is_inbound_default = EXCLUDED.is_inbound_default,
                is_outbound_default = EXCLUDED.is_outbound_default,
                pms_updated_at = EXCLUDED.pms_updated_at,
                source_hash = EXCLUDED.source_hash,
                sync_version = EXCLUDED.sync_version,
                synced_at = now()
            """
        )
    )

    await session.execute(
        text(
            """
            INSERT INTO wms_pms_barcode_projection (
                barcode_id,
                item_id,
                item_uom_id,
                barcode,
                symbology,
                active,
                is_primary,
                pms_updated_at,
                source_hash,
                sync_version,
                synced_at
            )
            VALUES (
                991021,
                991001,
                991011,
                'UT-SCAN-BARCODE-991001',
                'CUSTOM',
                TRUE,
                TRUE,
                now(),
                'ut-scan-barcode-991021',
                'ut-scan-projection',
                now()
            )
            ON CONFLICT (barcode_id) DO UPDATE SET
                item_id = EXCLUDED.item_id,
                item_uom_id = EXCLUDED.item_uom_id,
                barcode = EXCLUDED.barcode,
                symbology = EXCLUDED.symbology,
                active = EXCLUDED.active,
                is_primary = EXCLUDED.is_primary,
                pms_updated_at = EXCLUDED.pms_updated_at,
                source_hash = EXCLUDED.source_hash,
                sync_version = EXCLUDED.sync_version,
                synced_at = now()
            """
        )
    )

    await session.execute(
        text(
            """
            INSERT INTO wms_pms_sku_code_projection (
                sku_code_id,
                item_id,
                sku_code,
                code_type,
                is_primary,
                is_active,
                effective_from,
                effective_to,
                pms_updated_at,
                source_hash,
                sync_version,
                synced_at
            )
            VALUES (
                991031,
                991001,
                'UT-SCAN-SKU-991001',
                'PRIMARY',
                TRUE,
                TRUE,
                now(),
                NULL,
                now(),
                'ut-scan-sku-code-991031',
                'ut-scan-projection',
                now()
            )
            ON CONFLICT (sku_code_id) DO UPDATE SET
                item_id = EXCLUDED.item_id,
                sku_code = EXCLUDED.sku_code,
                code_type = EXCLUDED.code_type,
                is_primary = EXCLUDED.is_primary,
                is_active = EXCLUDED.is_active,
                effective_from = EXCLUDED.effective_from,
                effective_to = EXCLUDED.effective_to,
                pms_updated_at = EXCLUDED.pms_updated_at,
                source_hash = EXCLUDED.source_hash,
                sync_version = EXCLUDED.sync_version,
                synced_at = now()
            """
        )
    )


async def test_scan_barcode_probe_reads_projection_without_http(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PMS_API_BASE_URL", raising=False)
    await _seed_projection(session)
    await session.flush()

    resolved = await probe_item_from_barcode(
        session,
        "UT-SCAN-BARCODE-991001",
    )

    assert resolved is not None
    assert resolved.item_id == 991001
    assert resolved.item_uom_id == 991011
    assert resolved.ratio_to_base == 1
    assert resolved.symbology == "CUSTOM"
    assert resolved.active is True

    item_id = await resolve_item_id_from_barcode(
        session,
        "UT-SCAN-BARCODE-991001",
    )
    assert item_id == 991001


async def test_scan_sku_text_reads_projection_without_http(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PMS_API_BASE_URL", raising=False)
    await _seed_projection(session)
    await session.flush()

    item_id = await resolve_item_id_from_sku(
        session,
        "ut-scan-sku-991001",
    )

    assert item_id == 991001


async def test_scan_projection_lookup_returns_none_for_missing(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PMS_API_BASE_URL", raising=False)

    assert await probe_item_from_barcode(session, "MISSING-SCAN-BARCODE") is None
    assert await resolve_item_id_from_sku(session, "MISSING-SCAN-SKU") is None

async def test_parse_scan_raw_sku_text_reads_projection(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PMS_API_BASE_URL", raising=False)
    await _seed_projection(session)
    await session.flush()

    (
        parsed,
        mode,
        probe,
        qty,
        item_id,
        lot_code,
        warehouse_id,
        production_date,
        expiry_date,
    ) = await parse_scan(
        {
            "mode": "pick",
            "probe": True,
            "barcode": "UT-SCAN-SKU-991001",
            "qty": 1,
            "warehouse_id": 1,
        },
        session,
    )

    assert parsed["item_id"] == 991001
    assert mode == "pick"
    assert probe is True
    assert qty == 1
    assert item_id == 991001
    assert lot_code is None
    assert warehouse_id == 1
    assert production_date is None
    assert expiry_date is None


async def test_scan_ingest_pick_probe_uses_projection_without_base_kwargs_error(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PMS_API_BASE_URL", raising=False)
    await _seed_projection(session)
    await session.flush()

    result = await ingest(
        {
            "mode": "pick",
            "probe": True,
            "barcode": "UT-SCAN-BARCODE-991001",
            "qty": 1,
            "warehouse_id": 1,
        },
        session,
    )

    assert result["ok"] is True
    assert result["committed"] is False
    assert result["source"] == "scan_pick_probe_parse_only"
    assert result["item_id"] == 991001
    assert result["item_uom_id"] == 991011
    assert result["ratio_to_base"] == 1
    assert result["qty_base"] == 1
    assert result["errors"] == []
