# app/oms/fulfillment_projection/repos/fulfillment_projection_repo.py
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.oms.fulfillment_projection.contracts.fulfillment_projection import (
    OmsProjectionPlatform,
    OmsProjectionResource,
)


@dataclass(frozen=True)
class ProjectionResourceConfig:
    resource: OmsProjectionResource
    table_name: str
    id_column: str
    columns: tuple[str, ...]
    searchable_columns: tuple[str, ...]
    order_by_sql: str


RESOURCE_CONFIGS: dict[OmsProjectionResource, ProjectionResourceConfig] = {
    "orders": ProjectionResourceConfig(
        resource="orders",
        table_name="wms_oms_fulfillment_order_projection",
        id_column="ready_order_id",
        columns=(
            "ready_order_id",
            "source_order_id",
            "platform",
            "store_code",
            "store_name",
            "platform_order_no",
            "platform_status",
            "receiver_name",
            "receiver_phone",
            "receiver_province",
            "receiver_city",
            "receiver_district",
            "receiver_address",
            "receiver_postcode",
            "buyer_remark",
            "seller_remark",
            "ready_status",
            "ready_at",
            "source_updated_at",
            "line_count",
            "component_count",
            "total_required_qty",
            "source_hash",
            "sync_version",
            "synced_at",
        ),
        searchable_columns=(
            "ready_order_id",
            "platform",
            "store_code",
            "store_name",
            "platform_order_no",
            "receiver_name",
            "receiver_phone",
        ),
        order_by_sql="source_updated_at DESC, ready_order_id ASC",
    ),
    "lines": ProjectionResourceConfig(
        resource="lines",
        table_name="wms_oms_fulfillment_line_projection",
        id_column="ready_line_id",
        columns=(
            "ready_line_id",
            "ready_order_id",
            "source_line_id",
            "platform",
            "store_code",
            "identity_kind",
            "identity_value",
            "merchant_sku",
            "platform_item_id",
            "platform_sku_id",
            "platform_goods_name",
            "platform_sku_name",
            "ordered_qty",
            "fsku_id",
            "fsku_code",
            "fsku_name",
            "fsku_status_snapshot",
            "source_hash",
            "sync_version",
            "synced_at",
        ),
        searchable_columns=(
            "ready_line_id",
            "ready_order_id",
            "platform",
            "store_code",
            "identity_kind",
            "identity_value",
            "merchant_sku",
            "platform_item_id",
            "platform_sku_id",
            "platform_goods_name",
            "fsku_code",
            "fsku_name",
        ),
        order_by_sql="ready_order_id ASC, source_line_id ASC",
    ),
    "components": ProjectionResourceConfig(
        resource="components",
        table_name="wms_oms_fulfillment_component_projection",
        id_column="ready_component_id",
        columns=(
            "ready_component_id",
            "ready_line_id",
            "ready_order_id",
            "resolved_item_id",
            "resolved_item_sku_code_id",
            "resolved_item_uom_id",
            "component_sku_code",
            "sku_code_snapshot",
            "item_name_snapshot",
            "uom_snapshot",
            "qty_per_fsku",
            "required_qty",
            "alloc_unit_price",
            "sort_order",
            "source_hash",
            "sync_version",
            "synced_at",
        ),
        searchable_columns=(
            "ready_component_id",
            "ready_line_id",
            "ready_order_id",
            "component_sku_code",
            "sku_code_snapshot",
            "item_name_snapshot",
            "uom_snapshot",
        ),
        order_by_sql="ready_order_id ASC, ready_line_id ASC, sort_order ASC",
    ),
}

RESOURCE_ORDER: tuple[OmsProjectionResource, ...] = ("orders", "lines", "components")
SYNC_RESOURCE = "fulfillment-ready-orders"


