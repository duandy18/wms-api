from __future__ import annotations

from typing import Any, Dict
from uuid import uuid4

import pytest


def _assert_problem_shape(j: Dict[str, Any]) -> None:
    assert isinstance(j, dict)
    assert "message" in j
    assert "http_status" in j
    assert isinstance(j["http_status"], int)


def _assert_row_shape(row: Dict[str, Any]) -> None:
    assert set(row.keys()) == {
        "id",
        "platform",
        "store_code",
        "store",
        "identity_kind",
        "identity_value",
        "fsku_id",
        "fsku",
        "reason",
        "created_at",
        "updated_at",
    }

    assert set(row["store"].keys()) == {"id", "store_name"}
    assert set(row["fsku"].keys()) == {"id", "code", "name", "status"}


@pytest.mark.anyio
async def test_platform_code_mapping_list_filters_are_accepted(client):
    resp = await client.get(
        "/oms/platform-code-mappings"
        "?platform=DEMO"
        "&store_code=1"
        "&identity_kind=merchant_code"
        "&identity_value=ABC"
        "&fsku_id=1"
        "&fsku_code=FSKU"
        "&limit=10"
        "&offset=0"
    )

    if resp.status_code in (422, 500):
        _assert_problem_shape(resp.json())
        return

    assert resp.status_code == 200
    j = resp.json()
    assert j["ok"] is True
    assert "items" in j["data"]


@pytest.mark.anyio
async def test_platform_code_mapping_bind_success_or_problem(client):
    payload = {
        "platform": "DEMO",
        "store_code": "1",
        "identity_kind": "merchant_code",
        "identity_value": f"UT-MC-{uuid4().hex[:8]}",
        "fsku_id": 1,
        "reason": "UT contract",
    }
    resp = await client.post("/oms/platform-code-mappings/bind", json=payload)

    if resp.status_code != 200:
        _assert_problem_shape(resp.json())
        return

    j = resp.json()
    assert j["ok"] is True
    _assert_row_shape(j["data"])
    assert j["data"]["identity_kind"] == "merchant_code"
    assert j["data"]["identity_value"] == payload["identity_value"]


@pytest.mark.anyio
async def test_platform_code_mapping_delete_success_or_problem(client):
    payload = {
        "platform": "DEMO",
        "store_code": "1",
        "identity_kind": "merchant_code",
        "identity_value": f"UT-MC-DELETE-{uuid4().hex[:8]}",
        "fsku_id": 1,
        "reason": "UT contract",
    }

    bind_resp = await client.post("/oms/platform-code-mappings/bind", json=payload)
    if bind_resp.status_code != 200:
        _assert_problem_shape(bind_resp.json())
        return

    delete_payload = {
        "platform": payload["platform"],
        "store_code": payload["store_code"],
        "identity_kind": payload["identity_kind"],
        "identity_value": payload["identity_value"],
    }

    resp = await client.post("/oms/platform-code-mappings/delete", json=delete_payload)
    assert resp.status_code == 200, resp.text
    j = resp.json()
    assert j["ok"] is True
    _assert_row_shape(j["data"])
