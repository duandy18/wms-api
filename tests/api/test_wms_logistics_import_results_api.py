from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio
UTC = timezone.utc


async def _login_admin_headers(client: AsyncClient) -> dict[str, str]:
    r = await client.post("/users/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _seed_export_record(
    session: AsyncSession,
    *,
    source_doc_type: str = "ORDER_OUTBOUND",
    export_status: str = "PENDING",
    logistics_status: str = "NOT_IMPORTED",
    logistics_request_id: int | None = None,
    logistics_request_no: str | None = None,
) -> str:
    now = datetime.now(UTC)
    uniq = uuid4().hex[:10]
    source_ref = f"WMS:{source_doc_type}:{uniq}"
    source_doc_id = int(int(uuid4().int % 900000000) + 1000)

    await session.execute(
        text(
            """
            INSERT INTO wms_logistics_export_records (
              source_doc_type,
              source_doc_id,
              source_doc_no,
              source_ref,
              export_status,
              logistics_status,
              logistics_request_id,
              logistics_request_no,
              source_snapshot,
              created_at,
              updated_at
            )
            VALUES (
              :source_doc_type,
              :source_doc_id,
              :source_doc_no,
              :source_ref,
              :export_status,
              :logistics_status,
              :logistics_request_id,
              :logistics_request_no,
              CAST(:source_snapshot AS jsonb),
              :now,
              :now
            )
            """
        ),
        {
            "source_doc_type": source_doc_type,
            "source_doc_id": source_doc_id,
            "source_doc_no": f"DOC-{uniq}",
            "source_ref": source_ref,
            "export_status": export_status,
            "logistics_status": logistics_status,
            "logistics_request_id": logistics_request_id,
            "logistics_request_no": logistics_request_no,
            "source_snapshot": json.dumps({"seed": uniq}, ensure_ascii=False),
            "now": now,
        },
    )
    await session.commit()
    return source_ref


async def _load_export_record(
    session: AsyncSession,
    *,
    source_ref: str,
) -> dict[str, object]:
    row = (
        await session.execute(
            text(
                """
                SELECT
                  source_ref,
                  export_status,
                  logistics_status,
                  logistics_request_id,
                  logistics_request_no,
                  exported_at,
                  last_attempt_at,
                  last_error
                FROM wms_logistics_export_records
                WHERE source_ref = :source_ref
                LIMIT 1
                """
            ),
            {"source_ref": source_ref},
        )
    ).mappings().first()
    assert row is not None
    return dict(row)


