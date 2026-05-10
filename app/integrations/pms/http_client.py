# app/integrations/pms/http_client.py
"""
HTTP PMS read client.

This client is the future PMS integration implementation for the
independent pms-api process.

Important:
- It is not wired into WMS / OMS / Procurement / Finance yet.
- It does not fallback to InProcessPmsReadClient.
- A deployment must explicitly choose this implementation.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping, Sequence
from types import SimpleNamespace
from typing import Any, NoReturn, TypeVar

import httpx

from app.integrations.pms.contracts import (
    BarcodeProbeOut,
    ItemBasic,
    ItemPolicy,
    ItemReadQuery,
    PmsExportBarcode,
    PmsExportSkuCode,
    PmsExportSkuCodeResolution,
    PmsExportUom,
)

ModelT = TypeVar("ModelT")


def _clean_ids(values: Iterable[int]) -> list[int]:
    return sorted({int(value) for value in values if int(value) > 0})


def _base_url(value: str | None) -> str:
    raw = (value or os.getenv("PMS_API_BASE_URL") or "").strip()
    if not raw:
        raise RuntimeError("PMS_API_BASE_URL is required for HttpPmsReadClient")
    return raw.rstrip("/")


def _parse_model(model_type: type[ModelT], data: Mapping[str, Any]) -> ModelT:
    validator = getattr(model_type, "model_validate", None)
    if callable(validator):
        return validator(data)
    return model_type(**data)  # type: ignore[misc]


def _parse_model_list(model_type: type[ModelT], rows: object) -> list[ModelT]:
    if not isinstance(rows, list):
        return []
    return [_parse_model(model_type, row) for row in rows if isinstance(row, Mapping)]


def _parse_model_map(
    model_type: type[ModelT],
    body: Mapping[str, Any],
    field: str,
) -> dict[int, ModelT]:
    raw = body.get(field)
    if not isinstance(raw, Mapping):
        return {}

    out: dict[int, ModelT] = {}
    for key, value in raw.items():
        if not isinstance(value, Mapping):
            continue
        out[int(key)] = _parse_model(model_type, value)
    return out


def _parse_object_map(body: Mapping[str, Any], field: str) -> dict[int, object]:
    raw = body.get(field)
    if not isinstance(raw, Mapping):
        return {}

    out: dict[int, object] = {}
    for key, value in raw.items():
        if isinstance(value, Mapping):
            out[int(key)] = SimpleNamespace(**dict(value))
    return out


class HttpPmsReadClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.base_url = _base_url(base_url)
        self.timeout = httpx.Timeout(timeout_seconds)
        self.transport = transport
        self.headers = dict(headers or {})

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        none_status_codes: set[int] | None = None,
    ) -> Mapping[str, Any] | None:
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            transport=self.transport,
            headers=self.headers,
        ) as client:
            response = await client.request(
                method,
                path,
                json=json_body,
                params=params,
            )

        if none_status_codes and response.status_code in none_status_codes:
            return None

        response.raise_for_status()
        data = response.json()
        if not isinstance(data, Mapping):
            raise ValueError(f"pms-api response must be object: path={path}")
        return data

    @staticmethod
    def _unsupported(method: str) -> NoReturn:
        raise NotImplementedError(
            f"HttpPmsReadClient.{method} is not supported by current pms-api HTTP surface"
        )

    async def list_item_basics(
        self,
        *,
        query: ItemReadQuery | None = None,
    ) -> list[ItemBasic]:
        _ = query
        self._unsupported("list_item_basics")

    async def get_item_basic(self, *, item_id: int) -> ItemBasic | None:
        rows = await self.get_item_basics(item_ids=[int(item_id)])
        return rows.get(int(item_id))

    async def get_item_basics(
        self,
        *,
        item_ids: Iterable[int],
    ) -> dict[int, ItemBasic]:
        ids = _clean_ids(item_ids)
        if not ids:
            return {}

        body = await self._request(
            "POST",
            "/pms/read/v1/items/basic/batch",
            json_body={"item_ids": ids, "enabled_only": False},
        )
        assert body is not None
        return _parse_model_map(ItemBasic, body, "items_by_id")

    async def get_item_policy(self, *, item_id: int) -> ItemPolicy | None:
        rows = await self.get_item_policies(item_ids=[int(item_id)])
        return rows.get(int(item_id))

    async def get_item_policies(
        self,
        *,
        item_ids: Iterable[int],
    ) -> dict[int, ItemPolicy]:
        ids = _clean_ids(item_ids)
        if not ids:
            return {}

        body = await self._request(
            "POST",
            "/pms/read/v1/items/policies/batch",
            json_body={"item_ids": ids, "enabled_only": False},
        )
        assert body is not None
        return _parse_model_map(ItemPolicy, body, "policies_by_item_id")

    async def get_item_policy_by_sku(self, *, sku: str) -> ItemPolicy | None:
        _ = sku
        self._unsupported("get_item_policy_by_sku")

    async def search_report_item_ids_by_keyword(
        self,
        *,
        keyword: str,
        limit: int | None = None,
    ) -> list[int]:
        params: dict[str, Any] = {"keyword": str(keyword)}
        if limit is not None:
            params["limit"] = int(limit)

        body = await self._request(
            "GET",
            "/pms/read/v1/items/report-search",
            params=params,
        )
        assert body is not None
        item_ids = body.get("item_ids")
        if not isinstance(item_ids, list):
            return []
        return [int(value) for value in item_ids]

    async def get_report_meta_by_item_ids(
        self,
        *,
        item_ids: Iterable[int],
    ) -> dict[int, object]:
        ids = _clean_ids(item_ids)
        if not ids:
            return {}

        body = await self._request(
            "POST",
            "/pms/read/v1/items/report-meta/batch",
            json_body={"item_ids": ids, "enabled_only": False},
        )
        assert body is not None
        return _parse_object_map(body, "meta_by_item_id")

    async def get_uom(self, *, item_uom_id: int) -> PmsExportUom | None:
        rows = await self.list_uoms(item_uom_ids=[int(item_uom_id)])
        return rows[0] if rows else None

    async def list_uoms(
        self,
        *,
        item_ids: Sequence[int] | None = None,
        item_uom_ids: Sequence[int] | None = None,
    ) -> list[PmsExportUom]:
        body = await self._request(
            "POST",
            "/pms/read/v1/uoms/query",
            json_body={
                "item_ids": _clean_ids(item_ids or []),
                "item_uom_ids": _clean_ids(item_uom_ids or []),
            },
        )
        assert body is not None
        return _parse_model_list(PmsExportUom, body.get("uoms"))

    async def list_uoms_by_item_id(self, *, item_id: int) -> list[PmsExportUom]:
        return await self.list_uoms(item_ids=[int(item_id)])

    async def _get_default_or_base_uom(
        self,
        *,
        item_id: int,
        usage: str,
    ) -> PmsExportUom | None:
        body = await self._request(
            "POST",
            "/pms/read/v1/items/uom-defaults/batch",
            json_body={"item_ids": [int(item_id)], "usage": usage},
        )
        assert body is not None
        raw = body.get("uoms_by_item_id")
        if not isinstance(raw, Mapping):
            return None
        value = raw.get(str(int(item_id))) or raw.get(int(item_id))
        if not isinstance(value, Mapping):
            return None
        return _parse_model(PmsExportUom, value)

    async def get_purchase_default_or_base_uom(
        self,
        *,
        item_id: int,
    ) -> PmsExportUom | None:
        return await self._get_default_or_base_uom(item_id=int(item_id), usage="PURCHASE")

    async def get_inbound_default_or_base_uom(
        self,
        *,
        item_id: int,
    ) -> PmsExportUom | None:
        return await self._get_default_or_base_uom(item_id=int(item_id), usage="INBOUND")

    async def get_outbound_default_or_base_uom(
        self,
        *,
        item_id: int,
    ) -> PmsExportUom | None:
        return await self._get_default_or_base_uom(item_id=int(item_id), usage="OUTBOUND")

    async def get_barcode(self, *, barcode_id: int) -> PmsExportBarcode | None:
        _ = barcode_id
        self._unsupported("get_barcode")

    async def list_barcodes(
        self,
        *,
        item_ids: Sequence[int] | None = None,
        item_uom_ids: Sequence[int] | None = None,
        barcode: str | None = None,
        active: bool | None = None,
        primary_only: bool = False,
    ) -> list[PmsExportBarcode]:
        body = await self._request(
            "POST",
            "/pms/read/v1/barcodes/query",
            json_body={
                "item_ids": _clean_ids(item_ids or []),
                "item_uom_ids": _clean_ids(item_uom_ids or []),
                "barcode": barcode,
                "active": active,
                "primary_only": bool(primary_only),
            },
        )
        assert body is not None
        return _parse_model_list(PmsExportBarcode, body.get("barcodes"))

    async def list_barcodes_by_item_id(
        self,
        *,
        item_id: int,
        active: bool | None = True,
        primary_only: bool = False,
    ) -> list[PmsExportBarcode]:
        return await self.list_barcodes(
            item_ids=[int(item_id)],
            active=active,
            primary_only=primary_only,
        )

    async def probe_barcode(self, *, barcode: str) -> BarcodeProbeOut:
        body = await self._request(
            "POST",
            "/pms/read/v1/barcodes/probe",
            json_body={"barcode": str(barcode)},
        )
        assert body is not None
        return _parse_model(BarcodeProbeOut, body)

    async def get_sku_code(self, *, sku_code_id: int) -> PmsExportSkuCode | None:
        rows = await self.list_sku_codes(sku_code_ids=[int(sku_code_id)])
        return rows[0] if rows else None

    async def list_sku_codes(
        self,
        *,
        item_ids: Sequence[int] | None = None,
        sku_code_ids: Sequence[int] | None = None,
        code: str | None = None,
        active: bool | None = None,
        primary_only: bool = False,
    ) -> list[PmsExportSkuCode]:
        body = await self._request(
            "POST",
            "/pms/read/v1/sku-codes/query",
            json_body={
                "item_ids": _clean_ids(item_ids or []),
                "sku_code_ids": _clean_ids(sku_code_ids or []),
                "code": code,
                "active": active,
                "primary_only": bool(primary_only),
            },
        )
        assert body is not None
        return _parse_model_list(PmsExportSkuCode, body.get("sku_codes"))

    async def list_sku_codes_by_item_id(
        self,
        *,
        item_id: int,
        active: bool | None = True,
        primary_only: bool = False,
    ) -> list[PmsExportSkuCode]:
        return await self.list_sku_codes(
            item_ids=[int(item_id)],
            active=active,
            primary_only=primary_only,
        )

    async def resolve_active_code_for_outbound_default(
        self,
        *,
        code: str,
        enabled_only: bool = True,
    ) -> PmsExportSkuCodeResolution | None:
        body = await self._request(
            "GET",
            "/pms/read/v1/sku-codes/resolve-outbound-default",
            params={"code": str(code), "enabled_only": bool(enabled_only)},
            none_status_codes={404, 409, 422},
        )
        if body is None:
            return None
        return _parse_model(PmsExportSkuCodeResolution, body)


__all__ = ["HttpPmsReadClient"]
