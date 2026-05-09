# app/router_mount.py
from __future__ import annotations

from fastapi import APIRouter, FastAPI


def mount_routers(app: FastAPI) -> None:
    # ---------------------------------------------------------------------------
    # routers imports
    # ---------------------------------------------------------------------------
    from app.admin.router import router as admin_router
    from app.wms.inventory_adjustment.count.routers.count import router as count_router
    from app.wms.inventory_adjustment.count.routers.count_docs import router as count_docs_router
    from app.wms.inventory_adjustment.count.routers.stock_inventory_recount import router as stock_inventory_recount_router
    from app.wms.inventory_adjustment.summary.routers.summary import (
        router as inventory_adjustment_summary_router,
    )
    from app.finance.routers.router import router as finance_router
    from app.pms.items.routers.item_aggregate import router as item_aggregate_router
    from app.pms.items.routers.item_barcodes import router as item_barcodes_router
    from app.pms.items.routers.item_list import router as item_list_router
    from app.pms.items.routers.item_master import router as item_master_router
    from app.pms.items.routers.item_sku_codes import router as item_sku_codes_router
    from app.pms.items.routers.item_uoms import router as item_uoms_router
    from app.pms.items.routers.items import router as items_router
    from app.pms.sku_coding.routers.sku_coding import router as sku_coding_router
    from app.pms.export.items.routers.barcode_probe import router as pms_export_barcode_probe_router
    from app.pms.export.items.routers.item_aggregate_read import (
        router as pms_export_item_aggregate_read_router,
    )
    from app.pms.export.items.routers.items_read import router as pms_export_items_read_router
    from app.partners.export.suppliers.routers.suppliers_read import (
        router as partners_export_suppliers_read_router,
    )
    from app.wms.analysis.routers.ledger_reconcile_v2 import router as ledger_reconcile_v2_router
    from app.oms.routers.meta_platforms import router as meta_router
    from app.wms.outbound.routers.orders_fulfillment_debug import (
        router as orders_fulfillment_debug_router,
    )
    from app.analytics.routers.orders_sla_stats_routes import router as orders_sla_stats_router
    from app.analytics.routers.orders_stats_routes import router as orders_stats_router
    from app.wms.inbound.routers.inbound_events import router as inbound_events_router
    from app.wms.inbound.routers.inbound_commit import router as inbound_commit_router
    from app.wms.inventory_adjustment.inbound_reversal.routers.inbound_reversal import (
        router as inbound_reversal_router,
    )
    from app.wms.outbound.routers.order_submit import router as order_submit_router
    from app.wms.outbound.routers.manual_docs import router as manual_docs_router
    from app.wms.outbound.routers.manual_submit import router as manual_submit_router
    from app.wms.outbound.routers.outbound_summary import router as outbound_summary_router
    from app.wms.inventory_adjustment.outbound_reversal.routers.outbound_reversal import (
        router as outbound_reversal_router,
    )
    from app.wms.outbound.routers.lot_candidates import router as outbound_lot_candidates_router
    from app.wms.outbound.routers.print_jobs import router as print_jobs_router
    from app.procurement.routers.purchase_orders import router as purchase_orders_router
    from app.procurement.routers.purchase_reports import router as purchase_reports_router
    from app.wms.inventory_adjustment.return_inbound.routers.inbound_receipts import router as inbound_receipts_router
    from app.wms.inventory_adjustment.return_inbound.routers.inbound_operations import router as inbound_operations_router
    from app.wms.inventory_adjustment.return_inbound.routers.return_tasks import router as return_tasks_router
    from app.wms.stock.routers.inventory import router as stock_inventory_router
    from app.wms.snapshot.routers.snapshot_v3 import router as snapshot_v3_router
    from app.wms.ledger.routers.stock_ledger import router as stock_ledger_router
    from app.partners.suppliers.routers.supplier_contacts import router as supplier_contacts_router
    from app.partners.suppliers.routers.suppliers import router as suppliers_router
    from app.user.routers.user import router as user_router
    from app.wms.warehouses.routers.warehouses import router as warehouses_router


    from app.oms.router import router as oms_router

    from app.shipping_assist.handoffs.router import router as shipping_assist_handoffs_router
    from app.shipping_assist.records.router import router as tms_records_router

    # ---------------------------------------------------------------------------
    # scan routes
    # ---------------------------------------------------------------------------
    from app.wms.scan.routers.scan_entrypoint import register as register_scan_entrypoint

    scan_router = APIRouter(tags=["scan"])
    register_scan_entrypoint(scan_router)

    # ---------------------------------------------------------------------------
    # orders_fulfillment_v2 routes
    # ---------------------------------------------------------------------------
    from app.wms.outbound.routers.orders_fulfillment_v2_routes_1_reserve import (
        register as register_orders_fulfillment_v2_reserve,
    )

    orders_fulfillment_v2_router = APIRouter(prefix="/orders", tags=["orders-fulfillment-v2"])
    register_orders_fulfillment_v2_reserve(orders_fulfillment_v2_router)

    # ===========================
    # mount routers
    # ===========================
    app.include_router(scan_router)
    app.include_router(count_router)
    app.include_router(count_docs_router)
    app.include_router(inventory_adjustment_summary_router)
    app.include_router(stock_inventory_recount_router)

    app.include_router(orders_fulfillment_v2_router)
    app.include_router(orders_fulfillment_debug_router)

    app.include_router(order_submit_router)
    app.include_router(manual_docs_router)
    app.include_router(manual_submit_router)
    app.include_router(outbound_lot_candidates_router)
    app.include_router(outbound_summary_router)
    app.include_router(outbound_reversal_router)

    app.include_router(purchase_orders_router)
    app.include_router(purchase_reports_router)
    app.include_router(inbound_receipts_router)
    app.include_router(inbound_operations_router)
    app.include_router(inbound_events_router)
    app.include_router(inbound_commit_router)
    app.include_router(inbound_reversal_router)
    app.include_router(return_tasks_router)
    app.include_router(print_jobs_router)

    app.include_router(meta_router)
    app.include_router(oms_router)

    app.include_router(warehouses_router)

    # PMS 相关：
    # - public 读面先挂
    # - /pms/export/items/barcode-probe 先于 /items/{id}
    # - /items/aggregate 先于 /items/{id}
    # - /pms/export/items、/partners/export/suppliers 独立前缀，不与 owner 冲突
    app.include_router(pms_export_item_aggregate_read_router)
    app.include_router(pms_export_items_read_router)
    app.include_router(pms_export_barcode_probe_router)
    app.include_router(partners_export_suppliers_read_router)
    app.include_router(item_aggregate_router)
    app.include_router(item_list_router)
    app.include_router(items_router)
    app.include_router(item_master_router)
    app.include_router(item_sku_codes_router)
    app.include_router(sku_coding_router)
    app.include_router(item_barcodes_router)
    app.include_router(item_uoms_router)

    app.include_router(suppliers_router)
    app.include_router(supplier_contacts_router)



    app.include_router(shipping_assist_handoffs_router)
    app.include_router(tms_records_router)

    app.include_router(stock_inventory_router)

    app.include_router(stock_ledger_router)

    app.include_router(orders_stats_router)
    app.include_router(orders_sla_stats_router)

    app.include_router(user_router)
    app.include_router(admin_router)

    app.include_router(ledger_reconcile_v2_router)
    app.include_router(snapshot_v3_router)

    app.include_router(finance_router)
