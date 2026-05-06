# app/shipping_assist/records/sync/service.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Awaitable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .client import fetch_logistics_shipping_record_facts


SOURCE_NAME = "logistics.shipping_records"


class LogisticsShippingRecordSyncError(RuntimeError):
    pass


FetchFacts = Callable[..., Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class LogisticsShippingRecordSyncResult:
    fetched: int
    upserted: int
    last_cursor: int
    has_more: bool


def _clean(value: object | None) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _required_str(row: dict[str, Any], key: str) -> str:
    value = _clean(row.get(key))
    if value is None:
        raise LogisticsShippingRecordSyncError(f"logistics fact missing required field: {key}")
    return value


def _optional_decimal(row: dict[str, Any], key: str) -> Decimal | None:
    value = row.get(key)
    if value is None:
        return None
    return Decimal(str(value))


def _optional_datetime(row: dict[str, Any], key: str) -> datetime | None:
    value = row.get(key)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


async def _load_cursor(session: AsyncSession, *, source: str) -> int:
    row = (
        await session.execute(
            text(
                """
                SELECT last_cursor
                FROM logistics_shipping_record_sync_cursors
                WHERE source = :source
                LIMIT 1
                """
            ),
            {"source": source},
        )
    ).mappings().first()
    return int(row["last_cursor"]) if row is not None else 0


async def _save_cursor(session: AsyncSession, *, source: str, last_cursor: int) -> None:
    await session.execute(
        text(
            """
            INSERT INTO logistics_shipping_record_sync_cursors (
                source,
                last_cursor,
                updated_at
            )
            VALUES (
                :source,
                :last_cursor,
                now()
            )
            ON CONFLICT (source) DO UPDATE SET
                last_cursor = EXCLUDED.last_cursor,
                updated_at = now()
            """
        ),
        {"source": source, "last_cursor": int(last_cursor)},
    )


async def _resolve_warehouse_id(session: AsyncSession, *, warehouse_code: str) -> int:
    row = (
        await session.execute(
            text(
                """
                SELECT id
                FROM warehouses
                WHERE code = :warehouse_code
                  AND active IS TRUE
                LIMIT 1
                """
            ),
            {"warehouse_code": warehouse_code},
        )
    ).mappings().first()
    if row is None:
        raise LogisticsShippingRecordSyncError(
            f"WMS warehouse mapping not found for warehouse_code={warehouse_code}"
        )
    return int(row["id"])


async def _resolve_shipping_provider_id(
    session: AsyncSession,
    *,
    shipping_provider_code: str,
) -> int:
    row = (
        await session.execute(
            text(
                """
                SELECT id
                FROM shipping_providers
                WHERE shipping_provider_code = :shipping_provider_code
                  AND active IS TRUE
                LIMIT 1
                """
            ),
            {"shipping_provider_code": shipping_provider_code.strip().upper()},
        )
    ).mappings().first()
    if row is None:
        raise LogisticsShippingRecordSyncError(
            "WMS shipping provider mapping not found for "
            f"shipping_provider_code={shipping_provider_code}"
        )
    return int(row["id"])


async def _upsert_shipping_record(session: AsyncSession, *, fact: dict[str, Any]) -> None:
    warehouse_code = _required_str(fact, "warehouse_code")
    shipping_provider_code = _required_str(fact, "shipping_provider_code")

    warehouse_id = await _resolve_warehouse_id(session, warehouse_code=warehouse_code)
    shipping_provider_id = await _resolve_shipping_provider_id(
        session,
        shipping_provider_code=shipping_provider_code,
    )

    created_at = _optional_datetime(fact, "created_at")

    await session.execute(
        text(
            """
            INSERT INTO shipping_records (
                order_ref,
                platform,
                store_code,
                package_no,
                warehouse_id,
                shipping_provider_id,
                shipping_provider_code,
                shipping_provider_name,
                tracking_no,
                gross_weight_kg,
                freight_estimated,
                surcharge_estimated,
                cost_estimated,
                length_cm,
                width_cm,
                height_cm,
                sender,
                dest_province,
                dest_city,
                created_at
            )
            VALUES (
                :order_ref,
                :platform,
                :store_code,
                :package_no,
                :warehouse_id,
                :shipping_provider_id,
                :shipping_provider_code,
                :shipping_provider_name,
                :tracking_no,
                :gross_weight_kg,
                :freight_estimated,
                :surcharge_estimated,
                :cost_estimated,
                :length_cm,
                :width_cm,
                :height_cm,
                :sender,
                :dest_province,
                :dest_city,
                COALESCE(:created_at, now())
            )
            ON CONFLICT (platform, store_code, order_ref, package_no) DO UPDATE SET
                warehouse_id = EXCLUDED.warehouse_id,
                shipping_provider_id = EXCLUDED.shipping_provider_id,
                shipping_provider_code = EXCLUDED.shipping_provider_code,
                shipping_provider_name = EXCLUDED.shipping_provider_name,
                tracking_no = EXCLUDED.tracking_no,
                gross_weight_kg = EXCLUDED.gross_weight_kg,
                freight_estimated = EXCLUDED.freight_estimated,
                surcharge_estimated = EXCLUDED.surcharge_estimated,
                cost_estimated = EXCLUDED.cost_estimated,
                length_cm = EXCLUDED.length_cm,
                width_cm = EXCLUDED.width_cm,
                height_cm = EXCLUDED.height_cm,
                sender = EXCLUDED.sender,
                dest_province = EXCLUDED.dest_province,
                dest_city = EXCLUDED.dest_city,
                created_at = EXCLUDED.created_at
            """
        ),
        {
            "order_ref": _required_str(fact, "order_ref"),
            "platform": _required_str(fact, "platform").upper(),
            "store_code": _required_str(fact, "store_code"),
            "package_no": int(fact["package_no"]),
            "warehouse_id": warehouse_id,
            "shipping_provider_id": shipping_provider_id,
            "shipping_provider_code": shipping_provider_code.upper(),
            "shipping_provider_name": _clean(fact.get("shipping_provider_name")),
            "tracking_no": _clean(fact.get("tracking_no")),
            "gross_weight_kg": _optional_decimal(fact, "gross_weight_kg"),
            "freight_estimated": _optional_decimal(fact, "freight_estimated"),
            "surcharge_estimated": _optional_decimal(fact, "surcharge_estimated"),
            "cost_estimated": _optional_decimal(fact, "cost_estimated"),
            "length_cm": _optional_decimal(fact, "length_cm"),
            "width_cm": _optional_decimal(fact, "width_cm"),
            "height_cm": _optional_decimal(fact, "height_cm"),
            "sender": _clean(fact.get("sender")),
            "dest_province": _clean(fact.get("dest_province")),
            "dest_city": _clean(fact.get("dest_city")),
            "created_at": created_at,
        },
    )


async def sync_logistics_shipping_record_facts_once(
    session: AsyncSession,
    *,
    after_id: int | None = None,
    limit: int = 500,
    platform: str | None = None,
    store_code: str | None = None,
    fetch_facts: FetchFacts = fetch_logistics_shipping_record_facts,
) -> LogisticsShippingRecordSyncResult:
    cursor = int(after_id) if after_id is not None else await _load_cursor(session, source=SOURCE_NAME)

    payload = await fetch_facts(
        after_id=cursor,
        limit=int(limit),
        platform=platform,
        store_code=store_code,
    )

    rows = payload.get("rows") or []
    if not isinstance(rows, list):
        raise LogisticsShippingRecordSyncError("logistics facts rows must be an array")

    for row in rows:
        if not isinstance(row, dict):
            raise LogisticsShippingRecordSyncError("logistics facts row must be an object")
        await _upsert_shipping_record(session, fact=row)

    next_cursor_raw = payload.get("next_cursor")
    next_cursor = int(next_cursor_raw) if next_cursor_raw is not None else cursor
    if rows:
        await _save_cursor(session, source=SOURCE_NAME, last_cursor=next_cursor)

    return LogisticsShippingRecordSyncResult(
        fetched=len(rows),
        upserted=len(rows),
        last_cursor=next_cursor,
        has_more=bool(payload.get("has_more")),
    )
