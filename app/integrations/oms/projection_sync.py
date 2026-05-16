# app/integrations/oms/projection_sync.py
"""
Sync WMS-owned OMS fulfillment projection tables from oms-api read-v1 HTTP output.

Boundary:
- Source must be oms-api /oms/read/v1/fulfillment-ready-orders.
- This module must not read OMS owner tables directly.
- This module only writes WMS-owned OMS fulfillment projection tables.
- Projection is a current-state read index, not an outbound execution fact.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.oms.projection_contracts import (
    OmsFulfillmentReadyComponentIn,
    OmsFulfillmentReadyLineIn,
    OmsFulfillmentReadyListDataIn,
    OmsFulfillmentReadyListEnvelopeIn,
    OmsFulfillmentReadyOrderIn,
    OmsFulfillmentReadyPlatform,
)
from app.integrations.oms.service_auth import oms_service_auth_headers

SYNC_VERSION = "oms-read-v1-fulfillment-ready-orders"
RESOURCE_PATH = "/oms/read/v1/fulfillment-ready-orders"
DEFAULT_LIMIT = 200
MAX_LIMIT = 500


class OmsFulfillmentProjectionSyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class OmsFulfillmentProjectionSyncResult:
    fetched: int
    upserted_orders: int
    upserted_lines: int
    upserted_components: int
    pages: int
    last_offset: int
    total: int


def _base_url(value: str | None = None) -> str:
    raw = (value or os.getenv("OMS_API_BASE_URL") or "").strip()
    if not raw:
        raise RuntimeError("OMS_API_BASE_URL is required for OMS fulfillment projection sync")
    return raw.rstrip("/")


def _auth_headers(value: str | None = None) -> dict[str, str]:
    token = (value or os.getenv("OMS_API_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("OMS_API_TOKEN is required for OMS fulfillment projection sync")
    return oms_service_auth_headers({"Authorization": f"Bearer {token}"})


def _safe_limit(value: int) -> int:
    return max(1, min(int(value), MAX_LIMIT))


def _source_hash(payload: Mapping[str, Any]) -> str:
    text_value = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(text_value.encode("utf-8")).hexdigest()


def _model_hash(model: BaseModel) -> str:
    return _source_hash(model.model_dump(mode="json"))


def _none_or_str(value: object | None) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


def _order_total_required_qty(order: OmsFulfillmentReadyOrderIn) -> Decimal:
    total = Decimal("0")
    for line in order.lines:
        for component in line.components:
            total += component.required_qty
    return total


ORDER_UPSERT_SQL = """
    INSERT INTO wms_oms_fulfillment_order_projection (
        ready_order_id,
        source_order_id,
        platform,
        store_code,
        store_name,
        platform_order_no,
        platform_status,
        receiver_name,
        receiver_phone,
        receiver_province,
        receiver_city,
        receiver_district,
        receiver_address,
        receiver_postcode,
        buyer_remark,
        seller_remark,
        ready_status,
        ready_at,
        source_updated_at,
        line_count,
        component_count,
        total_required_qty,
        source_hash,
        sync_version,
        synced_at
    )
    VALUES (
        :ready_order_id,
        :source_order_id,
        :platform,
        :store_code,
        :store_name,
        :platform_order_no,
        :platform_status,
        :receiver_name,
        :receiver_phone,
        :receiver_province,
        :receiver_city,
        :receiver_district,
        :receiver_address,
        :receiver_postcode,
        :buyer_remark,
        :seller_remark,
        :ready_status,
        :ready_at,
        :source_updated_at,
        :line_count,
        :component_count,
        :total_required_qty,
        :source_hash,
        :sync_version,
        now()
    )
    ON CONFLICT (ready_order_id) DO UPDATE SET
        source_order_id = EXCLUDED.source_order_id,
        platform = EXCLUDED.platform,
        store_code = EXCLUDED.store_code,
        store_name = EXCLUDED.store_name,
        platform_order_no = EXCLUDED.platform_order_no,
        platform_status = EXCLUDED.platform_status,
        receiver_name = EXCLUDED.receiver_name,
        receiver_phone = EXCLUDED.receiver_phone,
        receiver_province = EXCLUDED.receiver_province,
        receiver_city = EXCLUDED.receiver_city,
        receiver_district = EXCLUDED.receiver_district,
        receiver_address = EXCLUDED.receiver_address,
        receiver_postcode = EXCLUDED.receiver_postcode,
        buyer_remark = EXCLUDED.buyer_remark,
        seller_remark = EXCLUDED.seller_remark,
        ready_status = EXCLUDED.ready_status,
        ready_at = EXCLUDED.ready_at,
        source_updated_at = EXCLUDED.source_updated_at,
        line_count = EXCLUDED.line_count,
        component_count = EXCLUDED.component_count,
        total_required_qty = EXCLUDED.total_required_qty,
        source_hash = EXCLUDED.source_hash,
        sync_version = EXCLUDED.sync_version,
        synced_at = now()
