from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


async def _login_headers(client: AsyncClient) -> dict[str, str]:
    resp = await client.post("/users/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_shipping_records_options_returns_active_provider_and_warehouse(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    suffix = uuid4().hex[:8].upper()
    warehouse_name = f"RECORDS-OPT-WH-{suffix}"
    warehouse_code = f"ROWH{suffix}"
    provider_name = f"RECORDS-OPT-PROVIDER-{suffix}"
    provider_code = f"ROSP{suffix}"

    warehouse_id = int(
        (
            await session.execute(
                text(
                    """
                    INSERT INTO warehouses (name, code, active, address)
                    VALUES (:name, :code, true, 'records options test warehouse')
                    RETURNING id
                    """
                ),
                {"name": warehouse_name, "code": warehouse_code},
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
                      'records options test provider'
                    )
                    RETURNING id
                    """
                ),
                {"name": provider_name, "code": provider_code},
            )
        ).scalar_one()
    )

    await session.commit()

    headers = await _login_headers(client)
    resp = await client.get("/shipping-assist/records/options", headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True

    providers = body["providers"]
    warehouses = body["warehouses"]

    assert any(
        int(item["id"]) == provider_id
        and item["name"] == provider_name
        and item["shipping_provider_code"] == provider_code
        for item in providers
    )

    assert any(
        int(item["id"]) == warehouse_id
        and item["name"] == warehouse_name
        for item in warehouses
    )
