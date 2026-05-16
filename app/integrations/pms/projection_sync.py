# app/integrations/pms/projection_sync.py
"""
Sync WMS-owned PMS read projection tables from pms-api read-v1 HTTP feed.

Boundary:
- Source must be pms-api /pms/read/v1/projection-feed/*.
- This module must not read PMS owner tables directly.
- This module only writes WMS-owned projection tables.
- Projection is a current-state read index, not snapshot and not write validation.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

import httpx
from sqlalchemy import text

from app.integrations.pms.service_auth import pms_service_auth_headers
from sqlalchemy.ext.asyncio import AsyncSession

ProjectionResource = Literal["items", "suppliers", "uoms", "sku-codes", "barcodes"]

SYNC_VERSION = "pms-read-v1-projection-feed"
DEFAULT_LIMIT = 500
MAX_LIMIT = 500

RESOURCE_ORDER: tuple[ProjectionResource, ...] = (
    "items",
    "suppliers",
    "uoms",
    "sku-codes",
    "barcodes",
)

RESOURCE_PATHS: dict[ProjectionResource, str] = {
    "items": "/pms/read/v1/projection-feed/items",
    "suppliers": "/pms/read/v1/projection-feed/suppliers",
    "uoms": "/pms/read/v1/projection-feed/uoms",
    "sku-codes": "/pms/read/v1/projection-feed/sku-codes",
    "barcodes": "/pms/read/v1/projection-feed/barcodes",
}


class PmsProjectionSyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class PmsProjectionResourceSyncResult:
    resource: ProjectionResource
    fetched: int
    upserted: int
    pages: int
    last_offset: int
    has_more: bool


@dataclass(frozen=True)
class PmsProjectionSyncResult:
    resources: dict[ProjectionResource, PmsProjectionResourceSyncResult]

    @property
    def fetched(self) -> int:
        return sum(row.fetched for row in self.resources.values())

    @property
    def upserted(self) -> int:
        return sum(row.upserted for row in self.resources.values())


def _base_url(value: str | None = None) -> str:
    raw = (value or os.getenv("PMS_API_BASE_URL") or "").strip()
    if not raw:
        raise RuntimeError("PMS_API_BASE_URL is required for PMS projection sync")
    return raw.rstrip("/")


def _safe_limit(value: int) -> int:
    return max(1, min(int(value), MAX_LIMIT))


def _as_mapping(value: object, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PmsProjectionSyncError(f"{context} must be an object")
    return value


def _required_int(row: Mapping[str, Any], key: str) -> int:
    value = row.get(key)
    if value is None:
        raise PmsProjectionSyncError(f"PMS projection feed row missing required field: {key}")
    return int(value)


def _required_str(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if value is None:
        raise PmsProjectionSyncError(f"PMS projection feed row missing required field: {key}")
    text_value = str(value).strip()
    if not text_value:
        raise PmsProjectionSyncError(f"PMS projection feed row has blank required field: {key}")
    return text_value


def _optional_str(row: Mapping[str, Any], key: str) -> str | None:
    value = row.get(key)
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


def _required_bool(row: Mapping[str, Any], key: str) -> bool:
    value = row.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "t", "1", "yes", "y"}:
            return True
        if lowered in {"false", "f", "0", "no", "n"}:
            return False
    raise PmsProjectionSyncError(f"PMS projection feed row has invalid boolean field: {key}")


def _optional_int(row: Mapping[str, Any], key: str) -> int | None:
    value = row.get(key)
    return int(value) if value is not None else None


def _optional_decimal(row: Mapping[str, Any], key: str) -> Decimal | None:
    value = row.get(key)
    return Decimal(str(value)) if value is not None else None


def _optional_datetime(row: Mapping[str, Any], key: str) -> datetime | None:
    value = row.get(key)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _required_datetime(row: Mapping[str, Any], key: str) -> datetime:
    value = _optional_datetime(row, key)
    if value is None:
        raise PmsProjectionSyncError(f"PMS projection feed row missing required field: {key}")
    return value


def _source_hash(row: Mapping[str, Any]) -> str:
    payload = json.dumps(
        dict(row),
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _item_params(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "item_id": _required_int(row, "item_id"),
        "sku": _required_str(row, "sku"),
        "name": _required_str(row, "name"),
        "spec": _optional_str(row, "spec"),
        "enabled": _required_bool(row, "enabled"),
        "supplier_id": _optional_int(row, "supplier_id"),
        "brand": _optional_str(row, "brand"),
        "category": _optional_str(row, "category"),
        "expiry_policy": _required_str(row, "expiry_policy"),
        "shelf_life_value": _optional_int(row, "shelf_life_value"),
        "shelf_life_unit": _optional_str(row, "shelf_life_unit"),
        "lot_source_policy": _required_str(row, "lot_source_policy"),
        "derivation_allowed": _required_bool(row, "derivation_allowed"),
        "uom_governance_enabled": _required_bool(row, "uom_governance_enabled"),
        "pms_updated_at": _required_datetime(row, "pms_updated_at"),
        "source_hash": _source_hash(row),
        "sync_version": SYNC_VERSION,
    }


def _supplier_params(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "supplier_id": _required_int(row, "supplier_id"),
        "supplier_code": _required_str(row, "supplier_code"),
        "supplier_name": _required_str(row, "supplier_name"),
        "active": _required_bool(row, "active"),
        "website": _optional_str(row, "website"),
        "pms_updated_at": _optional_datetime(row, "source_updated_at"),
        "source_hash": _source_hash(row),
        "sync_version": SYNC_VERSION,
    }



def _uom_params(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "item_uom_id": _required_int(row, "item_uom_id"),
        "item_id": _required_int(row, "item_id"),
        "uom": _required_str(row, "uom"),
        "display_name": _optional_str(row, "display_name"),
        "uom_name": _required_str(row, "uom_name"),
        "ratio_to_base": _required_int(row, "ratio_to_base"),
        "net_weight_kg": _optional_decimal(row, "net_weight_kg"),
        "is_base": _required_bool(row, "is_base"),
        "is_purchase_default": _required_bool(row, "is_purchase_default"),
        "is_inbound_default": _required_bool(row, "is_inbound_default"),
        "is_outbound_default": _required_bool(row, "is_outbound_default"),
        "pms_updated_at": _required_datetime(row, "pms_updated_at"),
        "source_hash": _source_hash(row),
        "sync_version": SYNC_VERSION,
    }


def _sku_code_params(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "sku_code_id": _required_int(row, "sku_code_id"),
        "item_id": _required_int(row, "item_id"),
        "sku_code": _required_str(row, "sku_code"),
        "code_type": _required_str(row, "code_type"),
        "is_primary": _required_bool(row, "is_primary"),
        "is_active": _required_bool(row, "is_active"),
        "effective_from": _optional_datetime(row, "effective_from"),
        "effective_to": _optional_datetime(row, "effective_to"),
        "pms_updated_at": _required_datetime(row, "pms_updated_at"),
        "source_hash": _source_hash(row),
        "sync_version": SYNC_VERSION,
    }


def _barcode_params(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "barcode_id": _required_int(row, "barcode_id"),
        "item_id": _required_int(row, "item_id"),
        "item_uom_id": _required_int(row, "item_uom_id"),
        "barcode": _required_str(row, "barcode"),
        "symbology": _required_str(row, "symbology"),
        "active": _required_bool(row, "active"),
        "is_primary": _required_bool(row, "is_primary"),
        "pms_updated_at": _required_datetime(row, "pms_updated_at"),
        "source_hash": _source_hash(row),
        "sync_version": SYNC_VERSION,
    }


UPSERT_SQL: dict[ProjectionResource, str] = {
    "items": """
        INSERT INTO wms_pms_item_projection (
            item_id,
            sku,
            name,
            spec,
            enabled,
            supplier_id,
            brand,
            category,
            expiry_policy,
            shelf_life_value,
            shelf_life_unit,
            lot_source_policy,
            derivation_allowed,
            uom_governance_enabled,
            pms_updated_at,
            source_hash,
            sync_version,
            synced_at
        )
        VALUES (
            :item_id,
            :sku,
            :name,
            :spec,
            :enabled,
            :supplier_id,
            :brand,
            :category,
            :expiry_policy,
            :shelf_life_value,
            :shelf_life_unit,
            :lot_source_policy,
            :derivation_allowed,
            :uom_governance_enabled,
            :pms_updated_at,
            :source_hash,
            :sync_version,
            now()
        )
        ON CONFLICT (item_id) DO UPDATE SET
            sku = EXCLUDED.sku,
            name = EXCLUDED.name,
            spec = EXCLUDED.spec,
            enabled = EXCLUDED.enabled,
            supplier_id = EXCLUDED.supplier_id,
            brand = EXCLUDED.brand,
            category = EXCLUDED.category,
            expiry_policy = EXCLUDED.expiry_policy,
            shelf_life_value = EXCLUDED.shelf_life_value,
            shelf_life_unit = EXCLUDED.shelf_life_unit,
            lot_source_policy = EXCLUDED.lot_source_policy,
            derivation_allowed = EXCLUDED.derivation_allowed,
            uom_governance_enabled = EXCLUDED.uom_governance_enabled,
            pms_updated_at = EXCLUDED.pms_updated_at,
            source_hash = EXCLUDED.source_hash,
            sync_version = EXCLUDED.sync_version,
            synced_at = now()
    """,
    "suppliers": """
        INSERT INTO wms_pms_supplier_projection (
            supplier_id,
            supplier_code,
            supplier_name,
            active,
            website,
            pms_updated_at,
            source_hash,
            sync_version,
            synced_at
        )
        VALUES (
            :supplier_id,
            :supplier_code,
            :supplier_name,
            :active,
            :website,
            :pms_updated_at,
            :source_hash,
            :sync_version,
            now()
        )
        ON CONFLICT (supplier_id) DO UPDATE SET
            supplier_code = EXCLUDED.supplier_code,
            supplier_name = EXCLUDED.supplier_name,
            active = EXCLUDED.active,
            website = EXCLUDED.website,
            pms_updated_at = EXCLUDED.pms_updated_at,
            source_hash = EXCLUDED.source_hash,
            sync_version = EXCLUDED.sync_version,
            synced_at = now()
    """,
    "uoms": """
        INSERT INTO wms_pms_uom_projection (
            item_uom_id,
            item_id,
            uom,
            display_name,
            uom_name,
            ratio_to_base,
            net_weight_kg,
            is_base,
            is_purchase_default,
            is_inbound_default,
            is_outbound_default,
            pms_updated_at,
            source_hash,
            sync_version,
            synced_at
        )
        VALUES (
            :item_uom_id,
            :item_id,
            :uom,
            :display_name,
            :uom_name,
            :ratio_to_base,
            :net_weight_kg,
            :is_base,
            :is_purchase_default,
            :is_inbound_default,
            :is_outbound_default,
            :pms_updated_at,
            :source_hash,
            :sync_version,
            now()
        )
        ON CONFLICT (item_uom_id) DO UPDATE SET
            item_id = EXCLUDED.item_id,
            uom = EXCLUDED.uom,
            display_name = EXCLUDED.display_name,
            uom_name = EXCLUDED.uom_name,
            ratio_to_base = EXCLUDED.ratio_to_base,
            net_weight_kg = EXCLUDED.net_weight_kg,
            is_base = EXCLUDED.is_base,
            is_purchase_default = EXCLUDED.is_purchase_default,
            is_inbound_default = EXCLUDED.is_inbound_default,
            is_outbound_default = EXCLUDED.is_outbound_default,
            pms_updated_at = EXCLUDED.pms_updated_at,
            source_hash = EXCLUDED.source_hash,
            sync_version = EXCLUDED.sync_version,
            synced_at = now()
    """,
    "sku-codes": """
        INSERT INTO wms_pms_sku_code_projection (
            sku_code_id,
            item_id,
            sku_code,
            code_type,
            is_primary,
            is_active,
            effective_from,
            effective_to,
            pms_updated_at,
            source_hash,
            sync_version,
            synced_at
        )
        VALUES (
            :sku_code_id,
            :item_id,
            :sku_code,
            :code_type,
            :is_primary,
            :is_active,
            :effective_from,
            :effective_to,
            :pms_updated_at,
            :source_hash,
            :sync_version,
            now()
        )
        ON CONFLICT (sku_code_id) DO UPDATE SET
            item_id = EXCLUDED.item_id,
            sku_code = EXCLUDED.sku_code,
            code_type = EXCLUDED.code_type,
            is_primary = EXCLUDED.is_primary,
            is_active = EXCLUDED.is_active,
            effective_from = EXCLUDED.effective_from,
            effective_to = EXCLUDED.effective_to,
            pms_updated_at = EXCLUDED.pms_updated_at,
            source_hash = EXCLUDED.source_hash,
            sync_version = EXCLUDED.sync_version,
            synced_at = now()
    """,
    "barcodes": """
        INSERT INTO wms_pms_barcode_projection (
            barcode_id,
            item_id,
            item_uom_id,
            barcode,
            symbology,
            active,
            is_primary,
            pms_updated_at,
            source_hash,
            sync_version,
            synced_at
        )
        VALUES (
            :barcode_id,
            :item_id,
            :item_uom_id,
            :barcode,
            :symbology,
            :active,
            :is_primary,
            :pms_updated_at,
            :source_hash,
            :sync_version,
            now()
        )
        ON CONFLICT (barcode_id) DO UPDATE SET
            item_id = EXCLUDED.item_id,
            item_uom_id = EXCLUDED.item_uom_id,
            barcode = EXCLUDED.barcode,
            symbology = EXCLUDED.symbology,
            active = EXCLUDED.active,
            is_primary = EXCLUDED.is_primary,
            pms_updated_at = EXCLUDED.pms_updated_at,
            source_hash = EXCLUDED.source_hash,
            sync_version = EXCLUDED.sync_version,
            synced_at = now()
    """,
}


def _params_for_resource(
    resource: ProjectionResource,
    row: Mapping[str, Any],
) -> dict[str, Any]:
    if resource == "items":
        return _item_params(row)
    if resource == "suppliers":
        return _supplier_params(row)
    if resource == "uoms":
        return _uom_params(row)
    if resource == "sku-codes":
        return _sku_code_params(row)
    if resource == "barcodes":
        return _barcode_params(row)
    raise PmsProjectionSyncError(f"unsupported projection resource: {resource}")


async def _fetch_page(
    client: httpx.AsyncClient,
    *,
    resource: ProjectionResource,
    limit: int,
    offset: int,
) -> Mapping[str, Any]:
    response = await client.get(
        RESOURCE_PATHS[resource],
        params={"limit": int(limit), "offset": int(offset)},
    )
    response.raise_for_status()
    return _as_mapping(response.json(), context=f"PMS projection feed {resource} response")


async def _upsert_rows(
    session: AsyncSession,
    *,
    resource: ProjectionResource,
    rows: Sequence[Mapping[str, Any]],
) -> int:
    if not rows:
        return 0

    params = [_params_for_resource(resource, row) for row in rows]
    await session.execute(text(UPSERT_SQL[resource]), params)
    return len(params)


async def _sync_resource(
    session: AsyncSession,
    client: httpx.AsyncClient,
    *,
    resource: ProjectionResource,
    limit: int,
) -> PmsProjectionResourceSyncResult:
    safe_limit = _safe_limit(limit)
    offset = 0
    pages = 0
    fetched = 0
    upserted = 0
    has_more = False
    last_offset = 0

    while True:
        payload = await _fetch_page(
            client,
            resource=resource,
            limit=safe_limit,
            offset=offset,
        )
        rows_value = payload.get("rows")
        if not isinstance(rows_value, list):
            raise PmsProjectionSyncError(f"PMS projection feed {resource} rows must be an array")

        rows = [_as_mapping(row, context=f"PMS projection feed {resource} row") for row in rows_value]
        pages += 1
        fetched += len(rows)
        upserted += await _upsert_rows(session, resource=resource, rows=rows)

        has_more = bool(payload.get("has_more"))
        last_offset = offset
        if not has_more:
            break

        next_offset_raw = payload.get("next_offset")
        if next_offset_raw is None:
            raise PmsProjectionSyncError(
                f"PMS projection feed {resource} has_more=true but next_offset is null"
            )

        next_offset = int(next_offset_raw)
        if next_offset <= offset:
            raise PmsProjectionSyncError(
                f"PMS projection feed {resource} next_offset must advance"
            )

        offset = next_offset

    return PmsProjectionResourceSyncResult(
        resource=resource,
        fetched=fetched,
        upserted=upserted,
        pages=pages,
        last_offset=last_offset,
        has_more=has_more,
    )


async def sync_pms_read_projection_once(
    session: AsyncSession,
    *,
    pms_api_base_url: str | None = None,
    limit: int = DEFAULT_LIMIT,
    resources: Sequence[ProjectionResource] | None = None,
    timeout_seconds: float = 30.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> PmsProjectionSyncResult:
    selected = tuple(resources or RESOURCE_ORDER)
    unknown = [resource for resource in selected if resource not in RESOURCE_ORDER]
    if unknown:
        raise PmsProjectionSyncError(f"unsupported projection resources: {unknown}")

    async with httpx.AsyncClient(
        base_url=_base_url(pms_api_base_url),
        headers=pms_service_auth_headers(),
        timeout=httpx.Timeout(timeout_seconds),
        transport=transport,
    ) as client:
        results: dict[ProjectionResource, PmsProjectionResourceSyncResult] = {}
        for resource in RESOURCE_ORDER:
            if resource not in selected:
                continue
            results[resource] = await _sync_resource(
                session,
                client,
                resource=resource,
                limit=limit,
            )

    return PmsProjectionSyncResult(resources=results)


__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "PmsProjectionResourceSyncResult",
    "PmsProjectionSyncError",
    "PmsProjectionSyncResult",
    "ProjectionResource",
    "RESOURCE_ORDER",
    "sync_pms_read_projection_once",
]
