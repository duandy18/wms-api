# app/integrations/pms/inprocess_client.py
"""
In-process PMS read client.

Current deployment mode:
- PMS lives in the same wms-api codebase/process.
- This client delegates to app.pms.export services.
- Non-PMS domains should call this integration client, not app.pms.export
  services directly.

Future deployment mode:
- Replace this implementation with an HTTP PMS client behind the same
  PmsReadClient protocol.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pms.contracts import (
    BarcodeProbeOut,
    ItemBasic,
    ItemPolicy,
    ItemReadQuery,
    PmsExportBarcode,
    PmsExportSkuCode,
    PmsExportSkuCodeResolution,
    PmsExportUom,
)
from app.pms.export.barcodes.services.barcode_read_service import (
    PmsExportBarcodeReadService,
)
from app.pms.export.items.services.barcode_probe_service import BarcodeProbeService
from app.pms.export.items.services.item_read_service import ItemReadService
from app.pms.export.sku_codes.services.sku_code_read_service import (
    PmsExportSkuCodeReadService,
)
from app.pms.export.uoms.services.uom_read_service import PmsExportUomReadService



def _contract_data(value):
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="python")
    return value


def _contract_model(model_type, value):
    if value is None:
        return None
    validator = getattr(model_type, "model_validate", None)
    if callable(validator):
        return validator(_contract_data(value))
    return model_type(**_contract_data(value))


class InProcessPmsReadClient:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_item_basics(
        self,
        *,
        query: ItemReadQuery | None = None,
    ) -> list[ItemBasic]:
        return await ItemReadService(self.session).alist_basic(query=query)

    async def get_item_basic(self, *, item_id: int) -> ItemBasic | None:
        return await ItemReadService(self.session).aget_basic_by_id(item_id=int(item_id))

    async def get_item_basics(
        self,
        *,
        item_ids: Iterable[int],
    ) -> dict[int, ItemBasic]:
        return await ItemReadService(self.session).aget_basics_by_item_ids(item_ids=item_ids)

    async def get_item_policy(self, *, item_id: int) -> ItemPolicy | None:
        return await ItemReadService(self.session).aget_policy_by_id(item_id=int(item_id))

    async def get_item_policies(
        self,
        *,
        item_ids: Iterable[int],
    ) -> dict[int, ItemPolicy]:
        return await ItemReadService(self.session).aget_policies_by_item_ids(item_ids=item_ids)

    async def get_item_policy_by_sku(self, *, sku: str) -> ItemPolicy | None:
        return await ItemReadService(self.session).aget_policy_by_sku(sku=str(sku))

    async def search_report_item_ids_by_keyword(
        self,
        *,
        keyword: str,
        limit: int | None = None,
    ) -> list[int]:
        return await ItemReadService(self.session).asearch_report_item_ids_by_keyword(
            keyword=str(keyword),
            limit=limit,
        )

    async def get_report_meta_by_item_ids(
        self,
        *,
        item_ids: Iterable[int],
    ) -> dict[int, object]:
        return await ItemReadService(self.session).aget_report_meta_by_item_ids(
            item_ids=item_ids,
        )

    async def get_uom(self, *, item_uom_id: int) -> PmsExportUom | None:
        return await PmsExportUomReadService(self.session).aget_by_id(
            item_uom_id=int(item_uom_id),
        )

    async def list_uoms(
        self,
        *,
        item_ids: Sequence[int] | None = None,
        item_uom_ids: Sequence[int] | None = None,
    ) -> list[PmsExportUom]:
        return await PmsExportUomReadService(self.session).alist_uoms(
            item_ids=item_ids,
            item_uom_ids=item_uom_ids,
        )

    async def list_uoms_by_item_id(self, *, item_id: int) -> list[PmsExportUom]:
        return await PmsExportUomReadService(self.session).alist_by_item_id(
            item_id=int(item_id),
        )

    async def get_purchase_default_or_base_uom(
        self,
        *,
        item_id: int,
    ) -> PmsExportUom | None:
        return await PmsExportUomReadService(self.session).aget_purchase_default_or_base(
            item_id=int(item_id),
        )

    async def get_inbound_default_or_base_uom(
        self,
        *,
        item_id: int,
    ) -> PmsExportUom | None:
        return await PmsExportUomReadService(self.session).aget_inbound_default_or_base(
            item_id=int(item_id),
        )

    async def get_outbound_default_or_base_uom(
        self,
        *,
        item_id: int,
    ) -> PmsExportUom | None:
        return await PmsExportUomReadService(self.session).aget_outbound_default_or_base(
            item_id=int(item_id),
        )

    async def get_barcode(self, *, barcode_id: int) -> PmsExportBarcode | None:
        return await PmsExportBarcodeReadService(self.session).aget_by_id(
            barcode_id=int(barcode_id),
        )

    async def list_barcodes(
        self,
        *,
        item_ids: Sequence[int] | None = None,
        item_uom_ids: Sequence[int] | None = None,
        barcode: str | None = None,
        active: bool | None = None,
        primary_only: bool = False,
    ) -> list[PmsExportBarcode]:
        return await PmsExportBarcodeReadService(self.session).alist_barcodes(
            item_ids=item_ids,
            item_uom_ids=item_uom_ids,
            barcode=barcode,
            active=active,
            primary_only=primary_only,
        )

    async def list_barcodes_by_item_id(
        self,
        *,
        item_id: int,
        active: bool | None = True,
        primary_only: bool = False,
    ) -> list[PmsExportBarcode]:
        return await PmsExportBarcodeReadService(self.session).alist_by_item_id(
            item_id=int(item_id),
            active=active,
            primary_only=primary_only,
        )

    async def probe_barcode(self, *, barcode: str) -> BarcodeProbeOut:
        probe = await BarcodeProbeService(self.session).aprobe(barcode=barcode)
        return _contract_model(BarcodeProbeOut, probe)

    async def get_sku_code(self, *, sku_code_id: int) -> PmsExportSkuCode | None:
        return await PmsExportSkuCodeReadService(self.session).aget_by_id(
            sku_code_id=int(sku_code_id),
        )

    async def list_sku_codes(
        self,
        *,
        item_ids: Sequence[int] | None = None,
        sku_code_ids: Sequence[int] | None = None,
        code: str | None = None,
        active: bool | None = None,
        primary_only: bool = False,
    ) -> list[PmsExportSkuCode]:
        return await PmsExportSkuCodeReadService(self.session).alist_sku_codes(
            item_ids=item_ids,
            sku_code_ids=sku_code_ids,
            code=code,
            active=active,
            primary_only=primary_only,
        )

    async def list_sku_codes_by_item_id(
        self,
        *,
        item_id: int,
        active: bool | None = True,
        primary_only: bool = False,
    ) -> list[PmsExportSkuCode]:
        return await PmsExportSkuCodeReadService(self.session).alist_by_item_id(
            item_id=int(item_id),
            active=active,
            primary_only=primary_only,
        )

    async def resolve_active_code_for_outbound_default(
        self,
        *,
        code: str,
        enabled_only: bool = True,
    ) -> PmsExportSkuCodeResolution | None:
        return await PmsExportSkuCodeReadService(
            self.session
        ).aresolve_active_code_for_outbound_default(
            code=str(code),
            enabled_only=bool(enabled_only),
        )


__all__ = ["InProcessPmsReadClient"]
