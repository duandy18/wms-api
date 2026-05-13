from __future__ import annotations

from app.integrations.procurement.contracts import (
    ProcurementPurchaseOrderSourceOptionOut,
)
from app.integrations.procurement.factory import create_procurement_read_client
from app.wms.inventory_adjustment.return_inbound.contracts.purchase_source_options import (
    InboundReceiptPurchaseSourceOptionOut,
    InboundReceiptPurchaseSourceOptionsOut,
)


async def list_inbound_receipt_purchase_source_options(
    *,
    target_warehouse_id: int | None = None,
    q: str | None = None,
    limit: int = 200,
) -> InboundReceiptPurchaseSourceOptionsOut:
    """List procurement purchase sources through procurement-api.

    边界说明：
    - WMS 只通过 procurement read API 读取采购来源。
    - 本函数不创建 inbound_receipts。
    - 本函数不读取 WMS 本地 purchase_orders owner 表。
    """

    client = create_procurement_read_client()
    source_options = await client.list_purchase_order_source_options(
        target_warehouse_id=target_warehouse_id,
        q=q,
        limit=limit,
    )

    return InboundReceiptPurchaseSourceOptionsOut(
        items=[
            _map_procurement_source_option(item)
            for item in source_options.items
        ]
    )


def _map_procurement_source_option(
    item: ProcurementPurchaseOrderSourceOptionOut,
) -> InboundReceiptPurchaseSourceOptionOut:
    return InboundReceiptPurchaseSourceOptionOut.model_validate(
        {
            "po_id": item.po_id,
            "po_no": item.po_no,
            "target_warehouse_id": item.target_warehouse_id,
            "target_warehouse_code_snapshot": item.target_warehouse_code_snapshot,
            "target_warehouse_name_snapshot": item.target_warehouse_name_snapshot,
            "supplier_id": item.supplier_id,
            "supplier_code_snapshot": item.supplier_code_snapshot,
            "supplier_name_snapshot": item.supplier_name_snapshot,
            "purchase_time": item.purchase_time,
            "order_status": item.order_status,
            "completion_status": item.completion_status,
            "last_received_at": item.last_received_at,
        }
    )


__all__ = ["list_inbound_receipt_purchase_source_options"]
