# app/pms_api/router_mount.py
"""
Standalone PMS API router mount.

Scope:
- PMS owner routes
- PMS export/read routes
- SKU coding routes
- supplier master-data routes currently required by PMS item ownership

Out of scope:
- WMS execution routes
- OMS routes
- Procurement routes
- Finance routes
- Shipping Assist routes
- Admin/user navigation routes
"""

from __future__ import annotations

from fastapi import FastAPI

from app.partners.export.suppliers.routers.suppliers_read import (
    router as partners_export_suppliers_read_router,
)
from app.partners.suppliers.routers.supplier_contacts import (
    router as supplier_contacts_router,
)
from app.partners.suppliers.routers.suppliers import router as suppliers_router
from app.pms.export.barcodes.routers.barcodes_read import (
    router as pms_export_barcodes_read_router,
)
from app.pms.export.items.routers.barcode_probe import (
    router as pms_export_barcode_probe_router,
)
from app.pms.export.items.routers.items_read import (
    router as pms_export_items_read_router,
)
from app.pms.export.sku_codes.routers.sku_codes_read import (
    router as pms_export_sku_codes_read_router,
)
from app.pms.export.uoms.routers.uoms_read import (
    router as pms_export_uoms_read_router,
)
from app.pms.items.routers.item_aggregate import router as item_aggregate_router
from app.pms.items.routers.item_barcodes import router as item_barcodes_router
from app.pms.items.routers.item_list import router as item_list_router
from app.pms.items.routers.item_master import router as item_master_router
from app.pms.items.routers.item_sku_codes import router as item_sku_codes_router
from app.pms.items.routers.item_uoms import router as item_uoms_router
from app.pms.items.routers.items import router as items_router
from app.pms.sku_coding.routers.sku_coding import router as sku_coding_router


def mount_pms_routers(app: FastAPI) -> None:
    """
    Mount PMS standalone process routes.

    Keep export/read routes before owner /items routes to avoid path-order
    surprises. Do not add WMS / OMS / Procurement / Finance / Shipping routes
    here.
    """

    # Cross-domain read/export surface for WMS / OMS / Procurement / Finance.
    app.include_router(pms_export_items_read_router)
    app.include_router(pms_export_uoms_read_router)
    app.include_router(pms_export_sku_codes_read_router)
    app.include_router(pms_export_barcodes_read_router)
    app.include_router(pms_export_barcode_probe_router)
    app.include_router(partners_export_suppliers_read_router)

    # PMS owner/master-data surface for pms-web.
    app.include_router(item_aggregate_router)
    app.include_router(item_list_router)
    app.include_router(items_router)
    app.include_router(item_master_router)
    app.include_router(item_sku_codes_router)
    app.include_router(sku_coding_router)
    app.include_router(item_barcodes_router)
    app.include_router(item_uoms_router)

    # Supplier master data is currently still under app.partners but is required
    # by PMS item ownership through supplier_id. This mount is intentional for
    # the first standalone PMS process; later we can re-home the module.
    app.include_router(suppliers_router)
    app.include_router(supplier_contacts_router)
