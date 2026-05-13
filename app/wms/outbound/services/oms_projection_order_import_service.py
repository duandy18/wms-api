# app/wms/outbound/services/oms_projection_order_import_service.py
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.wms.outbound.contracts.order_import import (
    OmsProjectionOrderImportOut,
    OmsProjectionOrderImportRowOut,
)


def _dedupe_ready_order_ids(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        ready_order_id = str(value or "").strip()
        if not ready_order_id or ready_order_id in seen:
            continue
        seen.add(ready_order_id)
        out.append(ready_order_id)
    return out


def _build_in_filter(name: str, values: list[str]) -> tuple[str, dict[str, str]]:
    params = {f"{name}_{idx}": value for idx, value in enumerate(values)}
    placeholders = ", ".join(f":{key}" for key in params)
    return placeholders, params


def _platform_to_wms(value: object) -> str:
    raw = str(value or "").strip()
    mapping = {
        "pdd": "PDD",
        "taobao": "TAOBAO",
        "jd": "JD",
    }
    return mapping.get(raw.lower(), raw.upper())


def _clean_text(value: object | None) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


def _trace_id_for_ready_order(ready_order_id: str) -> str:
    return hashlib.sha256(f"oms-projection:{ready_order_id}".encode("utf-8")).hexdigest()


def _required_qty_to_int(value: object) -> int | None:
    try:
        qty = Decimal(str(value))
    except Exception:
        return None

    if qty <= 0:
        return None

    if qty != qty.to_integral_value():
        return None

    return int(qty)


def _result(
    *,
    ready_order_id: str,
    status: str,
    order_id: int | None = None,
    order: Mapping[str, Any] | None = None,
    order_line_count: int = 0,
    component_count: int = 0,
    message: str | None = None,
) -> OmsProjectionOrderImportRowOut:
    return OmsProjectionOrderImportRowOut(
        ready_order_id=ready_order_id,
        status=status,
        order_id=order_id,
        platform=_platform_to_wms(order.get("platform")) if order is not None else None,
        store_code=str(order.get("store_code")) if order is not None else None,
        platform_order_no=str(order.get("platform_order_no")) if order is not None else None,
        order_line_count=int(order_line_count),
        component_count=int(component_count),
        message=message,
    )


async def _load_projection_orders(
    session: AsyncSession,
    *,
    ready_order_ids: list[str],
) -> dict[str, dict[str, Any]]:
    placeholders, params = _build_in_filter("ready_order_id", ready_order_ids)

    rows = (
        await session.execute(
            text(
                f"""
                SELECT
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
                FROM wms_oms_fulfillment_order_projection
                WHERE ready_order_id IN ({placeholders})
                """
            ),
            params,
        )
    ).mappings().all()

    return {str(row["ready_order_id"]): dict(row) for row in rows}


async def _load_projection_components(
    session: AsyncSession,
    *,
    ready_order_ids: list[str],
) -> dict[str, list[dict[str, Any]]]:
    placeholders, params = _build_in_filter("ready_order_id", ready_order_ids)

    rows = (
        await session.execute(
            text(
                f"""
                SELECT
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
                FROM wms_oms_fulfillment_component_projection
                WHERE ready_order_id IN ({placeholders})
                ORDER BY ready_order_id ASC, ready_line_id ASC, sort_order ASC, ready_component_id ASC
                """
            ),
            params,
        )
    ).mappings().all()

    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        data = dict(row)
        out.setdefault(str(data["ready_order_id"]), []).append(data)

    return out


async def _load_existing_imports(
    session: AsyncSession,
    *,
    ready_order_ids: list[str],
) -> dict[str, int]:
    placeholders, params = _build_in_filter("ready_order_id", ready_order_ids)

    rows = (
        await session.execute(
            text(
                f"""
                SELECT ready_order_id, order_id
                FROM wms_oms_fulfillment_order_imports
                WHERE ready_order_id IN ({placeholders})
                """
            ),
            params,
        )
    ).mappings().all()

    return {str(row["ready_order_id"]): int(row["order_id"]) for row in rows}


async def _load_existing_order_conflicts(
    session: AsyncSession,
    *,
    ready_order_ids: list[str],
) -> dict[str, int]:
    placeholders, params = _build_in_filter("ready_order_id", ready_order_ids)

    rows = (
        await session.execute(
            text(
                f"""
                SELECT
                  p.ready_order_id,
                  o.id AS order_id
                FROM wms_oms_fulfillment_order_projection AS p
                JOIN orders AS o
                  ON UPPER(o.platform) = UPPER(p.platform)
                 AND o.store_code = p.store_code
                 AND o.ext_order_no = p.platform_order_no
                WHERE p.ready_order_id IN ({placeholders})
                """
            ),
            params,
        )
    ).mappings().all()

    return {str(row["ready_order_id"]): int(row["order_id"]) for row in rows}


async def _ensure_store_from_projection(
    session: AsyncSession,
    *,
    order: Mapping[str, Any],
) -> int:
    platform = _platform_to_wms(order["platform"])
    store_code = str(order["store_code"])
    store_name = str(order.get("store_name") or store_code)

    row = (
        await session.execute(
            text(
                """
                INSERT INTO stores (
                  platform,
                  store_code,
                  store_name,
                  active
                )
                VALUES (
                  :platform,
                  :store_code,
                  :store_name,
                  TRUE
                )
                ON CONFLICT (platform, store_code) DO UPDATE
                   SET store_name = EXCLUDED.store_name,
                       active = TRUE,
                       updated_at = now()
                RETURNING id
                """
            ),
            {
                "platform": platform,
                "store_code": store_code,
                "store_name": store_name,
            },
        )
    ).scalar_one()

    return int(row)


async def _insert_execution_order(
    session: AsyncSession,
    *,
    order: Mapping[str, Any],
    store_id: int,
) -> int:
    platform = _platform_to_wms(order["platform"])
    store_code = str(order["store_code"])
    platform_order_no = str(order["platform_order_no"])
    trace_id = _trace_id_for_ready_order(str(order["ready_order_id"]))

    row = (
        await session.execute(
            text(
                """
                INSERT INTO orders (
                  status,
                  created_at,
                  updated_at,
                  total_amount,
                  buyer_name,
                  buyer_phone,
                  order_amount,
                  pay_amount,
                  order_no,
                  platform,
                  store_code,
                  ext_order_no,
                  trace_id,
                  store_id
                )
                VALUES (
                  'CREATED',
                  COALESCE(:created_at, now()),
                  now(),
                  0,
                  :buyer_name,
                  :buyer_phone,
                  0,
                  0,
                  :order_no,
                  :platform,
                  :store_code,
                  :ext_order_no,
                  :trace_id,
                  :store_id
                )
                ON CONFLICT ON CONSTRAINT uq_orders_platform_store_ext DO NOTHING
                RETURNING id
                """
            ),
            {
                "created_at": order.get("ready_at"),
                "buyer_name": _clean_text(order.get("receiver_name")),
                "buyer_phone": _clean_text(order.get("receiver_phone")),
                "order_no": platform_order_no,
                "platform": platform,
                "store_code": store_code,
                "ext_order_no": platform_order_no,
                "trace_id": trace_id,
                "store_id": int(store_id),
            },
        )
    ).scalar_one_or_none()

    if row is not None:
        return int(row)

    existing = (
        await session.execute(
            text(
                """
                SELECT id
                FROM orders
                WHERE UPPER(platform) = UPPER(:platform)
                  AND store_code = :store_code
                  AND ext_order_no = :ext_order_no
                LIMIT 1
                """
            ),
            {
                "platform": platform,
                "store_code": store_code,
                "ext_order_no": platform_order_no,
            },
        )
    ).scalar_one()

    return int(existing)


async def _upsert_execution_order_address(
    session: AsyncSession,
    *,
    order_id: int,
    order: Mapping[str, Any],
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO order_address (
              order_id,
              receiver_name,
              receiver_phone,
              province,
              city,
              district,
              detail,
              zipcode
            )
            VALUES (
              :order_id,
              :receiver_name,
              :receiver_phone,
              :province,
              :city,
              :district,
              :detail,
              :zipcode
            )
            ON CONFLICT (order_id) DO UPDATE
               SET receiver_name = EXCLUDED.receiver_name,
                   receiver_phone = EXCLUDED.receiver_phone,
                   province = EXCLUDED.province,
                   city = EXCLUDED.city,
                   district = EXCLUDED.district,
                   detail = EXCLUDED.detail,
                   zipcode = EXCLUDED.zipcode
            """
        ),
        {
            "order_id": int(order_id),
            "receiver_name": _clean_text(order.get("receiver_name")),
            "receiver_phone": _clean_text(order.get("receiver_phone")),
            "province": _clean_text(order.get("receiver_province")),
            "city": _clean_text(order.get("receiver_city")),
            "district": _clean_text(order.get("receiver_district")),
            "detail": _clean_text(order.get("receiver_address")),
            "zipcode": _clean_text(order.get("receiver_postcode")),
        },
    )


async def _insert_order_fulfillment_placeholder(
    session: AsyncSession,
    *,
    order_id: int,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO order_fulfillment (
              order_id,
              planned_warehouse_id,
              actual_warehouse_id,
              fulfillment_status,
              blocked_reasons,
              execution_stage
            )
            VALUES (
              :order_id,
              NULL,
              NULL,
              'OMS_IMPORTED',
              NULL,
              NULL
            )
            ON CONFLICT (order_id) DO NOTHING
            """
        ),
        {"order_id": int(order_id)},
    )


