# tests/services/test_pms_integration_factory.py
from __future__ import annotations

import httpx
import pytest

from app.integrations.pms.factory import (
    create_pms_read_client,
    create_sync_pms_read_client,
    get_pms_client_mode,
)
from app.integrations.pms.http_client import HttpPmsReadClient
from app.integrations.pms.sync_http_client import SyncHttpPmsReadClient


def test_get_pms_client_mode_defaults_to_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PMS_CLIENT_MODE", raising=False)

    assert get_pms_client_mode() == "http"


def test_get_pms_client_mode_reads_http_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PMS_CLIENT_MODE", "http")

    assert get_pms_client_mode() == "http"


def test_get_pms_client_mode_rejects_inprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PMS_CLIENT_MODE", "inprocess")

    with pytest.raises(RuntimeError, match="Invalid PMS_CLIENT_MODE"):
        get_pms_client_mode()


def test_create_http_pms_read_client_requires_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PMS_API_BASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="PMS_API_BASE_URL"):
        create_pms_read_client()


def test_create_http_pms_read_client() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "items_by_id": {},
                "missing_item_ids": [],
                "inactive_item_ids": [],
                "errors": [],
            },
        )
    )

    client = create_pms_read_client(
        pms_api_base_url="http://pms-api.test",
        transport=transport,
    )

    assert isinstance(client, HttpPmsReadClient)
    assert client.base_url == "http://pms-api.test"


def test_create_sync_http_pms_read_client_requires_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PMS_API_BASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="PMS_API_BASE_URL"):
        create_sync_pms_read_client()


def test_create_sync_http_pms_read_client() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
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
    )

    client = create_sync_pms_read_client(
        pms_api_base_url="http://pms-api.test",
        transport=transport,
    )

    assert isinstance(client, SyncHttpPmsReadClient)
    resolved = client.resolve_active_code_for_outbound_default(code="SKU-0001")
    assert resolved is not None
    assert resolved.item_id == 1
