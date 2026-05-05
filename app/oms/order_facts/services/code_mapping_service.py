from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.oms.order_facts.contracts.code_mapping import (
    CodeMappingCodeOptionListDataOut,
    CodeMappingCodeOptionOut,
)
from app.oms.services.platform_order_resolve_utils import norm_platform


_PLATFORM_TABLES = {
    "pdd": ("oms_pdd_order_mirrors", "oms_pdd_order_mirror_lines"),
    "taobao": ("oms_taobao_order_mirrors", "oms_taobao_order_mirror_lines"),
    "jd": ("oms_jd_order_mirrors", "oms_jd_order_mirror_lines"),
}


def _tables(platform: str) -> tuple[str, str]:
    key = (platform or "").strip().lower()
    if key not in _PLATFORM_TABLES:
        raise ValueError(f"unsupported platform: {platform!r}")
    return _PLATFORM_TABLES[key]


def _option_out(platform: str, row: Mapping[str, Any]) -> CodeMappingCodeOptionOut:
    binding_id = row.get("binding_id")
    fsku_id = row.get("fsku_id")

    return CodeMappingCodeOptionOut(
        platform=platform,
        store_code=str(row["store_code"]),
        merchant_code=str(row["merchant_code"]),
        latest_title=row.get("latest_title"),
        platform_item_id=row.get("platform_item_id"),
        platform_sku_id=row.get("platform_sku_id"),
        latest_platform_order_no=row.get("latest_platform_order_no"),
        latest_synced_at=row.get("latest_synced_at"),
        orders_count=int(row.get("orders_count") or 0),
        is_bound=binding_id is not None,
        binding_id=int(binding_id) if binding_id is not None else None,
        fsku_id=int(fsku_id) if fsku_id is not None else None,
        fsku_code=row.get("fsku_code"),
        fsku_name=row.get("fsku_name"),
        fsku_status=row.get("fsku_status"),
        binding_updated_at=row.get("binding_updated_at"),
    )


def _base_cte(*, mirror_table: str, line_table: str, where_sql: str) -> str:
    return f"""
        WITH base AS (
          SELECT
            m.collector_store_code AS store_code,
            TRIM(l.merchant_sku) AS merchant_code,
            l.title,
            l.platform_item_id,
            l.platform_sku_id,
            l.platform_order_no,
            m.last_synced_at,
            m.id AS mirror_id,
            l.id AS line_id
          FROM {line_table} l
          JOIN {mirror_table} m ON m.id = l.mirror_id
          WHERE l.merchant_sku IS NOT NULL
            AND TRIM(l.merchant_sku) <> ''
            AND {where_sql}
        ),
        agg AS (
          SELECT
            store_code,
            merchant_code,
            COUNT(DISTINCT platform_order_no) AS orders_count
          FROM base
          GROUP BY store_code, merchant_code
        ),
        latest AS (
          SELECT DISTINCT ON (store_code, merchant_code)
            store_code,
            merchant_code,
            title AS latest_title,
            platform_item_id,
            platform_sku_id,
            platform_order_no AS latest_platform_order_no,
            last_synced_at
          FROM base
          ORDER BY store_code, merchant_code, last_synced_at DESC NULLS LAST, mirror_id DESC, line_id DESC
        )
    """


async def list_code_mapping_code_options(
    session: AsyncSession,
    *,
    platform: str,
    store_code: str | None,
    merchant_code: str | None,
    only_unbound: bool,
    limit: int,
    offset: int,
) -> CodeMappingCodeOptionListDataOut:
    table_platform = (platform or "").strip().lower()
    business_platform = norm_platform(platform)
    mirror_table, line_table = _tables(table_platform)

    clauses: list[str] = ["1 = 1"]
    params: dict[str, Any] = {
        "platform": business_platform,
        "limit": int(limit),
        "offset": int(offset),
    }

    if store_code and store_code.strip():
        clauses.append("m.collector_store_code = :store_code")
        params["store_code"] = store_code.strip()

    if merchant_code and merchant_code.strip():
        clauses.append("l.merchant_sku ILIKE :merchant_code_like")
        params["merchant_code_like"] = f"%{merchant_code.strip()}%"

    where_sql = " AND ".join(clauses)
    base_cte = _base_cte(
        mirror_table=mirror_table,
        line_table=line_table,
        where_sql=where_sql,
    )

    only_unbound_sql = "AND b.id IS NULL" if only_unbound else ""

    count_row = (
        await session.execute(
            text(
                f"""
                {base_cte}
                SELECT COUNT(*) AS total
                FROM agg a
                LEFT JOIN platform_code_fsku_mappings b
                  ON b.platform = :platform
                 AND b.store_code = a.store_code
                 AND b.identity_kind = 'merchant_code'
                 AND b.identity_value = a.merchant_code
                WHERE 1 = 1
                {only_unbound_sql}
                """
            ),
            params,
        )
    ).mappings().one()

    rows = (
        await session.execute(
            text(
                f"""
                {base_cte}
                SELECT
                  l.store_code,
                  l.merchant_code,
                  l.latest_title,
                  l.platform_item_id,
                  l.platform_sku_id,
                  l.latest_platform_order_no,
                  l.last_synced_at AS latest_synced_at,
                  a.orders_count,

                  b.id AS binding_id,
                  b.fsku_id,
                  b.updated_at AS binding_updated_at,

                  f.code AS fsku_code,
                  f.name AS fsku_name,
                  f.status AS fsku_status
                FROM latest l
                JOIN agg a
                  ON a.store_code = l.store_code
                 AND a.merchant_code = l.merchant_code
                LEFT JOIN platform_code_fsku_mappings b
                  ON b.platform = :platform
                 AND b.store_code = l.store_code
                 AND b.identity_kind = 'merchant_code'
                 AND b.identity_value = l.merchant_code
                LEFT JOIN oms_fskus f
                  ON f.id = b.fsku_id
                WHERE 1 = 1
                {only_unbound_sql}
                ORDER BY l.last_synced_at DESC NULLS LAST, l.store_code ASC, l.merchant_code ASC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
    ).mappings().all()

    return CodeMappingCodeOptionListDataOut(
        items=[_option_out(business_platform, row) for row in rows],
        total=int(count_row["total"]),
        limit=int(limit),
        offset=int(offset),
    )
