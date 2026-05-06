from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.shipping_assist.records.sync.service import (
    LogisticsShippingRecordSyncError,
    sync_logistics_shipping_record_facts_once,
)

pytestmark = pytest.mark.asyncio


async def _seed_mapping(session: AsyncSession, *, suffix: str) -> tuple[int, int]:
    warehouse_id = int(
        (
            await session.execute(
                text(
                    """
                    INSERT INTO warehouses (name, code, active, address)
                    VALUES (:name, :code, true, 'SYNC-ADDR')
                    RETURNING id
                    """
                ),
                {
                    "name": f"SYNC-WH-{suffix}",
                    "code": f"SYNCWH{suffix}",
                },
            )
        ).scalar_one()
    )

    provider_id = int(
        (
            await session.execute(
                text(
                    """
                    INSERT INTO shipping_providers (
                        name,
                        shipping_provider_code,
                        active,
                        priority,
                        address
                    )
                    VALUES (
                        :name,
                        :code,
                        true,
                        10,
                        'SYNC-PROVIDER-ADDR'
                    )
                    RETURNING id
                    """
                ),
                {
                    "name": f"SYNC-PROVIDER-{suffix}",
                    "code": f"SYNCP{suffix}",
                },
            )
        ).scalar_one()
    )

    return warehouse_id, provider_id


async def _load_shipping_record(session: AsyncSession, *, order_ref: str) -> dict[str, object]:
    row = (
        await session.execute(
            text(
                """
                SELECT
                  id,
                  order_ref,
                  platform,
                  store_code,
                  package_no,
                  warehouse_id,
                  shipping_provider_id,
                  shipping_provider_code,
                  tracking_no,
                  freight_estimated,
                  surcharge_estimated,
                  cost_estimated,
                  gross_weight_kg,
                  dest_province,
                  dest_city
                FROM shipping_records
                WHERE order_ref = :order_ref
                LIMIT 1
                """
            ),
            {"order_ref": order_ref},
        )
    ).mappings().first()
    assert row is not None
    return dict(row)


async def _load_finance_line(session: AsyncSession, *, shipping_record_id: int) -> dict[str, object]:
    row = (
        await session.execute(
            text(
                """
                SELECT
                  shipping_record_id,
                  order_ref,
                  package_no,
                  tracking_no,
                  warehouse_id,
                  shipping_provider_id,
                  freight_estimated,
                  surcharge_estimated,
                  cost_estimated
                FROM finance_shipping_cost_lines
                WHERE shipping_record_id = :shipping_record_id
                LIMIT 1
                """
            ),
            {"shipping_record_id": int(shipping_record_id)},
        )
    ).mappings().first()
    assert row is not None
    return dict(row)


def _fact(*, suffix: str, logistics_id: int) -> dict[str, object]:
    return {
        "logistics_shipping_record_id": logistics_id,
        "order_ref": f"SYNC-ORDER-{suffix}",
        "platform": "PDD",
        "store_code": f"STORE-{suffix}",
        "package_no": 1,
        "warehouse_id": 999999,
        "warehouse_code": f"SYNCWH{suffix}",
        "warehouse_name": "REMOTE-WH-NAME",
        "shipping_provider_id": 888888,
        "shipping_provider_code": f"SYNCP{suffix}",
        "shipping_provider_name": "REMOTE-PROVIDER-NAME",
        "tracking_no": f"TRACK-{suffix}",
        "freight_estimated": 10.0,
        "surcharge_estimated": 2.5,
        "cost_estimated": 12.5,
        "gross_weight_kg": 1.25,
        "length_cm": 10.0,
        "width_cm": 20.0,
        "height_cm": 30.0,
        "sender": "张三",
        "dest_province": "北京市",
        "dest_city": "北京市",
        "created_at": datetime(2026, 5, 1, tzinfo=timezone.utc).isoformat(),
    }


async def test_sync_logistics_shipping_record_facts_upserts_by_codes_and_refreshes_finance(
    session: AsyncSession,
) -> None:
    suffix = uuid4().hex[:8].upper()
    warehouse_id, provider_id = await _seed_mapping(session, suffix=suffix)
    fact = _fact(suffix=suffix, logistics_id=101)

    async def fake_fetch(**kwargs: object) -> dict[str, object]:
        assert kwargs["after_id"] == 0
        assert kwargs["limit"] == 500
        return {"ok": True, "rows": [fact], "next_cursor": 101, "has_more": False}

    result = await sync_logistics_shipping_record_facts_once(
        session,
        after_id=0,
        fetch_facts=fake_fetch,
    )

    assert result.fetched == 1
    assert result.upserted == 1
    assert result.last_cursor == 101
    assert result.has_more is False

    record = await _load_shipping_record(session, order_ref=f"SYNC-ORDER-{suffix}")
    assert int(record["warehouse_id"]) == warehouse_id
    assert int(record["shipping_provider_id"]) == provider_id
    assert record["shipping_provider_code"] == f"SYNCP{suffix}"
    assert record["tracking_no"] == f"TRACK-{suffix}"
    assert float(record["cost_estimated"]) == pytest.approx(12.5)

    finance_line = await _load_finance_line(session, shipping_record_id=int(record["id"]))
    assert int(finance_line["warehouse_id"]) == warehouse_id
    assert int(finance_line["shipping_provider_id"]) == provider_id
    assert finance_line["tracking_no"] == f"TRACK-{suffix}"
    assert float(finance_line["cost_estimated"]) == pytest.approx(12.5)


async def test_sync_logistics_shipping_record_facts_rejects_missing_warehouse_mapping(
    session: AsyncSession,
) -> None:
    suffix = uuid4().hex[:8].upper()

    async def fake_fetch(**kwargs: object) -> dict[str, object]:
        return {
            "ok": True,
            "rows": [_fact(suffix=suffix, logistics_id=201)],
            "next_cursor": 201,
            "has_more": False,
        }

    with pytest.raises(LogisticsShippingRecordSyncError) as exc:
        await sync_logistics_shipping_record_facts_once(
            session,
            after_id=0,
            fetch_facts=fake_fetch,
        )

    assert "warehouse_code" in str(exc.value)


async def test_sync_logistics_shipping_record_facts_persists_cursor(
    session: AsyncSession,
) -> None:
    suffix = uuid4().hex[:8].upper()
    await _seed_mapping(session, suffix=suffix)

    async def fake_fetch(**kwargs: object) -> dict[str, object]:
        return {
            "ok": True,
            "rows": [_fact(suffix=suffix, logistics_id=301)],
            "next_cursor": 301,
            "has_more": True,
        }

    await sync_logistics_shipping_record_facts_once(
        session,
        after_id=None,
        fetch_facts=fake_fetch,
    )

    row = (
        await session.execute(
            text(
                """
                SELECT last_cursor
                FROM logistics_shipping_record_sync_cursors
                WHERE source = 'logistics.shipping_records'
                """
            )
        )
    ).mappings().one()

    assert int(row["last_cursor"]) == 301
