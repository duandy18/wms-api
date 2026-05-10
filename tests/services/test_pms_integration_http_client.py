# tests/services/test_pms_integration_http_client.py
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.integrations.pms.contracts import BarcodeProbeStatus
from app.integrations.pms.http_client import HttpPmsReadClient

pytestmark = pytest.mark.asyncio


def _json(request: httpx.Request) -> dict[str, Any]:
    if not request.content:
        return {}
    return json.loads(request.content.decode("utf-8"))


def _transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path

        if path == "/pms/read/v1/items/basic":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "sku": "SKU-0001",
                        "name": "笔记本",
                        "spec": None,
                        "enabled": True,
                        "supplier_id": 3,
                        "brand": "得力",
                        "category": "办公用品",
                    }
                ],
            )

        if path == "/pms/read/v1/items/basic/batch":
            payload = _json(request)
            assert payload["item_ids"] in ([1, 2], [1])
            return httpx.Response(
                200,
                json={
                    "items_by_id": {
                        "1": {
                            "id": 1,
                            "sku": "SKU-0001",
                            "name": "笔记本",
                            "spec": None,
                            "enabled": True,
                            "supplier_id": 3,
                            "brand": "得力",
                            "category": "办公用品",
                        }
                    },
                    "missing_item_ids": [2],
                    "inactive_item_ids": [],
                    "errors": [],
                },
            )

        if path == "/pms/read/v1/items/policy-by-sku":
            if request.url.params["sku"] == "MISSING":
                return httpx.Response(404, json={"detail": "pms_item_policy_not_found"})
            return httpx.Response(
                200,
                json={
                    "item_id": 1,
                    "expiry_policy": "NONE",
                    "shelf_life_value": None,
                    "shelf_life_unit": None,
                    "lot_source_policy": "INTERNAL_ONLY",
                    "derivation_allowed": True,
                    "uom_governance_enabled": False,
                },
            )

        if path == "/pms/read/v1/items/policies/batch":
            return httpx.Response(
                200,
                json={
                    "policies_by_item_id": {
                        "1": {
                            "item_id": 1,
                            "expiry_policy": "NONE",
                            "shelf_life_value": None,
                            "shelf_life_unit": None,
                            "lot_source_policy": "INTERNAL_ONLY",
                            "derivation_allowed": True,
                            "uom_governance_enabled": False,
                        }
                    },
                    "missing_item_ids": [],
                    "inactive_item_ids": [],
                    "errors": [],
                },
            )

        if path == "/pms/read/v1/items/report-search":
            assert request.url.params["keyword"] == "笔"
            return httpx.Response(200, json={"item_ids": [1, 2]})

        if path == "/pms/read/v1/items/report-meta/batch":
            return httpx.Response(
                200,
                json={
                    "meta_by_item_id": {
                        "1": {
                            "item_id": 1,
                            "sku": "SKU-0001",
                            "name": "笔记本",
                            "brand": "得力",
                            "category": "办公用品",
                            "barcode": "6921734948311",
                        }
                    },
                    "missing_item_ids": [],
                    "errors": [],
                },
            )

        if path == "/pms/read/v1/uoms/query":
            return httpx.Response(
                200,
                json={
                    "uoms": [
                        {
                            "id": 7,
                            "item_id": 1,
                            "uom": "本",
                            "display_name": None,
                            "uom_name": "本",
                            "ratio_to_base": 1,
                            "net_weight_kg": 0.2,
                            "is_base": True,
                            "is_purchase_default": False,
                            "is_inbound_default": True,
                            "is_outbound_default": True,
                        }
                    ],
                    "missing_item_uom_ids": [],
                    "errors": [],
                },
            )

        if path == "/pms/read/v1/items/uom-defaults/batch":
            return httpx.Response(
                200,
                json={
                    "uoms_by_item_id": {
                        "1": {
                            "id": 7,
                            "item_id": 1,
                            "uom": "本",
                            "display_name": None,
                            "uom_name": "本",
                            "ratio_to_base": 1,
                            "net_weight_kg": 0.2,
                            "is_base": True,
                            "is_purchase_default": False,
                            "is_inbound_default": True,
                            "is_outbound_default": True,
                        }
                    },
                    "missing_item_ids": [],
                    "missing_default_uom_item_ids": [],
                    "errors": [],
                },
            )

        if path == "/pms/read/v1/barcodes/2":
            return httpx.Response(
                200,
                json={
                    "id": 2,
                    "item_id": 1,
                    "item_uom_id": 7,
                    "barcode": "6921734948311",
                    "symbology": "CUSTOM",
                    "active": True,
                    "is_primary": True,
                    "uom": "本",
                    "display_name": None,
                    "uom_name": "本",
                    "ratio_to_base": 1,
                },
            )

        if path == "/pms/read/v1/barcodes/query":
            return httpx.Response(
                200,
                json={
                    "barcodes": [
                        {
                            "id": 2,
                            "item_id": 1,
                            "item_uom_id": 7,
                            "barcode": "6921734948311",
                            "symbology": "CUSTOM",
                            "active": True,
                            "is_primary": True,
                            "uom": "本",
                            "display_name": None,
                            "uom_name": "本",
                            "ratio_to_base": 1,
                        }
                    ],
                    "errors": [],
                },
            )

        if path == "/pms/read/v1/barcodes/probe":
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "status": "BOUND",
                    "barcode": "6921734948311",
                    "item_id": 1,
                    "item_uom_id": 7,
                    "ratio_to_base": 1,
                    "symbology": "CUSTOM",
                    "active": True,
                    "item_basic": {
                        "id": 1,
                        "sku": "SKU-0001",
                        "name": "笔记本",
                        "spec": None,
                        "enabled": True,
                        "supplier_id": 3,
                        "brand": "得力",
                        "category": "办公用品",
                    },
                    "errors": [],
                },
            )

        if path == "/pms/read/v1/sku-codes/query":
            return httpx.Response(
                200,
                json={
                    "sku_codes": [
                        {
                            "id": 10,
                            "item_id": 1,
                            "code": "SKU-0001",
                            "code_type": "PRIMARY",
                            "is_primary": True,
                            "is_active": True,
                            "effective_from": None,
                            "effective_to": None,
                            "remark": None,
                            "item_sku": "SKU-0001",
                            "item_name": "笔记本",
                            "item_enabled": True,
                        }
                    ],
                    "errors": [],
                },
            )

        if path == "/pms/read/v1/sku-codes/resolve-outbound-default":
            if request.url.params["code"] == "MISSING":
                return httpx.Response(404, json={"detail": "pms_sku_code_not_found"})

            return httpx.Response(
                200,
                json={
                    "sku_code_id": 10,
                    "item_id": 1,
                    "sku_code": "SKU-0001",
                    "code_type": "PRIMARY",
                    "is_primary": True,
                    "item_sku": "SKU-0001",
                    "item_name": "笔记本",
                    "item_uom_id": 7,
                    "uom": "本",
                    "display_name": None,
                    "uom_name": "本",
                    "ratio_to_base": 1,
                },
            )

        return httpx.Response(404, json={"detail": f"unexpected path: {path}"})

    return httpx.MockTransport(handler)


