from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.oms.order_facts.contracts.order_sku_resolution import (
    OrderSkuResolutionComponentOut,
    OrderSkuResolutionDataOut,
    OrderSkuResolutionLineOut,
    OrderSkuResolutionNextActionOut,
)


_PLATFORM_TABLES = {
    "pdd": ("oms_pdd_order_mirrors", "oms_pdd_order_mirror_lines", "PDD"),
    "taobao": ("oms_taobao_order_mirrors", "oms_taobao_order_mirror_lines", "TAOBAO"),
    "jd": ("oms_jd_order_mirrors", "oms_jd_order_mirror_lines", "JD"),
}


class OrderSkuResolutionNotFound(Exception):
    pass


class OrderSkuResolutionValidationError(Exception):
    pass


def _tables(platform: str) -> tuple[str, str, str]:
    key = (platform or "").strip().lower()
    if key not in _PLATFORM_TABLES:
        raise OrderSkuResolutionValidationError(f"unsupported platform: {platform!r}")
    return _PLATFORM_TABLES[key]


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _dec(value: Any, *, label: str) -> Decimal:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise OrderSkuResolutionValidationError(f"{label} 非法：{value!r}") from exc
    return d


def _fmt_decimal(value: Any) -> str:
    d = _dec(value, label="decimal")
    s = format(d.normalize(), "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


def _platform_item_sku_value(*, platform_item_id: str | None, platform_sku_id: str | None) -> str | None:
    if not platform_item_id or not platform_sku_id:
        return None
    return f"{platform_item_id}::{platform_sku_id}"


def _identity_candidates(row: Mapping[str, Any]) -> list[tuple[str, str]]:
    merchant_code = _str_or_none(row.get("merchant_code"))
    platform_item_id = _str_or_none(row.get("platform_item_id"))
    platform_sku_id = _str_or_none(row.get("platform_sku_id"))
    platform_item_sku = _platform_item_sku_value(
        platform_item_id=platform_item_id,
        platform_sku_id=platform_sku_id,
    )

    out: list[tuple[str, str]] = []
    if merchant_code:
        out.append(("merchant_code", merchant_code))
    if platform_sku_id:
        out.append(("platform_sku_id", platform_sku_id))
    if platform_item_sku:
        out.append(("platform_item_sku", platform_item_sku))
    return out


def _next_actions(
    *,
    platform: str,
    store_code: str,
    merchant_code: str | None,
    platform_item_id: str | None,
    platform_sku_id: str | None,
) -> list[OrderSkuResolutionNextActionOut]:
    platform_lower = platform.lower()
    return [
        OrderSkuResolutionNextActionOut(
            action="go_code_mapping",
            label="前往平台编码映射页补充平台身份 → OMS FSKU 映射",
            route_path=f"/oms/{platform_lower}/code-mapping",
            payload={
                "platform": platform,
                "store_code": store_code,
                "merchant_code": merchant_code,
                "platform_item_id": platform_item_id,
                "platform_sku_id": platform_sku_id,
            },
        ),
        OrderSkuResolutionNextActionOut(
            action="go_fsku_rules",
            label="前往 FSKU 组合规则页维护 OMS FSKU → 仓库 SKU 组件",
            route_path="/oms/fskus",
            payload={
                "platform": platform,
                "store_code": store_code,
            },
        ),
    ]


async def _load_header(
    session: AsyncSession,
    *,
    platform: str,
    mirror_id: int,
) -> Mapping[str, Any]:
    mirror_table, _line_table, business_platform = _tables(platform)
    row = (
        await session.execute(
            text(
                f"""
                SELECT
                  id,
                  collector_order_id,
                  collector_store_id,
                  collector_store_code,
                  collector_store_name,
                  wms_store_id,
                  platform_order_no,
                  platform_status,
                  source_updated_at,
                  receiver_json,
                  amounts_json,
                  platform_fields_json,
                  raw_refs_json
                FROM {mirror_table}
                WHERE id = :mirror_id
                LIMIT 1
                """
            ),
            {"mirror_id": int(mirror_id)},
        )
    ).mappings().first()

    if row is None:
        raise OrderSkuResolutionNotFound(
            f"{business_platform} platform order mirror not found: {int(mirror_id)}"
        )
    return row


async def _load_lines(
    session: AsyncSession,
    *,
    platform: str,
    mirror_id: int,
) -> list[Mapping[str, Any]]:
    _mirror_table, line_table, _business_platform = _tables(platform)
    rows = (
        await session.execute(
            text(
                f"""
                SELECT
                  id AS line_id,
                  mirror_id,
                  collector_line_id,
                  collector_order_id,
                  platform_order_no,
                  merchant_sku AS merchant_code,
                  platform_item_id,
                  platform_sku_id,
                  title,
                  quantity,
                  line_amount
                FROM {line_table}
                WHERE mirror_id = :mirror_id
                ORDER BY id ASC
                """
            ),
            {"mirror_id": int(mirror_id)},
        )
    ).mappings().all()
    return list(rows)


async def _load_fsku_components(
    session: AsyncSession,
    *,
    fsku_id: int,
    line_qty: Decimal,
) -> list[OrderSkuResolutionComponentOut]:
    rows = (
        await session.execute(
            text(
                """
                SELECT
                  c.resolved_item_id AS item_id,
                  c.resolved_item_sku_code_id AS item_sku_code_id,
                  c.resolved_item_uom_id AS item_uom_id,
                  c.sku_code_snapshot AS sku_code,
                  c.item_name_snapshot AS item_name,
                  c.uom_snapshot AS uom,
                  c.qty_per_fsku AS qty_per_fsku,
                  c.alloc_unit_price AS alloc_unit_price,
                  c.sort_order AS sort_order
                FROM oms_fsku_components c
                JOIN oms_fskus f ON f.id = c.fsku_id
                WHERE c.fsku_id = :fsku_id
                  AND f.status = 'published'
                ORDER BY c.sort_order ASC
                """
            ),
            {"fsku_id": int(fsku_id)},
        )
    ).mappings().all()

    out: list[OrderSkuResolutionComponentOut] = []
    for row in rows:
        qty = line_qty * _dec(row["qty_per_fsku"], label="qty_per_fsku")
        out.append(
            OrderSkuResolutionComponentOut(
                item_id=int(row["item_id"]),
                item_sku_code_id=int(row["item_sku_code_id"]),
                item_uom_id=int(row["item_uom_id"]),
                sku_code=str(row["sku_code"]),
                item_name=str(row["item_name"]),
                uom=str(row["uom"]),
                qty=_fmt_decimal(qty),
                alloc_unit_price=_fmt_decimal(row["alloc_unit_price"]),
                sort_order=int(row["sort_order"]),
            )
        )
    return out


async def _resolve_by_direct_fsku_code(
    session: AsyncSession,
    *,
    code: str,
    line_qty: Decimal,
) -> tuple[int, str, str, list[OrderSkuResolutionComponentOut]] | None:
    row = (
        await session.execute(
            text(
                """
                SELECT id, code, name
                FROM oms_fskus
                WHERE code = :code
                  AND status = 'published'
                LIMIT 1
                """
            ),
            {"code": code},
        )
    ).mappings().first()

    if row is None:
        return None

    components = await _load_fsku_components(
        session,
        fsku_id=int(row["id"]),
        line_qty=line_qty,
    )
    if not components:
        return None

    return int(row["id"]), str(row["code"]), str(row["name"]), components


async def _resolve_by_platform_code_mapping(
    session: AsyncSession,
    *,
    platform: str,
    store_code: str,
    identity_kind: str,
    identity_value: str,
    line_qty: Decimal,
) -> tuple[int, str, str, list[OrderSkuResolutionComponentOut]] | None:
    row = (
        await session.execute(
            text(
                """
                SELECT f.id, f.code, f.name
                FROM platform_code_fsku_mappings m
                JOIN oms_fskus f ON f.id = m.fsku_id
                WHERE m.platform = :platform
                  AND m.store_code = :store_code
                  AND m.identity_kind = :identity_kind
                  AND m.identity_value = :identity_value
                  AND f.status = 'published'
                LIMIT 1
                """
            ),
            {
                "platform": platform,
                "store_code": store_code,
                "identity_kind": identity_kind,
                "identity_value": identity_value,
            },
        )
    ).mappings().first()

    if row is None:
        return None

    components = await _load_fsku_components(
        session,
        fsku_id=int(row["id"]),
        line_qty=line_qty,
    )
    if not components:
        return None

    return int(row["id"]), str(row["code"]), str(row["name"]), components


async def _resolve_line(
    session: AsyncSession,
    *,
    platform: str,
    store_code: str,
    mirror_id: int,
    row: Mapping[str, Any],
) -> OrderSkuResolutionLineOut:
    line_id = int(row["line_id"])
    merchant_code = _str_or_none(row.get("merchant_code"))
    platform_item_id = _str_or_none(row.get("platform_item_id"))
    platform_sku_id = _str_or_none(row.get("platform_sku_id"))
    line_qty = _dec(row.get("quantity") or "0", label=f"line_id={line_id}.quantity")

    fsku_id: int | None = None
    fsku_code: str | None = None
    fsku_name: str | None = None
    source = "unresolved"
    resolved_identity_kind: str | None = None
    resolved_identity_value: str | None = None
    components: list[OrderSkuResolutionComponentOut] = []

    if merchant_code:
        direct = await _resolve_by_direct_fsku_code(
            session,
            code=merchant_code,
            line_qty=line_qty,
        )
        if direct is not None:
            fsku_id, fsku_code, fsku_name, components = direct
            source = "direct_fsku_code"
            resolved_identity_kind = "merchant_code"
            resolved_identity_value = merchant_code

    if not components:
        for identity_kind, identity_value in _identity_candidates(row):
            mapped = await _resolve_by_platform_code_mapping(
                session,
                platform=platform,
                store_code=store_code,
                identity_kind=identity_kind,
                identity_value=identity_value,
                line_qty=line_qty,
            )
            if mapped is not None:
                fsku_id, fsku_code, fsku_name, components = mapped
                source = "code_mapping"
                resolved_identity_kind = identity_kind
                resolved_identity_value = identity_value
                break

    unresolved_reason: str | None = None
    next_actions: list[OrderSkuResolutionNextActionOut] = []
    if not components:
        unresolved_reason = "MISSING_PLATFORM_IDENTITY" if not _identity_candidates(row) else "CODE_NOT_MAPPED"
        next_actions = _next_actions(
            platform=platform,
            store_code=store_code,
            merchant_code=merchant_code,
            platform_item_id=platform_item_id,
            platform_sku_id=platform_sku_id,
        )

    return OrderSkuResolutionLineOut(
        platform=platform,
        mirror_id=int(mirror_id),
        line_id=line_id,
        collector_order_id=int(row["collector_order_id"]),
        collector_line_id=int(row["collector_line_id"]),
        store_code=store_code,
        platform_order_no=str(row["platform_order_no"]),
        merchant_code=merchant_code,
        platform_item_id=platform_item_id,
        platform_sku_id=platform_sku_id,
        title=_str_or_none(row.get("title")),
        quantity=_fmt_decimal(row.get("quantity") or "0"),
        line_amount=_fmt_decimal(row["line_amount"]) if row.get("line_amount") is not None else None,
        resolution_status="resolved" if components else "needs_mapping",
        resolution_source=source,  # type: ignore[arg-type]
        resolved_identity_kind=resolved_identity_kind,  # type: ignore[arg-type]
        resolved_identity_value=resolved_identity_value,
        fsku_id=fsku_id,
        fsku_code=fsku_code,
        fsku_name=fsku_name,
        unresolved_reason=unresolved_reason,
        next_actions=next_actions,
        components=components,
    )


async def get_order_sku_resolution(
    session: AsyncSession,
    *,
    platform: str,
    mirror_id: int,
) -> OrderSkuResolutionDataOut:
    _mirror_table, _line_table, business_platform = _tables(platform)
    header = await _load_header(session, platform=platform, mirror_id=int(mirror_id))
    lines = await _load_lines(session, platform=platform, mirror_id=int(mirror_id))

    store_code = str(header["collector_store_code"])
    out_lines = [
        await _resolve_line(
            session,
            platform=business_platform,
            store_code=store_code,
            mirror_id=int(mirror_id),
            row=row,
        )
        for row in lines
    ]

    status = "resolved" if out_lines and all(x.resolution_status == "resolved" for x in out_lines) else "needs_mapping"

    return OrderSkuResolutionDataOut(
        platform=business_platform,
        mirror_id=int(mirror_id),
        platform_order_no=str(header["platform_order_no"]),
        store_code=store_code,
        status=status,  # type: ignore[arg-type]
        lines=out_lines,
    )
