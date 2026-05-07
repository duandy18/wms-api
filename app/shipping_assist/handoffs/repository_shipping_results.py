
# app/shipping_assist/handoffs/repository_shipping_results.py
#
# 分拆说明：
# - 本文件承载独立 Logistics 物流完成结果回写；
# - 读取交接状态/交接 payload，写入 shipping_records 与 wms_logistics_export_records；
# - shipping_records 触发 finance_shipping_cost_lines 刷新，仍保持现有事实链路。
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _clean(value: object | None) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _clean_required(value: object | None, *, field: str) -> str:
    s = _clean(value)
    if s is None:
        raise ValueError(f"{field}_required")
    return s


def _decimal_or_none(value: Decimal | int | float | str | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


async def _load_shipping_result_context(
    session: AsyncSession,
    *,
    source_ref: str,
) -> dict[str, Any] | None:
    row = (
        await session.execute(
            text(
                """
                SELECT
                  r.source_doc_type,
                  r.source_doc_id,
                  r.source_doc_no,
                  r.source_ref,
                  r.export_status,
                  r.logistics_status,
                  r.logistics_request_id,
                  r.logistics_request_no,

                  p.platform,
                  p.store_code,
                  p.order_ref,
                  p.ext_order_no,
                  p.warehouse_id,
                  p.receiver_province,
                  p.receiver_city
                FROM wms_logistics_export_records r
                JOIN wms_logistics_handoff_payloads p
                  ON p.export_record_id = r.id
                WHERE r.source_ref = :source_ref
                FOR UPDATE OF r
                """
            ),
            {"source_ref": str(source_ref).strip()},
        )
    ).mappings().first()

    return dict(row) if row else None


def _base_shipping_record_values(
    ctx: Mapping[str, Any],
) -> dict[str, object]:
    source_doc_type = str(ctx["source_doc_type"])

    if source_doc_type == "ORDER_OUTBOUND":
        platform = _clean_required(ctx.get("platform"), field="platform").upper()
        store_code = _clean_required(ctx.get("store_code"), field="store_code")
        order_ref = _clean(ctx.get("order_ref"))
        if order_ref is None:
            ext_order_no = _clean_required(ctx.get("ext_order_no"), field="ext_order_no")
            order_ref = f"ORD:{platform}:{store_code}:{ext_order_no}"

        warehouse_id = ctx.get("warehouse_id")
        if warehouse_id is None:
            raise ValueError("warehouse_id_required")

        return {
            "platform": platform,
            "store_code": store_code,
            "order_ref": order_ref,
            "warehouse_id": int(warehouse_id),
            "dest_province": _clean(ctx.get("receiver_province")),
            "dest_city": _clean(ctx.get("receiver_city")),
        }

    if source_doc_type == "MANUAL_OUTBOUND":
        doc_no = _clean_required(ctx.get("source_doc_no"), field="manual_doc_no")
        warehouse_id = ctx.get("warehouse_id")
        if warehouse_id is None:
            raise ValueError("warehouse_id_required")

        return {
            "platform": "MANUAL",
            "store_code": "MANUAL",
            "order_ref": f"MANUAL:{doc_no}",
            "warehouse_id": int(warehouse_id),
            "dest_province": None,
            "dest_city": None,
        }

    raise ValueError("unsupported_source_doc_type")


async def _resolve_shipping_provider(
    session: AsyncSession,
    *,
    shipping_provider_code: str,
) -> dict[str, object]:
    code = shipping_provider_code.strip().upper()
    row = (
        await session.execute(
            text(
                """
                SELECT
                  id,
                  name,
                  shipping_provider_code
                FROM shipping_providers
                WHERE shipping_provider_code = :shipping_provider_code
                  AND active IS TRUE
                LIMIT 1
                """
            ),
            {"shipping_provider_code": code},
        )
    ).mappings().first()

    if row is None:
        raise ValueError(f"shipping_provider_mapping_not_found:{code}")

    return {
        "shipping_provider_id": int(row["id"]),
        "shipping_provider_code": str(row["shipping_provider_code"]),
        "shipping_provider_name": str(row["name"]),
    }


async def _upsert_shipping_record(
    session: AsyncSession,
    *,
    base: Mapping[str, object],
    package: Mapping[str, object],
    completed_at: datetime | None,
) -> int:
    provider = await _resolve_shipping_provider(
        session,
        shipping_provider_code=_clean_required(
            package.get("shipping_provider_code"),
            field="shipping_provider_code",
        ),
    )

    package_no = int(package["package_no"])
    provider_name = _clean(package.get("shipping_provider_name")) or str(
        provider["shipping_provider_name"]
    )

    dest_province = _clean(package.get("dest_province")) or _clean(base.get("dest_province"))
    dest_city = _clean(package.get("dest_city")) or _clean(base.get("dest_city"))

    row = (
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
                  COALESCE(:completed_at, now())
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
                RETURNING id
                """
            ),
            {
                "order_ref": str(base["order_ref"]),
                "platform": str(base["platform"]),
                "store_code": str(base["store_code"]),
                "package_no": package_no,
                "warehouse_id": int(base["warehouse_id"]),
                "shipping_provider_id": int(provider["shipping_provider_id"]),
                "shipping_provider_code": str(provider["shipping_provider_code"]),
                "shipping_provider_name": provider_name,
                "tracking_no": _clean_required(package.get("tracking_no"), field="tracking_no"),
                "gross_weight_kg": _decimal_or_none(package.get("gross_weight_kg")),  # type: ignore[arg-type]
                "freight_estimated": _decimal_or_none(package.get("freight_estimated")),  # type: ignore[arg-type]
                "surcharge_estimated": _decimal_or_none(package.get("surcharge_estimated")),  # type: ignore[arg-type]
                "cost_estimated": _decimal_or_none(package.get("cost_estimated")),  # type: ignore[arg-type]
                "length_cm": _decimal_or_none(package.get("length_cm")),  # type: ignore[arg-type]
                "width_cm": _decimal_or_none(package.get("width_cm")),  # type: ignore[arg-type]
                "height_cm": _decimal_or_none(package.get("height_cm")),  # type: ignore[arg-type]
                "sender": _clean(package.get("sender")),
                "dest_province": dest_province,
                "dest_city": dest_city,
                "completed_at": completed_at,
            },
        )
    ).scalar_one()

    return int(row)


def _assert_request_identity(
    ctx: Mapping[str, Any],
    *,
    logistics_request_id: int | None,
    logistics_request_no: str | None,
) -> None:
    existing_id = ctx.get("logistics_request_id")
    existing_no = _clean(ctx.get("logistics_request_no"))

    if existing_id is not None and logistics_request_id is not None:
        if int(existing_id) != int(logistics_request_id):
            raise ValueError("logistics_request_id_mismatch")

    if existing_no is not None and logistics_request_no is not None:
        if existing_no != logistics_request_no.strip():
            raise ValueError("logistics_request_no_mismatch")


async def apply_logistics_shipping_results(
    session: AsyncSession,
    *,
    source_ref: str,
    logistics_request_id: int | None,
    logistics_request_no: str | None,
    completed_at: datetime | None,
    packages: list[Mapping[str, object]],
) -> dict[str, object] | None:
    ctx = await _load_shipping_result_context(session, source_ref=source_ref)
    if ctx is None:
        return None

    export_status = str(ctx["export_status"])
    logistics_status = str(ctx["logistics_status"])

    if export_status != "EXPORTED":
        raise ValueError("logistics_export_record_not_exported")

    if logistics_status not in ("IMPORTED", "IN_PROGRESS", "COMPLETED"):
        raise ValueError("logistics_export_record_not_imported")

    _assert_request_identity(
        ctx,
        logistics_request_id=logistics_request_id,
        logistics_request_no=logistics_request_no,
    )

    base = _base_shipping_record_values(ctx)

    shipping_record_ids: list[int] = []
    for package in packages:
        shipping_record_ids.append(
            await _upsert_shipping_record(
                session,
                base=base,
                package=package,
                completed_at=completed_at,
            )
        )

    row = (
        await session.execute(
            text(
                """
                UPDATE wms_logistics_export_records
                   SET logistics_status = 'COMPLETED',
                       logistics_request_id = COALESCE(:logistics_request_id, logistics_request_id),
                       logistics_request_no = COALESCE(:logistics_request_no, logistics_request_no),
                       logistics_completed_at = COALESCE(:completed_at, now()),
                       last_attempt_at = now(),
                       last_error = NULL,
                       updated_at = now()
                 WHERE source_ref = :source_ref
                 RETURNING
                   source_ref,
                   logistics_status,
                   logistics_completed_at
                """
            ),
            {
                "source_ref": str(source_ref).strip(),
                "logistics_request_id": logistics_request_id,
                "logistics_request_no": logistics_request_no.strip()
                if logistics_request_no is not None
                else None,
                "completed_at": completed_at,
            },
        )
    ).mappings().first()

    if row is None:
        return None

    return {
        "source_ref": str(row["source_ref"]),
        "logistics_status": str(row["logistics_status"]),
        "logistics_completed_at": row["logistics_completed_at"],
        "shipping_record_ids": shipping_record_ids,
        "packages_count": len(shipping_record_ids),
    }