"""

LINE_INSERT_SQL = """
    INSERT INTO wms_oms_fulfillment_line_projection (
        ready_line_id,
        ready_order_id,
        source_line_id,
        platform,
        store_code,
        identity_kind,
        identity_value,
        merchant_sku,
        platform_item_id,
        platform_sku_id,
        platform_goods_name,
        platform_sku_name,
        ordered_qty,
        fsku_id,
        fsku_code,
        fsku_name,
        fsku_status_snapshot,
        source_hash,
        sync_version,
        synced_at
    )
    VALUES (
        :ready_line_id,
        :ready_order_id,
        :source_line_id,
        :platform,
        :store_code,
        :identity_kind,
        :identity_value,
        :merchant_sku,
        :platform_item_id,
        :platform_sku_id,
        :platform_goods_name,
        :platform_sku_name,
        :ordered_qty,
        :fsku_id,
        :fsku_code,
        :fsku_name,
        :fsku_status_snapshot,
        :source_hash,
        :sync_version,
        now()
    )
"""

COMPONENT_INSERT_SQL = """
    INSERT INTO wms_oms_fulfillment_component_projection (
        ready_component_id,
        ready_line_id,
        ready_order_id,
        resolved_item_id,
        resolved_item_sku_code_id,
        resolved_item_uom_id,
        component_sku_code,
        sku_code_snapshot,
        item_name_snapshot,
        uom_snapshot,
        qty_per_fsku,
        required_qty,
        alloc_unit_price,
        sort_order,
        source_hash,
        sync_version,
        synced_at
    )
    VALUES (
        :ready_component_id,
        :ready_line_id,
        :ready_order_id,
        :resolved_item_id,
        :resolved_item_sku_code_id,
        :resolved_item_uom_id,
        :component_sku_code,
        :sku_code_snapshot,
        :item_name_snapshot,
        :uom_snapshot,
        :qty_per_fsku,
        :required_qty,
        :alloc_unit_price,
        :sort_order,
        :source_hash,
        :sync_version,
        now()
    )