class OmsFulfillmentProjectionRepo:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def config(resource: OmsProjectionResource) -> ProjectionResourceConfig:
        try:
            return RESOURCE_CONFIGS[resource]
        except KeyError as exc:
            raise ValueError(f"unsupported OMS projection resource: {resource}") from exc

    @staticmethod
    def jsonable(value: Any) -> Any:
        if isinstance(value, Decimal):
            return str(value)
        return value

    @staticmethod
    def sync_run_from_row(row: Any) -> dict[str, Any]:
        data = dict(row)
        return {
            "id": int(data["id"]),
            "resource": str(data["resource"]),
            "platform": data.get("platform"),
            "store_code": data.get("store_code"),
            "status": str(data["status"]),
            "fetched": int(data.get("fetched") or 0),
            "upserted_orders": int(data.get("upserted_orders") or 0),
            "upserted_lines": int(data.get("upserted_lines") or 0),
            "upserted_components": int(data.get("upserted_components") or 0),
            "pages": int(data.get("pages") or 0),
            "started_at": data["started_at"],
            "finished_at": data.get("finished_at"),
            "duration_ms": (
                int(data["duration_ms"]) if data.get("duration_ms") is not None else None
            ),
            "error_message": data.get("error_message"),
            "triggered_by_user_id": (
                int(data["triggered_by_user_id"])
                if data.get("triggered_by_user_id") is not None
                else None
            ),
            "oms_api_base_url_snapshot": data.get("oms_api_base_url_snapshot"),
            "sync_version": data.get("sync_version"),
        }

    def latest_sync_run(self) -> dict[str, Any] | None:
        row = (
            self.db.execute(
                text(
                    """
                    SELECT
                        id,
                        resource,
                        platform,
                        store_code,
                        status,
                        fetched,
                        upserted_orders,
                        upserted_lines,
                        upserted_components,
                        pages,
                        started_at,
                        finished_at,
                        duration_ms,
                        error_message,
                        triggered_by_user_id,
                        oms_api_base_url_snapshot,
                        sync_version
                    FROM wms_oms_fulfillment_projection_sync_runs
                    WHERE resource = 'fulfillment-ready-orders'
                    ORDER BY started_at DESC, id DESC
                    LIMIT 1
                    """
                )
            )
            .mappings()
            .first()
        )
        return self.sync_run_from_row(row) if row is not None else None

    def resource_stats(self, cfg: ProjectionResourceConfig) -> dict[str, Any]:
        row = (
            self.db.execute(
                text(
                    f"""
                    SELECT
                        count(*)::bigint AS row_count,
                        max(synced_at) AS max_synced_at
                    FROM {cfg.table_name}
                    """
                )
            )
            .mappings()
            .one()
        )
        return {
            "row_count": int(row["row_count"] or 0),
            "max_synced_at": row["max_synced_at"],
        }

    def list_projection_rows(
        self,
        *,
        cfg: ProjectionResourceConfig,
        limit: int,
        offset: int,
        q: str | None,
    ) -> dict[str, Any]:
        where_sql = ""
        params: dict[str, Any] = {"limit": int(limit), "offset": int(offset)}
        query_text = (q or "").strip()
        if query_text and cfg.searchable_columns:
            where_parts = [
                f"CAST({column} AS TEXT) ILIKE :q"
                for column in cfg.searchable_columns
            ]
            where_sql = "WHERE " + " OR ".join(where_parts)
            params["q"] = f"%{query_text}%"

        total = int(
            self.db.execute(
                text(f"SELECT count(*)::bigint FROM {cfg.table_name} {where_sql}"),
                params,
            ).scalar_one()
        )

        rows = (
            self.db.execute(
                text(
                    f"""
                    SELECT {", ".join(cfg.columns)}
                    FROM {cfg.table_name}
                    {where_sql}
                    ORDER BY {cfg.order_by_sql}
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            )
            .mappings()
            .all()
        )

        return {
            "resource": cfg.resource,
            "table_name": cfg.table_name,
            "limit": int(limit),
            "offset": int(offset),
            "total": total,
            "columns": list(cfg.columns),
            "rows": [
                {key: self.jsonable(value) for key, value in dict(row).items()}
                for row in rows
            ],
        }

    def create_sync_run(
        self,
        *,
        platform: OmsProjectionPlatform | None,
        store_code: str | None,
        triggered_by_user_id: int | None,
        oms_api_base_url_snapshot: str | None,
        sync_version: str,
    ) -> int:
        row = (
            self.db.execute(
                text(
                    """
                    INSERT INTO wms_oms_fulfillment_projection_sync_runs (
                        resource,
                        platform,
                        store_code,
                        status,
                        fetched,
                        upserted_orders,
                        upserted_lines,
                        upserted_components,
                        pages,
                        started_at,
                        triggered_by_user_id,
                        oms_api_base_url_snapshot,
                        sync_version
                    )
                    VALUES (
                        'fulfillment-ready-orders',
                        :platform,
                        :store_code,
                        'RUNNING',
                        0,
                        0,
                        0,
                        0,
                        0,
                        now(),
                        :triggered_by_user_id,
                        :oms_api_base_url_snapshot,
                        :sync_version
                    )
                    RETURNING id
                    """
                ),
                {
                    "platform": platform,
                    "store_code": store_code,
                    "triggered_by_user_id": triggered_by_user_id,
                    "oms_api_base_url_snapshot": oms_api_base_url_snapshot,
                    "sync_version": sync_version,
                },
            )
            .mappings()
            .one()
        )
        self.db.commit()
        return int(row["id"])

    def finish_sync_run(
        self,
        *,
        run_id: int,
        status: str,
        duration_ms: int,
        fetched: int = 0,
        upserted_orders: int = 0,
        upserted_lines: int = 0,
        upserted_components: int = 0,
        pages: int = 0,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        row = (
            self.db.execute(
                text(
                    """
                    UPDATE wms_oms_fulfillment_projection_sync_runs
                       SET status = :status,
                           fetched = :fetched,
                           upserted_orders = :upserted_orders,
                           upserted_lines = :upserted_lines,
                           upserted_components = :upserted_components,
                           pages = :pages,
                           finished_at = now(),
                           duration_ms = :duration_ms,
                           error_message = :error_message
                     WHERE id = :run_id
                    RETURNING
                        id,
                        resource,
                        platform,
                        store_code,
                        status,
                        fetched,
                        upserted_orders,
                        upserted_lines,
                        upserted_components,
                        pages,
                        started_at,
                        finished_at,
                        duration_ms,
                        error_message,
                        triggered_by_user_id,
                        oms_api_base_url_snapshot,
                        sync_version
                    """
                ),
                {
                    "run_id": int(run_id),
                    "status": status,
                    "fetched": int(fetched),
                    "upserted_orders": int(upserted_orders),
                    "upserted_lines": int(upserted_lines),
                    "upserted_components": int(upserted_components),
                    "pages": int(pages),
                    "duration_ms": int(duration_ms),
                    "error_message": error_message,
                },
            )
            .mappings()
            .one()
        )
        self.db.commit()
        return self.sync_run_from_row(row)

    def list_sync_runs(
        self,
        *,
        platform: OmsProjectionPlatform | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        where_parts = ["resource = 'fulfillment-ready-orders'"]
        params: dict[str, Any] = {"limit": int(limit)}
        if platform is not None:
            where_parts.append("platform = :platform")
            params["platform"] = platform

        rows = (
            self.db.execute(
                text(
                    f"""
                    SELECT
                        id,
                        resource,
                        platform,
                        store_code,
                        status,
                        fetched,
                        upserted_orders,
                        upserted_lines,
                        upserted_components,
                        pages,
                        started_at,
                        finished_at,
                        duration_ms,
                        error_message,
                        triggered_by_user_id,
                        oms_api_base_url_snapshot,
                        sync_version
                    FROM wms_oms_fulfillment_projection_sync_runs
                    WHERE {" AND ".join(where_parts)}
                    ORDER BY started_at DESC, id DESC
                    LIMIT :limit
                    """
                ),
                params,
            )
            .mappings()
            .all()
        )
        return [self.sync_run_from_row(row) for row in rows]

    def check_orders(self, limit: int) -> list[dict[str, Any]]:
        rows = (
            self.db.execute(
                text(
                    """
                    WITH line_actuals AS (
                      SELECT
                        ready_order_id,
                        count(*)::int AS actual_line_count
                      FROM wms_oms_fulfillment_line_projection
                      GROUP BY ready_order_id
                    ),
                    component_actuals AS (
                      SELECT
                        ready_order_id,
                        count(*)::int AS actual_component_count,
                        COALESCE(sum(required_qty), 0)::numeric(18, 6) AS actual_required_qty
                      FROM wms_oms_fulfillment_component_projection
                      GROUP BY ready_order_id
                    )
                    SELECT
                      o.ready_order_id,
                      o.line_count AS expected_line_count,
                      COALESCE(l.actual_line_count, 0) AS actual_line_count,
                      o.component_count AS expected_component_count,
                      COALESCE(c.actual_component_count, 0) AS actual_component_count,
                      o.total_required_qty AS expected_required_qty,
                      COALESCE(c.actual_required_qty, 0)::numeric(18, 6) AS actual_required_qty
                    FROM wms_oms_fulfillment_order_projection AS o
                    LEFT JOIN line_actuals AS l
                      ON l.ready_order_id = o.ready_order_id
                    LEFT JOIN component_actuals AS c
                      ON c.ready_order_id = o.ready_order_id
                    WHERE o.line_count <> COALESCE(l.actual_line_count, 0)
                       OR o.component_count <> COALESCE(c.actual_component_count, 0)
                       OR o.total_required_qty <> COALESCE(c.actual_required_qty, 0)
                    ORDER BY o.ready_order_id ASC
                    LIMIT :limit
                    """
                ),
                {"limit": int(limit)},
            )
            .mappings()
            .all()
        )

        issues: list[dict[str, Any]] = []
        for row in rows:
            ready_order_id = str(row["ready_order_id"])
            if row["expected_line_count"] != row["actual_line_count"]:
                issues.append(
                    {
                        "issue_type": "ORDER_LINE_COUNT_MISMATCH",
                        "resource": "orders",
                        "source_id": ready_order_id,
                        "message": "订单投影 line_count 与行投影实际数量不一致",
                        "ready_order_id": ready_order_id,
                        "expected_value": str(row["expected_line_count"]),
                        "actual_value": str(row["actual_line_count"]),
                    }
                )
            if row["expected_component_count"] != row["actual_component_count"]:
                issues.append(
                    {
                        "issue_type": "ORDER_COMPONENT_COUNT_MISMATCH",
                        "resource": "orders",
                        "source_id": ready_order_id,
                        "message": "订单投影 component_count 与组件投影实际数量不一致",
                        "ready_order_id": ready_order_id,
                        "expected_value": str(row["expected_component_count"]),
                        "actual_value": str(row["actual_component_count"]),
                    }
                )
            if row["expected_required_qty"] != row["actual_required_qty"]:
                issues.append(
                    {
                        "issue_type": "ORDER_REQUIRED_QTY_MISMATCH",
                        "resource": "orders",
                        "source_id": ready_order_id,
                        "message": "订单投影 total_required_qty 与组件 required_qty 合计不一致",
                        "ready_order_id": ready_order_id,
                        "expected_value": str(row["expected_required_qty"]),
                        "actual_value": str(row["actual_required_qty"]),
                    }
                )

        return issues[:limit]

    def check_lines(self, limit: int) -> list[dict[str, Any]]:
        rows = (
            self.db.execute(
                text(
                    """
                    SELECT
                        l.ready_line_id,
                        l.ready_order_id
                    FROM wms_oms_fulfillment_line_projection AS l
                    LEFT JOIN wms_oms_fulfillment_order_projection AS o
                      ON o.ready_order_id = l.ready_order_id
                    WHERE o.ready_order_id IS NULL
                    ORDER BY l.ready_line_id ASC
                    LIMIT :limit
                    """
                ),
                {"limit": int(limit)},
            )
            .mappings()
            .all()
        )
        return [
            {
                "issue_type": "LINE_ORDER_MISSING_IN_PROJECTION",
                "resource": "lines",
                "source_id": str(row["ready_line_id"]),
                "message": "行投影中的 ready_order_id 在订单投影中不存在",
                "ready_order_id": str(row["ready_order_id"]),
                "ready_line_id": str(row["ready_line_id"]),
            }
            for row in rows
        ]

    def check_components(self, limit: int) -> list[dict[str, Any]]:
        rows = (
            self.db.execute(
                text(
                    """
                    SELECT
                        c.ready_component_id,
                        c.ready_line_id,
                        c.ready_order_id,
                        l.ready_order_id AS line_ready_order_id,
                        o.ready_order_id AS order_ready_order_id,
                        CASE
                          WHEN o.ready_order_id IS NULL THEN 'COMPONENT_ORDER_MISSING_IN_PROJECTION'
                          WHEN l.ready_line_id IS NULL THEN 'COMPONENT_LINE_MISSING_IN_PROJECTION'
                          WHEN l.ready_order_id <> c.ready_order_id THEN 'COMPONENT_LINE_ORDER_MISMATCH'
                          ELSE 'OK'
                        END AS issue_type
                    FROM wms_oms_fulfillment_component_projection AS c
                    LEFT JOIN wms_oms_fulfillment_order_projection AS o
                      ON o.ready_order_id = c.ready_order_id
                    LEFT JOIN wms_oms_fulfillment_line_projection AS l
                      ON l.ready_line_id = c.ready_line_id
                    WHERE o.ready_order_id IS NULL
                       OR l.ready_line_id IS NULL
                       OR l.ready_order_id <> c.ready_order_id
                    ORDER BY c.ready_component_id ASC
                    LIMIT :limit
                    """
                ),
                {"limit": int(limit)},
            )
            .mappings()
            .all()
        )

        messages = {
            "COMPONENT_ORDER_MISSING_IN_PROJECTION": "组件投影中的 ready_order_id 在订单投影中不存在",
            "COMPONENT_LINE_MISSING_IN_PROJECTION": "组件投影中的 ready_line_id 在行投影中不存在",
            "COMPONENT_LINE_ORDER_MISMATCH": "组件投影的 ready_order_id 与行投影所属 ready_order_id 不一致",
        }
        return [
            {
                "issue_type": str(row["issue_type"]),
                "resource": "components",
                "source_id": str(row["ready_component_id"]),
                "message": messages.get(str(row["issue_type"]), "OMS 履约组件投影一致性异常"),
                "ready_order_id": str(row["ready_order_id"]),
                "ready_line_id": str(row["ready_line_id"]),
                "ready_component_id": str(row["ready_component_id"]),
                "expected_value": (
                    str(row["ready_order_id"])
                    if row["issue_type"] == "COMPONENT_LINE_ORDER_MISMATCH"
                    else None
                ),
                "actual_value": (
                    str(row["line_ready_order_id"])
                    if row["issue_type"] == "COMPONENT_LINE_ORDER_MISMATCH"
                    else None
                ),
            }
            for row in rows
        ]


__all__ = [
    "OmsFulfillmentProjectionRepo",
    "ProjectionResourceConfig",
    "RESOURCE_CONFIGS",
    "RESOURCE_ORDER",
    "SYNC_RESOURCE",
]
