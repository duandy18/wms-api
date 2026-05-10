# app/integrations/pms/contracts.py
"""
PMS integration contracts.

Temporary in-repo bridge:
- The source of truth is still app.pms.export contracts.
- Non-PMS domains should import these contracts from app.integrations.pms.
- When PMS becomes an independent service/repo, this file is the cutover point
  to generated SDK/OpenAPI contracts.
"""

from app.pms.export.barcodes.contracts.barcode import PmsExportBarcode
from app.pms.export.items.contracts.barcode_probe import (
    BarcodeProbeError,
    BarcodeProbeIn,
    BarcodeProbeOut,
    BarcodeProbeStatus,
)
from app.pms.export.items.contracts.item_basic import ItemBasic
from app.pms.export.items.contracts.item_policy import (
    ExpiryPolicy,
    ItemPolicy,
    LotSourcePolicy,
    ShelfLifeUnit,
)
from app.pms.export.items.contracts.item_query import ItemReadQuery
from app.pms.export.sku_codes.contracts.sku_code import (
    PmsExportSkuCode,
    PmsExportSkuCodeResolution,
)
from app.pms.export.uoms.contracts.uom import PmsExportUom

__all__ = [
    "BarcodeProbeError",
    "BarcodeProbeIn",
    "BarcodeProbeOut",
    "BarcodeProbeStatus",
    "ExpiryPolicy",
    "ItemBasic",
    "ItemPolicy",
    "ItemReadQuery",
    "LotSourcePolicy",
    "PmsExportBarcode",
    "PmsExportSkuCode",
    "PmsExportSkuCodeResolution",
    "PmsExportUom",
    "ShelfLifeUnit",
]