def _client() -> HttpPmsReadClient:
    return HttpPmsReadClient(
        base_url="http://pms-api.test",
        transport=_transport(),
    )


async def test_http_pms_read_client_reads_item_basic_policy_and_report_meta() -> None:
    client = _client()

    basics = await client.get_item_basics(item_ids=[2, 1, 1, 0])
    assert sorted(basics) == [1]
    assert basics[1].sku == "SKU-0001"

    item = await client.get_item_basic(item_id=1)
    assert item is not None
    assert item.name == "笔记本"

    policies = await client.get_item_policies(item_ids=[1])
    assert policies[1].expiry_policy == "NONE"

    policy = await client.get_item_policy(item_id=1)
    assert policy is not None
    assert policy.lot_source_policy == "INTERNAL_ONLY"

    ids = await client.search_report_item_ids_by_keyword(keyword="笔", limit=10)
    assert ids == [1, 2]

    meta = await client.get_report_meta_by_item_ids(item_ids=[1])
    assert getattr(meta[1], "barcode") == "6921734948311"


async def test_http_pms_read_client_reads_uom_barcode_and_sku_code() -> None:
    client = _client()

    uom = await client.get_uom(item_uom_id=7)
    assert uom is not None
    assert uom.uom == "本"

    uoms = await client.list_uoms_by_item_id(item_id=1)
    assert uoms[0].id == 7

    outbound_uom = await client.get_outbound_default_or_base_uom(item_id=1)
    assert outbound_uom is not None
    assert outbound_uom.id == 7

    barcodes = await client.list_barcodes_by_item_id(item_id=1)
    assert barcodes[0].barcode == "6921734948311"

    probe = await client.probe_barcode(barcode="6921734948311")
    assert probe.status is BarcodeProbeStatus.BOUND
    assert probe.item_id == 1
    assert probe.item_basic is not None
    assert probe.item_basic.sku == "SKU-0001"

    sku_codes = await client.list_sku_codes(item_ids=[1], active=True)
    assert sku_codes[0].code == "SKU-0001"

    sku_code = await client.get_sku_code(sku_code_id=10)
    assert sku_code is not None
    assert sku_code.item_id == 1

    resolved = await client.resolve_active_code_for_outbound_default(code="SKU-0001")
    assert resolved is not None
    assert resolved.item_uom_id == 7

    missing = await client.resolve_active_code_for_outbound_default(code="MISSING")
    assert missing is None


async def test_http_pms_read_client_requires_explicit_base_url(monkeypatch) -> None:
    monkeypatch.delenv("PMS_API_BASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="PMS_API_BASE_URL"):
        HttpPmsReadClient()


async def test_http_pms_read_client_compat_methods_are_backed_by_http() -> None:
    client = _client()

    rows = await client.list_item_basics()
    assert len(rows) == 1
    assert rows[0].sku == "SKU-0001"

    policy = await client.get_item_policy_by_sku(sku="SKU-0001")
    assert policy is not None
    assert policy.item_id == 1
    assert policy.expiry_policy == "NONE"

    missing_policy = await client.get_item_policy_by_sku(sku="MISSING")
    assert missing_policy is None

    barcode = await client.get_barcode(barcode_id=2)
    assert barcode is not None
    assert barcode.barcode == "6921734948311"