async def test_logistics_import_results_marks_exported(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    headers = await _login_admin_headers(client)
    source_ref = await _seed_export_record(session)

    resp = await client.post(
        "/wms/outbound/logistics-import-results",
        headers=headers,
        json={
            "source_ref": source_ref,
            "export_status": "EXPORTED",
            "logistics_request_id": 88,
            "logistics_request_no": "LSR202605070001",
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert data["source_ref"] == source_ref
    assert data["export_status"] == "EXPORTED"
    assert data["logistics_status"] == "IMPORTED"
    assert data["logistics_request_id"] == 88
    assert data["logistics_request_no"] == "LSR202605070001"
    assert data["exported_at"] is not None
    assert data["last_attempt_at"] is not None
    assert data["last_error"] is None

    row = await _load_export_record(session, source_ref=source_ref)
    assert row["export_status"] == "EXPORTED"
    assert row["logistics_status"] == "IMPORTED"
    assert int(row["logistics_request_id"]) == 88
    assert row["logistics_request_no"] == "LSR202605070001"
    assert row["exported_at"] is not None
    assert row["last_attempt_at"] is not None
    assert row["last_error"] is None


async def test_logistics_import_results_success_is_idempotent_for_same_request(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    headers = await _login_admin_headers(client)
    source_ref = await _seed_export_record(
        session,
        export_status="EXPORTED",
        logistics_status="IMPORTED",
        logistics_request_id=88,
        logistics_request_no="LSR202605070001",
    )

    resp = await client.post(
        "/wms/outbound/logistics-import-results",
        headers=headers,
        json={
            "source_ref": source_ref,
            "export_status": "EXPORTED",
            "logistics_request_id": 88,
            "logistics_request_no": "LSR202605070001",
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["export_status"] == "EXPORTED"
    assert data["logistics_status"] == "IMPORTED"
    assert data["logistics_request_id"] == 88
    assert data["logistics_request_no"] == "LSR202605070001"


async def test_logistics_import_results_rejects_success_with_different_request(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    headers = await _login_admin_headers(client)
    source_ref = await _seed_export_record(
        session,
        export_status="EXPORTED",
        logistics_status="IMPORTED",
        logistics_request_id=88,
        logistics_request_no="LSR202605070001",
    )

    resp = await client.post(
        "/wms/outbound/logistics-import-results",
        headers=headers,
        json={
            "source_ref": source_ref,
            "export_status": "EXPORTED",
            "logistics_request_id": 99,
            "logistics_request_no": "LSR-DIFFERENT",
        },
    )

    assert resp.status_code == 409, resp.text
    assert "already_exported" in resp.text


async def test_logistics_import_results_marks_failed(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    headers = await _login_admin_headers(client)
    source_ref = await _seed_export_record(session)

    resp = await client.post(
        "/wms/outbound/logistics-import-results",
        headers=headers,
        json={
            "source_ref": source_ref,
            "export_status": "FAILED",
            "error_message": "receiver_phone is missing",
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["source_ref"] == source_ref
    assert data["export_status"] == "FAILED"
    assert data["logistics_status"] == "FAILED"
    assert data["logistics_request_id"] is None
    assert data["logistics_request_no"] is None
    assert data["last_attempt_at"] is not None
    assert data["last_error"] == "receiver_phone is missing"

    row = await _load_export_record(session, source_ref=source_ref)
    assert row["export_status"] == "FAILED"
    assert row["logistics_status"] == "FAILED"
    assert row["last_error"] == "receiver_phone is missing"


async def test_logistics_import_results_rejects_failed_after_exported(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    headers = await _login_admin_headers(client)
    source_ref = await _seed_export_record(
        session,
        export_status="EXPORTED",
        logistics_status="IMPORTED",
        logistics_request_id=88,
        logistics_request_no="LSR202605070001",
    )

    resp = await client.post(
        "/wms/outbound/logistics-import-results",
        headers=headers,
        json={
            "source_ref": source_ref,
            "export_status": "FAILED",
            "error_message": "late failure callback",
        },
    )

    assert resp.status_code == 409, resp.text
    assert "already_imported" in resp.text


async def test_logistics_import_results_returns_404_for_missing_source_ref(
    client: AsyncClient,
) -> None:
    headers = await _login_admin_headers(client)

    resp = await client.post(
        "/wms/outbound/logistics-import-results",
        headers=headers,
        json={
            "source_ref": "WMS:ORDER_OUTBOUND:NOT_FOUND",
            "export_status": "EXPORTED",
            "logistics_request_id": 88,
            "logistics_request_no": "LSR202605070001",
        },
    )

    assert resp.status_code == 404, resp.text


async def test_logistics_import_results_validates_payload_contract(
    client: AsyncClient,
) -> None:
    headers = await _login_admin_headers(client)

    missing_request = await client.post(
        "/wms/outbound/logistics-import-results",
        headers=headers,
        json={
            "source_ref": "WMS:ORDER_OUTBOUND:1",
            "export_status": "EXPORTED",
        },
    )
    assert missing_request.status_code == 422

    missing_error = await client.post(
        "/wms/outbound/logistics-import-results",
        headers=headers,
        json={
            "source_ref": "WMS:ORDER_OUTBOUND:1",
            "export_status": "FAILED",
        },
    )
    assert missing_error.status_code == 422