"""


def _order_params(order: OmsFulfillmentReadyOrderIn) -> dict[str, Any]:
    return {
        "ready_order_id": order.ready_order_id,
        "source_order_id": int(order.source_order_id),
        "platform": str(order.platform),
        "store_code": order.store_code,
        "store_name": order.store_name,
        "platform_order_no": order.platform_order_no,
        "platform_status": _none_or_str(order.platform_status),
        "receiver_name": order.receiver_name,
        "receiver_phone": order.receiver_phone,
        "receiver_province": order.receiver_province,
        "receiver_city": order.receiver_city,
        "receiver_district": _none_or_str(order.receiver_district),
        "receiver_address": order.receiver_address,
        "receiver_postcode": _none_or_str(order.receiver_postcode),
        "buyer_remark": _none_or_str(order.buyer_remark),
        "seller_remark": _none_or_str(order.seller_remark),
        "ready_status": order.ready_status,
        "ready_at": order.ready_at,
        "source_updated_at": order.source_updated_at,
        "line_count": len(order.lines),
        "component_count": sum(len(line.components) for line in order.lines),
        "total_required_qty": _order_total_required_qty(order),
        "source_hash": _model_hash(order),
        "sync_version": SYNC_VERSION,
    }


def _line_params(
    order: OmsFulfillmentReadyOrderIn,
    line: OmsFulfillmentReadyLineIn,
) -> dict[str, Any]:
    return {
        "ready_line_id": line.ready_line_id,
        "ready_order_id": order.ready_order_id,
        "source_line_id": int(line.source_line_id),
        "platform": str(order.platform),
        "store_code": order.store_code,
        "identity_kind": str(line.identity_kind),
        "identity_value": line.identity_value,
        "merchant_sku": _none_or_str(line.merchant_sku),
        "platform_item_id": _none_or_str(line.platform_item_id),
        "platform_sku_id": _none_or_str(line.platform_sku_id),
        "platform_goods_name": _none_or_str(line.platform_goods_name),
        "platform_sku_name": _none_or_str(line.platform_sku_name),
        "ordered_qty": line.ordered_qty,
        "fsku_id": int(line.fsku_id),
        "fsku_code": line.fsku_code,
        "fsku_name": line.fsku_name,
        "fsku_status_snapshot": line.fsku_status_snapshot,
        "source_hash": _model_hash(line),
        "sync_version": SYNC_VERSION,
    }


def _component_params(
    order: OmsFulfillmentReadyOrderIn,
    component: OmsFulfillmentReadyComponentIn,
) -> dict[str, Any]:
    return {
        "ready_component_id": component.ready_component_id,
        "ready_line_id": component.ready_line_id,
        "ready_order_id": order.ready_order_id,
        "resolved_item_id": int(component.resolved_item_id),
        "resolved_item_sku_code_id": int(component.resolved_item_sku_code_id),
        "resolved_item_uom_id": int(component.resolved_item_uom_id),
        "component_sku_code": component.component_sku_code,
        "sku_code_snapshot": component.sku_code_snapshot,
        "item_name_snapshot": component.item_name_snapshot,
        "uom_snapshot": component.uom_snapshot,
        "qty_per_fsku": component.qty_per_fsku,
        "required_qty": component.required_qty,
        "alloc_unit_price": component.alloc_unit_price,
        "sort_order": int(component.sort_order),
        "source_hash": _model_hash(component),
        "sync_version": SYNC_VERSION,
    }


async def _fetch_page(
    client: httpx.AsyncClient,
    *,
    platform: OmsFulfillmentReadyPlatform | None,
    store_code: str | None,
    limit: int,
    offset: int,
) -> OmsFulfillmentReadyListDataIn:
    params: dict[str, object] = {
        "limit": int(limit),
        "offset": int(offset),
    }
    if platform is not None:
        params["platform"] = platform
    if store_code:
        params["store_code"] = store_code.strip()

    response = await client.get(RESOURCE_PATH, params=params)
    if response.status_code in {401, 403}:
        raise OmsFulfillmentProjectionSyncError(
            f"OMS fulfillment projection sync auth failed: status={response.status_code}"
        )
    response.raise_for_status()

    envelope = OmsFulfillmentReadyListEnvelopeIn.model_validate(response.json())
    return envelope.data


async def _replace_order_children(
    session: AsyncSession,
    *,
    ready_order_id: str,
) -> None:
    await session.execute(
        text(
            """
            DELETE FROM wms_oms_fulfillment_component_projection
            WHERE ready_order_id = :ready_order_id
            """
        ),
        {"ready_order_id": ready_order_id},
    )
    await session.execute(
        text(
            """
            DELETE FROM wms_oms_fulfillment_line_projection
            WHERE ready_order_id = :ready_order_id
            """
        ),
        {"ready_order_id": ready_order_id},
    )


async def _upsert_order_tree(
    session: AsyncSession,
    *,
    order: OmsFulfillmentReadyOrderIn,
) -> tuple[int, int, int]:
    await _replace_order_children(session, ready_order_id=order.ready_order_id)

    await session.execute(text(ORDER_UPSERT_SQL), _order_params(order))

    line_params = [_line_params(order, line) for line in order.lines]
    if line_params:
        await session.execute(text(LINE_INSERT_SQL), line_params)

    component_params = [
        _component_params(order, component)
        for line in order.lines
        for component in line.components
    ]
    if component_params:
        await session.execute(text(COMPONENT_INSERT_SQL), component_params)

    return 1, len(line_params), len(component_params)


async def sync_oms_fulfillment_projection_once(
    session: AsyncSession,
    *,
    oms_api_base_url: str | None = None,
    oms_api_token: str | None = None,
    platform: OmsFulfillmentReadyPlatform | None = None,
    store_code: str | None = None,
    limit: int = DEFAULT_LIMIT,
    timeout_seconds: float = 30.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> OmsFulfillmentProjectionSyncResult:
    safe_limit = _safe_limit(limit)
    offset = 0
    pages = 0
    fetched = 0
    upserted_orders = 0
    upserted_lines = 0
    upserted_components = 0
    total = 0
    last_offset = 0

    async with httpx.AsyncClient(
        base_url=_base_url(oms_api_base_url),
        headers=_auth_headers(oms_api_token),
        timeout=httpx.Timeout(timeout_seconds),
        transport=transport,
    ) as client:
        while True:
            data = await _fetch_page(
                client,
                platform=platform,
                store_code=store_code,
                limit=safe_limit,
                offset=offset,
            )
            pages += 1
            total = int(data.total)
            last_offset = offset

            if not data.items:
                break

            fetched += len(data.items)
            for order in data.items:
                order_count, line_count, component_count = await _upsert_order_tree(
                    session,
                    order=order,
                )
                upserted_orders += order_count
                upserted_lines += line_count
                upserted_components += component_count

            offset += safe_limit
            if offset >= total:
                break

    return OmsFulfillmentProjectionSyncResult(
        fetched=fetched,
        upserted_orders=upserted_orders,
        upserted_lines=upserted_lines,
        upserted_components=upserted_components,
        pages=pages,
        last_offset=last_offset,
        total=total,
    )


__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "OmsFulfillmentProjectionSyncError",
    "OmsFulfillmentProjectionSyncResult",
    "SYNC_VERSION",
    "sync_oms_fulfillment_projection_once",
]
