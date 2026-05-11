# app/integrations/pms/projection_reconciliation.py
"""
Read-only reconciliation for WMS PMS projection references.

Boundary:
- This module compares WMS scalar PMS references against WMS local projection tables.
- It must not read PMS owner tables directly.
- It must not write or repair data.
- It must not replace HTTP write validation.
- It exists to support the shared-DB transition before physical FK retirement.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

IdentifierKind = Literal["table", "column"]
IssueType = Literal[
    "ITEM_MISSING_IN_PROJECTION",
    "UOM_MISSING_IN_PROJECTION",
    "UOM_ITEM_MISMATCH",
    "SKU_CODE_MISSING_IN_PROJECTION",
    "SKU_CODE_ITEM_MISMATCH",
]

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class ItemReference:
    source_table: str
    source_id_column: str | None
    item_id_column: str


@dataclass(frozen=True)
class UomReference:
    source_table: str
    source_id_column: str | None
    item_id_column: str
    item_uom_id_column: str


@dataclass(frozen=True)
class SkuCodeReference:
    source_table: str
    source_id_column: str | None
    item_id_column: str
    sku_code_id_column: str


@dataclass(frozen=True)
class PmsProjectionReconciliationIssue:
    issue_type: IssueType
    source_table: str
    source_column: str
    source_id: str
    item_id: int | None = None
    item_uom_id: int | None = None
    sku_code_id: int | None = None
    projection_item_id: int | None = None


@dataclass(frozen=True)
class PmsProjectionReconciliationResult:
    issues: list[PmsProjectionReconciliationIssue]

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def ok(self) -> bool:
        return self.issue_count == 0

    def summary_by_type(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for issue in self.issues:
            out[issue.issue_type] = out.get(issue.issue_type, 0) + 1
        return dict(sorted(out.items()))

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "issue_count": self.issue_count,
            "summary_by_type": self.summary_by_type(),
            "issues": [asdict(issue) for issue in self.issues],
        }


DEFAULT_ITEM_REFERENCES: tuple[ItemReference, ...] = (
    ItemReference("stocks_lot", "id", "item_id"),
    ItemReference("stock_ledger", "id", "item_id"),
    ItemReference("stock_snapshots", "id", "item_id"),
    ItemReference("lots", "id", "item_id"),
    ItemReference("inbound_event_lines", "id", "item_id"),
    ItemReference("wms_inbound_operation_lines", "id", "item_id"),
    ItemReference("inbound_receipt_lines", "id", "item_id"),
    ItemReference("count_doc_lines", "id", "item_id"),
    ItemReference("purchase_order_lines", "id", "item_id"),
    ItemReference("purchase_order_line_completion", None, "item_id"),
    ItemReference("order_items", "id", "item_id"),
    ItemReference("order_lines", "id", "item_id"),
    ItemReference("oms_fsku_components", "id", "resolved_item_id"),
    ItemReference("manual_outbound_lines", "id", "item_id"),
    ItemReference("outbound_commits", "id", "item_id"),
    ItemReference("outbound_event_lines", "id", "item_id"),
    ItemReference("outbound_ship_ops", "id", "item_id"),
    ItemReference("pick_task_lines", "id", "item_id"),
    ItemReference("platform_order_manual_decisions", "id", "item_id"),
    ItemReference("receive_task_scan_events", "id", "item_id"),
    ItemReference("return_task_lines", "id", "item_id"),
    ItemReference("store_items", "id", "item_id"),
    ItemReference("finance_purchase_price_ledger_lines", "id", "item_id"),
    ItemReference("finance_order_sales_lines", "id", "item_id"),
)

DEFAULT_UOM_REFERENCES: tuple[UomReference, ...] = (
    UomReference("inbound_event_lines", "id", "item_id", "actual_uom_id"),
    UomReference("wms_inbound_operation_lines", "id", "item_id", "actual_item_uom_id"),
    UomReference("inbound_receipt_lines", "id", "item_id", "item_uom_id"),
    UomReference("count_doc_lines", "id", "item_id", "counted_item_uom_id"),
    UomReference("purchase_order_lines", "id", "item_id", "purchase_uom_id_snapshot"),
    UomReference("purchase_order_line_completion", None, "item_id", "purchase_uom_id_snapshot"),
    UomReference("oms_fsku_components", "id", "resolved_item_id", "resolved_item_uom_id"),
    UomReference("manual_outbound_lines", "id", "item_id", "item_uom_id"),
)

DEFAULT_SKU_CODE_REFERENCES: tuple[SkuCodeReference, ...] = (
    SkuCodeReference("oms_fsku_components", "id", "resolved_item_id", "resolved_item_sku_code_id"),
)


def _quote_identifier(name: str, *, kind: IdentifierKind) -> str:
    parts = str(name).split(".")
    if not parts or any(not _IDENTIFIER_RE.fullmatch(part) for part in parts):
        raise ValueError(f"invalid SQL {kind} identifier: {name!r}")
    return ".".join(f'"{part}"' for part in parts)


def _source_id_select_and_order(source_id_column: str | None) -> tuple[str, str]:
    if source_id_column is None:
        return "CAST(t.ctid AS TEXT)", "t.ctid"

    quoted = _quote_identifier(source_id_column, kind="column")
    return f"CAST(t.{quoted} AS TEXT)", f"t.{quoted}"


async def _collect_item_issues(
    session: AsyncSession,
    *,
    ref: ItemReference,
    limit: int,
) -> list[PmsProjectionReconciliationIssue]:
    source_table_sql = _quote_identifier(ref.source_table, kind="table")
    source_id_select_sql, source_id_order_sql = _source_id_select_and_order(
        ref.source_id_column
    )
    item_id_sql = _quote_identifier(ref.item_id_column, kind="column")

    rows = (
        await session.execute(
            text(
                f"""
                SELECT
                    {source_id_select_sql} AS source_id,
                    t.{item_id_sql} AS item_id
                FROM {source_table_sql} AS t
                LEFT JOIN wms_pms_item_projection AS p
                  ON p.item_id = t.{item_id_sql}
                WHERE t.{item_id_sql} IS NOT NULL
                  AND p.item_id IS NULL
                ORDER BY {source_id_order_sql}
                LIMIT :limit
                """
            ),
            {"limit": int(limit)},
        )
    ).mappings().all()

    return [
        PmsProjectionReconciliationIssue(
            issue_type="ITEM_MISSING_IN_PROJECTION",
            source_table=ref.source_table,
            source_column=ref.item_id_column,
            source_id=str(row["source_id"]),
            item_id=int(row["item_id"]),
        )
        for row in rows
    ]


async def _collect_uom_issues(
    session: AsyncSession,
    *,
    ref: UomReference,
    limit: int,
) -> list[PmsProjectionReconciliationIssue]:
    source_table_sql = _quote_identifier(ref.source_table, kind="table")
    source_id_select_sql, source_id_order_sql = _source_id_select_and_order(
        ref.source_id_column
    )
    item_id_sql = _quote_identifier(ref.item_id_column, kind="column")
    item_uom_id_sql = _quote_identifier(ref.item_uom_id_column, kind="column")

    rows = (
        await session.execute(
            text(
                f"""
                SELECT
                    {source_id_select_sql} AS source_id,
                    t.{item_id_sql} AS item_id,
                    t.{item_uom_id_sql} AS item_uom_id,
                    u.item_id AS projection_item_id,
                    CASE
                      WHEN u.item_uom_id IS NULL THEN 'UOM_MISSING_IN_PROJECTION'
                      WHEN u.item_id <> t.{item_id_sql} THEN 'UOM_ITEM_MISMATCH'
                      ELSE 'OK'
                    END AS issue_type
                FROM {source_table_sql} AS t
                LEFT JOIN wms_pms_uom_projection AS u
                  ON u.item_uom_id = t.{item_uom_id_sql}
                WHERE t.{item_uom_id_sql} IS NOT NULL
                  AND (
                    u.item_uom_id IS NULL
                    OR u.item_id <> t.{item_id_sql}
                  )
                ORDER BY {source_id_order_sql}
                LIMIT :limit
                """
            ),
            {"limit": int(limit)},
        )
    ).mappings().all()

    return [
        PmsProjectionReconciliationIssue(
            issue_type=str(row["issue_type"]),  # type: ignore[arg-type]
            source_table=ref.source_table,
            source_column=ref.item_uom_id_column,
            source_id=str(row["source_id"]),
            item_id=int(row["item_id"]) if row["item_id"] is not None else None,
            item_uom_id=int(row["item_uom_id"]) if row["item_uom_id"] is not None else None,
            projection_item_id=(
                int(row["projection_item_id"])
                if row["projection_item_id"] is not None
                else None
            ),
        )
        for row in rows
    ]


async def _collect_sku_code_issues(
    session: AsyncSession,
    *,
    ref: SkuCodeReference,
    limit: int,
) -> list[PmsProjectionReconciliationIssue]:
    source_table_sql = _quote_identifier(ref.source_table, kind="table")
    source_id_select_sql, source_id_order_sql = _source_id_select_and_order(
        ref.source_id_column
    )
    item_id_sql = _quote_identifier(ref.item_id_column, kind="column")
    sku_code_id_sql = _quote_identifier(ref.sku_code_id_column, kind="column")

    rows = (
        await session.execute(
            text(
                f"""
                SELECT
                    {source_id_select_sql} AS source_id,
                    t.{item_id_sql} AS item_id,
                    t.{sku_code_id_sql} AS sku_code_id,
                    s.item_id AS projection_item_id,
                    CASE
                      WHEN s.sku_code_id IS NULL THEN 'SKU_CODE_MISSING_IN_PROJECTION'
                      WHEN s.item_id <> t.{item_id_sql} THEN 'SKU_CODE_ITEM_MISMATCH'
                      ELSE 'OK'
                    END AS issue_type
                FROM {source_table_sql} AS t
                LEFT JOIN wms_pms_sku_code_projection AS s
                  ON s.sku_code_id = t.{sku_code_id_sql}
                WHERE t.{sku_code_id_sql} IS NOT NULL
                  AND (
                    s.sku_code_id IS NULL
                    OR s.item_id <> t.{item_id_sql}
                  )
                ORDER BY {source_id_order_sql}
                LIMIT :limit
                """
            ),
            {"limit": int(limit)},
        )
    ).mappings().all()

    return [
        PmsProjectionReconciliationIssue(
            issue_type=str(row["issue_type"]),  # type: ignore[arg-type]
            source_table=ref.source_table,
            source_column=ref.sku_code_id_column,
            source_id=str(row["source_id"]),
            item_id=int(row["item_id"]) if row["item_id"] is not None else None,
            sku_code_id=int(row["sku_code_id"]) if row["sku_code_id"] is not None else None,
            projection_item_id=(
                int(row["projection_item_id"])
                if row["projection_item_id"] is not None
                else None
            ),
        )
        for row in rows
    ]


async def reconcile_pms_projection_references(
    session: AsyncSession,
    *,
    item_references: tuple[ItemReference, ...] = DEFAULT_ITEM_REFERENCES,
    uom_references: tuple[UomReference, ...] = DEFAULT_UOM_REFERENCES,
    sku_code_references: tuple[SkuCodeReference, ...] = DEFAULT_SKU_CODE_REFERENCES,
    per_reference_limit: int = 200,
) -> PmsProjectionReconciliationResult:
    safe_limit = max(1, min(int(per_reference_limit), 1000))
    issues: list[PmsProjectionReconciliationIssue] = []

    for ref in item_references:
        issues.extend(await _collect_item_issues(session, ref=ref, limit=safe_limit))

    for ref in uom_references:
        issues.extend(await _collect_uom_issues(session, ref=ref, limit=safe_limit))

    for ref in sku_code_references:
        issues.extend(await _collect_sku_code_issues(session, ref=ref, limit=safe_limit))

    return PmsProjectionReconciliationResult(issues=issues)


__all__ = [
    "DEFAULT_ITEM_REFERENCES",
    "DEFAULT_SKU_CODE_REFERENCES",
    "DEFAULT_UOM_REFERENCES",
    "ItemReference",
    "PmsProjectionReconciliationIssue",
    "PmsProjectionReconciliationResult",
    "SkuCodeReference",
    "UomReference",
    "reconcile_pms_projection_references",
]