async def _insert_order_item_from_component(
    session: AsyncSession,
    *,
    order_id: int,
    component: Mapping[str, Any],
    qty: int,
) -> None:
    unit_price = Decimal(str(component.get("alloc_unit_price") or "0"))
    line_amount = Decimal(qty) * unit_price
    extras = {
        "source": "OMS_FULFILLMENT_PROJECTION",
        "ready_order_id": str(component["ready_order_id"]),
        "ready_line_id": str(component["ready_line_id"]),
        "ready_component_id": str(component["ready_component_id"]),
        "resolved_item_sku_code_id": int(component["resolved_item_sku_code_id"]),
        "resolved_item_uom_id": int(component["resolved_item_uom_id"]),
        "uom_snapshot": str(component["uom_snapshot"]),
    }

    await session.execute(
        text(
            """
            INSERT INTO order_items (
              order_id,
              item_id,
              qty,
              unit_price,
              line_amount,
              sku_id,
              title,
              price,
              discount,
              amount,
              extras
            )
            VALUES (
              :order_id,
              :item_id,
              :qty,
              :unit_price,
              :line_amount,
              :sku_id,
              :title,
              :price,
              0,
              :amount,
              CAST(:extras AS jsonb)
            )
            ON CONFLICT ON CONSTRAINT uq_order_items_ord_sku DO UPDATE
               SET qty = COALESCE(order_items.qty, 0) + EXCLUDED.qty,
                   line_amount = COALESCE(order_items.line_amount, 0) + EXCLUDED.line_amount,
                   amount = COALESCE(order_items.amount, 0) + EXCLUDED.amount,
                   extras = order_items.extras || EXCLUDED.extras
            """
        ),
        {
            "order_id": int(order_id),
            "item_id": int(component["resolved_item_id"]),
            "qty": int(qty),
            "unit_price": unit_price,
            "line_amount": line_amount,
            "sku_id": str(component["sku_code_snapshot"]),
            "title": str(component["item_name_snapshot"]),
            "price": unit_price,
            "amount": line_amount,
            "extras": json.dumps(extras, ensure_ascii=False),
        },
    )


