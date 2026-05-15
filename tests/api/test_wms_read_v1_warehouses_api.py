from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from app.wms.warehouses.routers import warehouses_read_v1 as router_module


class FakeMappings:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def all(self) -> list[dict[str, Any]]:
        return self._rows

    def first(self) -> dict[str, Any] | None:
        return self._rows[0] if self._rows else None


class FakeResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> FakeMappings:
        return FakeMappings(self._rows)


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(
        self,
        _stmt: object,
        params: dict[str, Any] | None = None,
    ) -> FakeResult:
        normalized_params = dict(params or {})
        self.calls.append(normalized_params)

        if "warehouse_id" in normalized_params:
            warehouse_id = int(normalized_params["warehouse_id"])
            if warehouse_id == 404:
                return FakeResult([])
            return FakeResult(
                [
                    {
                        "id": warehouse_id,
                        "code": "WH-1",
                        "name": "河北省固安第一仓库",
                        "active": True,
                    }
                ]
            )

        active = normalized_params.get("active")
        rows = [
            {
                "id": 1,
                "code": "WH-1",
                "name": "河北省固安第一仓库",
                "active": True,
            },
            {
                "id": 2,
                "code": "WH-2",
                "name": "河北第二仓库测试",
                "active": True,
            },
        ]

        if active is False:
            rows = [
                {
                    "id": 9,
                    "code": "WH-OFF",
                    "name": "停用仓",
                    "active": False,
                }
            ]

        return FakeResult(rows)


def _client(fake_session: FakeSession) -> TestClient:
    app = FastAPI()
    router = APIRouter()
    router_module.register(router)
    app.include_router(router)

    async def override_session() -> AsyncGenerator[FakeSession]:
        yield fake_session

    app.dependency_overrides[router_module.get_session] = override_session
    return TestClient(app)


def test_list_wms_read_warehouses_defaults_to_active_true() -> None:
    fake_session = FakeSession()
    response = _client(fake_session).get("/wms/read/v1/warehouses")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": 1,
                "code": "WH-1",
                "name": "河北省固安第一仓库",
                "active": True,
            },
            {
                "id": 2,
                "code": "WH-2",
                "name": "河北第二仓库测试",
                "active": True,
            },
        ]
    }
    assert fake_session.calls[0]["active"] is True


def test_list_wms_read_warehouses_can_query_inactive() -> None:
    fake_session = FakeSession()
    response = _client(fake_session).get("/wms/read/v1/warehouses?active=false")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": 9,
                "code": "WH-OFF",
                "name": "停用仓",
                "active": False,
            }
        ]
    }
    assert fake_session.calls[0]["active"] is False


def test_get_wms_read_warehouse_returns_contract() -> None:
    fake_session = FakeSession()
    response = _client(fake_session).get("/wms/read/v1/warehouses/1")

    assert response.status_code == 200
    assert response.json() == {
        "id": 1,
        "code": "WH-1",
        "name": "河北省固安第一仓库",
        "active": True,
    }


def test_get_wms_read_warehouse_returns_404() -> None:
    fake_session = FakeSession()
    response = _client(fake_session).get("/wms/read/v1/warehouses/404")

    assert response.status_code == 404
    assert response.json() == {"detail": "warehouse not found"}
