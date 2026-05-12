# tests/api/test_admin_pms_integration_api.py
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def _login_admin_headers(client: AsyncClient) -> dict[str, str]:
    r = await client.post("/users/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_pms_integration_status_lists_projection_resources(
    client: AsyncClient,
) -> None:
    headers = await _login_admin_headers(client)

    r = await client.get("/admin/pms-integration/status", headers=headers)
    assert r.status_code == 200, r.text

    data = r.json()
    assert data["pms_api_base_url_configured"] in {True, False}

    resources = {row["resource"]: row for row in data["resources"]}
    assert list(resources.keys()) == [
        "items",
        "suppliers",
        "uoms",
        "sku-codes",
        "barcodes",
    ]

    assert resources["items"]["table_name"] == "wms_pms_item_projection"
    assert resources["suppliers"]["table_name"] == "wms_pms_supplier_projection"
    assert resources["uoms"]["table_name"] == "wms_pms_uom_projection"
    assert resources["sku-codes"]["table_name"] == "wms_pms_sku_code_projection"
    assert resources["barcodes"]["table_name"] == "wms_pms_barcode_projection"

    for row in resources.values():
        assert isinstance(row["row_count"], int)
        assert row["row_count"] >= 0


@pytest.mark.asyncio
async def test_admin_pms_integration_can_list_projection_rows(
    client: AsyncClient,
) -> None:
    headers = await _login_admin_headers(client)

    r = await client.get(
        "/admin/pms-integration/projections/items?limit=5&offset=0",
        headers=headers,
    )
    assert r.status_code == 200, r.text

    data = r.json()
    assert data["resource"] == "items"
    assert data["table_name"] == "wms_pms_item_projection"
    assert data["limit"] == 5
    assert data["offset"] == 0
    assert data["total"] >= 0
    assert "item_id" in data["columns"]
    assert "sku" in data["columns"]
    assert isinstance(data["rows"], list)


@pytest.mark.asyncio
async def test_admin_pms_integration_can_check_barcode_projection(
    client: AsyncClient,
) -> None:
    headers = await _login_admin_headers(client)

    r = await client.post(
        "/admin/pms-integration/projections/barcodes/check",
        headers=headers,
    )
    assert r.status_code == 200, r.text

    data = r.json()
    assert data["resource"] == "barcodes"
    assert isinstance(data["ok"], bool)
    assert isinstance(data["issue_count"], int)
    assert isinstance(data["issues"], list)


@pytest.mark.asyncio
async def test_admin_pms_integration_sync_without_pms_base_url_returns_400_and_logs_failed_run(
    client: AsyncClient,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PMS_API_BASE_URL", raising=False)
    headers = await _login_admin_headers(client)

    r = await client.post(
        "/admin/pms-integration/projections/items/sync",
        headers=headers,
    )
    assert r.status_code == 400, r.text
    assert "PMS_API_BASE_URL" in r.text

    row = (
        await session.execute(
            text(
                """
                SELECT resource, status, error_message
                FROM wms_pms_projection_sync_runs
                WHERE resource = 'items'
                ORDER BY id DESC
                LIMIT 1
                """
            )
        )
    ).mappings().one()

    assert row["resource"] == "items"
    assert row["status"] == "FAILED"
    assert "PMS_API_BASE_URL" in str(row["error_message"])


@pytest.mark.asyncio
async def test_admin_pms_integration_sync_runs_can_be_listed(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO wms_pms_projection_sync_runs (
                resource,
                status,
                fetched,
                upserted,
                pages,
                started_at,
                finished_at,
                duration_ms,
                sync_version
            )
            VALUES (
                'suppliers',
                'SUCCESS',
                2,
                2,
                1,
                now(),
                now(),
                10,
                'ut-sync-run'
            )
            """
        )
    )
    await session.commit()

    headers = await _login_admin_headers(client)
    r = await client.get(
        "/admin/pms-integration/sync-runs?resource=suppliers&limit=5",
        headers=headers,
    )
    assert r.status_code == 200, r.text

    data = r.json()
    assert data["resource"] == "suppliers"
    assert data["limit"] == 5
    assert data["runs"]
    assert data["runs"][0]["resource"] == "suppliers"