async def _insert_order_import_audit(
    session: AsyncSession,
    *,
    order_id: int,
    order: Mapping[str, Any],
    component_count: int,
    imported_by_user_id: int | None,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO wms_oms_fulfillment_order_imports (
              ready_order_id,
              order_id,
              platform,
              store_code,
              platform_order_no,
              source_order_id,
              source_hash,
              import_status,
              order_line_count,
              component_count,
              imported_by_user_id
            )
            VALUES (
              :ready_order_id,
              :order_id,
              :platform,
              :store_code,
              :platform_order_no,
              :source_order_id,
              :source_hash,
              'IMPORTED',
              :order_line_count,
              :component_count,
              :imported_by_user_id
            )
            """
        ),
        {
            "ready_order_id": str(order["ready_order_id"]),
            "order_id": int(order_id),
            "platform": _platform_to_wms(order["platform"]),
            "store_code": str(order["store_code"]),
            "platform_order_no": str(order["platform_order_no"]),
            "source_order_id": int(order["source_order_id"]),
            "source_hash": _clean_text(order.get("source_hash")),
            "order_line_count": int(component_count),
            "component_count": int(component_count),
            "imported_by_user_id": imported_by_user_id,
        },
    )


async def _import_order_lines_and_items(
    session: AsyncSession,
    *,
    order_id: int,
    components: list[Mapping[str, Any]],
) -> None:
    for component in components:
        qty = _required_qty_to_int(component.get("required_qty"))
        if qty is None:
            raise ValueError(
                "component_required_qty_must_be_positive_integer:"
                f" ready_component_id={component.get('ready_component_id')}"
            )

        order_line_id = (
            await session.execute(
                text(
                    """
                    INSERT INTO order_lines (
                      order_id,
                      item_id,
                      req_qty
                    )
                    VALUES (
                      :order_id,
                      :item_id,
                      :req_qty
                    )
                    RETURNING id
                    """
                ),
                {
                    "order_id": int(order_id),
                    "item_id": int(component["resolved_item_id"]),
                    "req_qty": int(qty),
                },
            )
        ).scalar_one()

        await _insert_order_item_from_component(
            session,
            order_id=int(order_id),
            component=component,
            qty=int(qty),
        )

        await session.execute(
            text(
                """
                INSERT INTO wms_oms_fulfillment_component_imports (
                  ready_component_id,
                  ready_order_id,
                  ready_line_id,
                  order_id,
                  order_line_id,
                  resolved_item_id,
                  resolved_item_sku_code_id,
                  resolved_item_uom_id,
                  component_sku_code,
                  sku_code_snapshot,
                  item_name_snapshot,
                  uom_snapshot,
                  required_qty,
                  source_hash
                )
                VALUES (
                  :ready_component_id,
                  :ready_order_id,
                  :ready_line_id,
                  :order_id,
                  :order_line_id,
                  :resolved_item_id,
                  :resolved_item_sku_code_id,
                  :resolved_item_uom_id,
                  :component_sku_code,
                  :sku_code_snapshot,
                  :item_name_snapshot,
                  :uom_snapshot,
                  :required_qty,
                  :source_hash
                )
                """
            ),
            {
                "ready_component_id": str(component["ready_component_id"]),
                "ready_order_id": str(component["ready_order_id"]),
                "ready_line_id": str(component["ready_line_id"]),
                "order_id": int(order_id),
                "order_line_id": int(order_line_id),
                "resolved_item_id": int(component["resolved_item_id"]),
                "resolved_item_sku_code_id": int(component["resolved_item_sku_code_id"]),
                "resolved_item_uom_id": int(component["resolved_item_uom_id"]),
                "component_sku_code": str(component["component_sku_code"]),
                "sku_code_snapshot": str(component["sku_code_snapshot"]),
                "item_name_snapshot": str(component["item_name_snapshot"]),
                "uom_snapshot": str(component["uom_snapshot"]),
                "required_qty": component["required_qty"],
                "source_hash": _clean_text(component.get("source_hash")),
            },
        )


async def import_orders_from_oms_projection(
    session: AsyncSession,
    *,
    ready_order_ids: list[str],
    dry_run: bool,
    imported_by_user_id: int | None,
) -> OmsProjectionOrderImportOut:
    ids = _dedupe_ready_order_ids(ready_order_ids)

    orders = await _load_projection_orders(session, ready_order_ids=ids)
    components_by_order = await _load_projection_components(session, ready_order_ids=ids)
    existing_imports = await _load_existing_imports(session, ready_order_ids=ids)
    existing_order_conflicts = await _load_existing_order_conflicts(session, ready_order_ids=ids)

    results: list[OmsProjectionOrderImportRowOut] = []

    for ready_order_id in ids:
        order = orders.get(ready_order_id)
        if order is None:
            results.append(
                _result(
                    ready_order_id=ready_order_id,
                    status="FAILED",
                    message="projection_order_not_found",
                )
            )
            continue

        if ready_order_id in existing_imports:
            results.append(
                _result(
                    ready_order_id=ready_order_id,
                    status="ALREADY_IMPORTED",
                    order_id=existing_imports[ready_order_id],
                    order=order,
                    message="order_already_imported",
                )
            )
            continue

        if ready_order_id in existing_order_conflicts:
            results.append(
                _result(
                    ready_order_id=ready_order_id,
                    status="FAILED",
                    order_id=existing_order_conflicts[ready_order_id],
                    order=order,
                    message="existing_execution_order_conflict",
                )
            )
            continue

        components = components_by_order.get(ready_order_id, [])
        expected_component_count = int(order.get("component_count") or 0)
        if not components:
            results.append(
                _result(
                    ready_order_id=ready_order_id,
                    status="FAILED",
                    order=order,
                    message="projection_components_not_found",
                )
            )
            continue

        if expected_component_count != len(components):
            results.append(
                _result(
                    ready_order_id=ready_order_id,
                    status="FAILED",
                    order=order,
                    component_count=len(components),
                    message=(
                        "projection_component_count_mismatch:"
                        f" expected={expected_component_count}, actual={len(components)}"
                    ),
                )
            )
            continue

        invalid_component = next(
            (
                component
                for component in components
                if _required_qty_to_int(component.get("required_qty")) is None
            ),
            None,
        )
        if invalid_component is not None:
            results.append(
                _result(
                    ready_order_id=ready_order_id,
                    status="FAILED",
                    order=order,
                    component_count=len(components),
                    message=(
                        "component_required_qty_must_be_positive_integer:"
                        f" ready_component_id={invalid_component.get('ready_component_id')}"
                    ),
                )
            )
            continue

        if dry_run:
            results.append(
                _result(
                    ready_order_id=ready_order_id,
                    status="DRY_RUN",
                    order=order,
                    order_line_count=len(components),
                    component_count=len(components),
                    message="would_import_execution_order",
                )
            )
            continue

        store_id = await _ensure_store_from_projection(session, order=order)
        order_id = await _insert_execution_order(session, order=order, store_id=store_id)

        await _upsert_execution_order_address(session, order_id=order_id, order=order)
        await _insert_order_fulfillment_placeholder(session, order_id=order_id)
        await _insert_order_import_audit(
            session,
            order_id=order_id,
            order=order,
            component_count=len(components),
            imported_by_user_id=imported_by_user_id,
        )
        await _import_order_lines_and_items(
            session,
            order_id=order_id,
            components=components,
        )

        results.append(
            _result(
                ready_order_id=ready_order_id,
                status="IMPORTED",
                order_id=order_id,
                order=order,
                order_line_count=len(components),
                component_count=len(components),
                message="imported_execution_order",
            )
        )

    imported = sum(1 for row in results if row.status == "IMPORTED")
    already_imported = sum(1 for row in results if row.status == "ALREADY_IMPORTED")
    failed = sum(1 for row in results if row.status == "FAILED")

    return OmsProjectionOrderImportOut(
        dry_run=bool(dry_run),
        requested=len(ids),
        imported=imported,
        already_imported=already_imported,
        failed=failed,
        results=results,
    )


async def list_oms_projection_import_candidates(
    session: AsyncSession,
    *,
    q: str | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    query_text = str(q or "").strip()

    where_sql = ""
    params: dict[str, Any] = {
        "limit": int(limit),
        "offset": int(offset),
    }

    if query_text:
        where_sql = """
        WHERE (
          p.ready_order_id ILIKE :q
          OR p.platform ILIKE :q
          OR p.store_code ILIKE :q
          OR p.store_name ILIKE :q
          OR p.platform_order_no ILIKE :q
          OR p.receiver_name ILIKE :q
          OR p.receiver_phone ILIKE :q
        )
        """
        params["q"] = f"%{query_text}%"

    total = int(
        (
            await session.execute(
                text(
                    f"""
                    SELECT count(*)::bigint
                    FROM wms_oms_fulfillment_order_projection AS p
                    {where_sql}
                    """
                ),
                params,
            )
        ).scalar_one()
    )

    rows = (
        await session.execute(
            text(
                f"""
                SELECT
                  p.ready_order_id,
                  p.platform,
                  p.store_code,
                  p.store_name,
                  p.platform_order_no,
                  p.platform_status,
                  p.receiver_name,
                  p.receiver_phone,
                  p.ready_status,
                  p.ready_at,
                  p.synced_at,
                  p.line_count,
                  p.component_count,
                  p.total_required_qty,
                  i.order_id AS imported_order_id,
                  i.import_status,
                  i.imported_at
                FROM wms_oms_fulfillment_order_projection AS p
                LEFT JOIN wms_oms_fulfillment_order_imports AS i
                  ON i.ready_order_id = p.ready_order_id
                {where_sql}
                ORDER BY
                  CASE WHEN i.ready_order_id IS NULL THEN 0 ELSE 1 END ASC,
                  p.source_updated_at DESC,
                  p.ready_order_id ASC
                LIMIT :limit
                OFFSET :offset
                """
            ),
            params,
        )
    ).mappings().all()

    items: list[dict[str, Any]] = []
    for row in rows:
        imported_order_id = row.get("imported_order_id")
        imported = imported_order_id is not None
        items.append(
            {
                "ready_order_id": str(row["ready_order_id"]),
                "platform": _platform_to_wms(row["platform"]),
                "store_code": str(row["store_code"]),
                "store_name": row.get("store_name"),
                "platform_order_no": str(row["platform_order_no"]),
                "platform_status": row.get("platform_status"),
                "receiver_name": row.get("receiver_name"),
                "receiver_phone": row.get("receiver_phone"),
                "ready_status": str(row["ready_status"]),
                "ready_at": str(row["ready_at"]) if row.get("ready_at") is not None else None,
                "synced_at": str(row["synced_at"]) if row.get("synced_at") is not None else None,
                "line_count": int(row.get("line_count") or 0),
                "component_count": int(row.get("component_count") or 0),
                "total_required_qty": str(row["total_required_qty"]) if row.get("total_required_qty") is not None else None,
                "import_status": str(row.get("import_status") or "NOT_IMPORTED"),
                "imported_order_id": int(imported_order_id) if imported_order_id is not None else None,
                "imported_at": str(row["imported_at"]) if row.get("imported_at") is not None else None,
                "can_import": not imported,
            }
        )

    return {
        "items": items,
        "total": total,
        "limit": int(limit),
        "offset": int(offset),
    }
