from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.shipping_assist.records import routes_sync

pytestmark = pytest.mark.asyncio


async def _login_headers(client: AsyncClient) -> dict[str, str]:
    resp = await client.post("/users/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _seed_mapping(session: AsyncSession, *, suffix: str) -> tuple[int, int]:
    warehouse_id = int(
        (
            await session.execute(
                text(
                    """
                    INSERT INTO warehouses (name, code, active, address)
                    VALUES (:name, :code, true, 'SYNC-API-WH-ADDR')
                    RETURNING id
                    """
                ),
                {"name": f"SYNC-API-WH-{suffix}", "code": f"SYNCAPIWH{suffix}"},
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
                        'SYNC-API-PROVIDER-ADDR'
                    )
                    RETURNING id
                    """
                ),
                {"name": f"SYNC-API-PROVIDER-{suffix}", "code": f"SYNCAPISP{suffix}"},
            )
        ).scalar_one()
    )

    await session.commit()
    return warehouse_id, provider_id


def _fact(*, suffix: str, logistics_id: int) -> dict[str, object]:
    return {
        "logistics_shipping_record_id": logistics_id,
        "order_ref": f"SYNC-API-ORDER-{suffix}",
        "platform": "PDD",
        "store_code": f"STORE-{suffix}",
        "package_no": 1,
        "warehouse_id": 999999,
        "warehouse_code": f"SYNCAPIWH{suffix}",
        "warehouse_name": "REMOTE-WH-NAME",
        "shipping_provider_id": 888888,
        "shipping_provider_code": f"SYNCAPISP{suffix}",
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


async def test_sync_from_logistics_api_upserts_shipping_record_and_refreshes_finance(
    client: AsyncClient,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suffix = uuid4().hex[:8].upper()
    warehouse_id, provider_id = await _seed_mapping(session, suffix=suffix)

    async def fake_fetch_logistics_shipping_record_facts(**kwargs: object) -> dict[str, object]:
        assert kwargs["after_id"] == 0
        assert kwargs["limit"] == 100
        assert kwargs["platform"] == "PDD"
        assert kwargs["store_code"] == f"STORE-{suffix}"
        return {
            "ok": True,
            "rows": [_fact(suffix=suffix, logistics_id=501)],
            "next_cursor": 501,
            "has_more": False,
        }

    monkeypatch.setattr(
        routes_sync,
        "fetch_logistics_shipping_record_facts",
        fake_fetch_logistics_shipping_record_facts,
    )

    headers = await _login_headers(client)
    resp = await client.post(
        "/shipping-assist/shipping/records/sync-from-logistics",
        headers=headers,
        json={
            "after_id": 0,
            "limit": 100,
            "platform": "PDD",
            "store_code": f"STORE-{suffix}",
        },
    )
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body == {
        "ok": True,
        "fetched": 1,
        "upserted": 1,
        "last_cursor": 501,
        "has_more": False,
    }

    record = (
        await session.execute(
            text(
                """
                SELECT
                  id,
                  warehouse_id,
                  shipping_provider_id,
                  shipping_provider_code,
                  tracking_no,
                  cost_estimated
                FROM shipping_records
                WHERE order_ref = :order_ref
                LIMIT 1
                """
            ),
            {"order_ref": f"SYNC-API-ORDER-{suffix}"},
        )
    ).mappings().one()

    assert int(record["warehouse_id"]) == warehouse_id
    assert int(record["shipping_provider_id"]) == provider_id
    assert record["shipping_provider_code"] == f"SYNCAPISP{suffix}"
    assert record["tracking_no"] == f"TRACK-{suffix}"
    assert float(record["cost_estimated"]) == pytest.approx(12.5)

    finance_line = (
        await session.execute(
            text(
                """
                SELECT
                  shipping_record_id,
                  warehouse_id,
                  shipping_provider_id,
                  tracking_no,
                  cost_estimated
                FROM finance_shipping_cost_lines
                WHERE shipping_record_id = :shipping_record_id
                LIMIT 1
                """
            ),
            {"shipping_record_id": int(record["id"])},
        )
    ).mappings().one()

    assert int(finance_line["warehouse_id"]) == warehouse_id
    assert int(finance_line["shipping_provider_id"]) == provider_id
    assert finance_line["tracking_no"] == f"TRACK-{suffix}"
    assert float(finance_line["cost_estimated"]) == pytest.approx(12.5)


async def test_sync_from_logistics_api_returns_409_when_mapping_missing(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suffix = uuid4().hex[:8].upper()

    async def fake_fetch_logistics_shipping_record_facts(**kwargs: object) -> dict[str, object]:
        del kwargs
        return {
            "ok": True,
            "rows": [_fact(suffix=suffix, logistics_id=601)],
            "next_cursor": 601,
            "has_more": False,
        }

    monkeypatch.setattr(
        routes_sync,
        "fetch_logistics_shipping_record_facts",
        fake_fetch_logistics_shipping_record_facts,
    )

    headers = await _login_headers(client)
    resp = await client.post(
        "/shipping-assist/shipping/records/sync-from-logistics",
        headers=headers,
        json={"after_id": 0, "limit": 100},
    )

    assert resp.status_code == 409, resp.text
    assert "warehouse_code" in resp.text
