# app/procurement/repos/purchase_order_create_repo.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pms.contracts import PmsExportUom
from app.integrations.pms.factory import create_pms_read_client
from app.procurement.models.purchase_order import PurchaseOrder
from app.procurement.models.purchase_order_line import PurchaseOrderLine
from app.procurement.repos.purchase_order_line_completion_repo import (
    upsert_completion_rows_for_po,
)


async def reserve_purchase_order_id(session: AsyncSession) -> int:
    """
    预留 purchase_orders.id，便于 service 层用同一个 id 生成 po_no=PO-{id}。
    """
    row = await session.execute(text("SELECT nextval('purchase_orders_id_seq')"))
    return int(row.scalar_one())


def _uom_name_snapshot(row: PmsExportUom) -> str:
    name = str(row.uom_name or row.display_name or row.uom or "").strip()
    if not name:
        raise ValueError("PMS export uom_name/uom 不能为空")
    return name


async def require_item_uom_ratio_to_base(
    session: AsyncSession,
    *,
    item_id: int,
    uom_id: int,
) -> tuple[int, str]:
    row = await create_pms_read_client(session=session).get_uom(item_uom_id=int(uom_id))
    if row is None or int(row.item_id) != int(item_id):
        raise ValueError(
            f"uom_id 不存在或不属于该商品：item_id={int(item_id)} uom_id={int(uom_id)}"
        )

    ratio = int(row.ratio_to_base or 0)
    if ratio <= 0:
        raise ValueError("PMS export uom.ratio_to_base 必须 >= 1")

    return ratio, _uom_name_snapshot(row)


async def pick_default_purchase_uom(
    session: AsyncSession,
    *,
    item_id: int,
) -> tuple[int, int, str]:
    """
    采购默认单位读取统一走 PMS integration client。

    优先级：
    1) is_purchase_default = true
    2) is_base = true
    3) 任意第一条 UOM
    返回：(uom_id, ratio_to_base, uom_name_snapshot)
    """
    client = create_pms_read_client(session=session)
    row = await client.get_purchase_default_or_base_uom(item_id=int(item_id))

    if row is None:
        rows = await client.list_uoms_by_item_id(item_id=int(item_id))
        row = rows[0] if rows else None

    if row is None:
        raise ValueError(f"商品缺少 PMS export uoms：item_id={int(item_id)}")

    ratio = int(row.ratio_to_base or 0)
    if ratio <= 0:
        raise ValueError("PMS export uom.ratio_to_base 必须 >= 1")

    return int(row.id), ratio, _uom_name_snapshot(row)


async def insert_purchase_order_head(
    session: AsyncSession,
    *,
    po_id: int,
    po_no: str,
    supplier_id: int,
    supplier_name: str,
    warehouse_id: int,
    purchaser: str,
    purchase_time: datetime,
    total_amount: Decimal,
    remark: str | None,
) -> PurchaseOrder:
    po = PurchaseOrder(
        id=int(po_id),
        po_no=str(po_no),
        supplier_id=int(supplier_id),
        supplier_name=str(supplier_name),
        warehouse_id=int(warehouse_id),
        purchaser=str(purchaser),
        purchase_time=purchase_time,
        total_amount=total_amount,
        status="CREATED",
        remark=remark,
    )
    session.add(po)
    await session.flush()
    return po


async def insert_purchase_order_lines(
    session: AsyncSession,
    *,
    po_id: int,
    lines: Sequence[dict[str, Any]],
) -> None:
    for line in lines:
        session.add(PurchaseOrderLine(po_id=int(po_id), **dict(line)))
    await session.flush()

    # 同事务初始化采购行 completion 读表。
    await upsert_completion_rows_for_po(session, po_id=int(po_id))


__all__ = [
    "reserve_purchase_order_id",
    "require_item_uom_ratio_to_base",
    "pick_default_purchase_uom",
    "insert_purchase_order_head",
    "insert_purchase_order_lines",
]
