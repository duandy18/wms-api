# app/integrations/pms/client.py
"""
PMS read client protocol.

This is the consumer-side PMS boundary. WMS / OMS / Procurement / Finance
must depend on this protocol instead of importing PMS owner/export
services directly.

No fallback policy belongs here:
- current implementation: HttpPmsReadClient
- future implementation: HttpPmsReadClient
- one deployment must choose one implementation explicitly
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol

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


class PmsReadClient(Protocol):
    async def list_item_basics(
        self,
        *,
        query: ItemReadQuery | None = None,
    ) -> list[ItemBasic]:
        ...

    async def get_item_basic(self, *, item_id: int) -> ItemBasic | None:
        ...

    async def get_item_basics(
        self,
        *,
        item_ids: Iterable[int],
    ) -> dict[int, ItemBasic]:
        ...

    async def get_item_policy(self, *, item_id: int) -> ItemPolicy | None:
        ...

    async def get_item_policies(
        self,
        *,
        item_ids: Iterable[int],
    ) -> dict[int, ItemPolicy]:
        ...

    async def get_item_policy_by_sku(self, *, sku: str) -> ItemPolicy | None:
        ...

    async def search_report_item_ids_by_keyword(
        self,
        *,
        keyword: str,
        limit: int | None = None,
    ) -> list[int]:
        ...

    async def get_report_meta_by_item_ids(
        self,
        *,
        item_ids: Iterable[int],
    ) -> dict[int, object]:
        ...

    async def get_uom(self, *, item_uom_id: int) -> PmsExportUom | None:
        ...

    async def list_uoms(
        self,
        *,
        item_ids: Sequence[int] | None = None,
        item_uom_ids: Sequence[int] | None = None,
    ) -> list[PmsExportUom]:
        ...

    async def list_uoms_by_item_id(self, *, item_id: int) -> list[PmsExportUom]:
        ...

    async def get_purchase_default_or_base_uom(
        self,
        *,
        item_id: int,
    ) -> PmsExportUom | None:
        ...

    async def get_inbound_default_or_base_uom(
        self,
        *,
        item_id: int,
    ) -> PmsExportUom | None:
        ...

    async def get_outbound_default_or_base_uom(
        self,
        *,
        item_id: int,
    ) -> PmsExportUom | None:
        ...

    async def get_barcode(self, *, barcode_id: int) -> PmsExportBarcode | None:
        ...

    async def list_barcodes(
        self,
        *,
        item_ids: Sequence[int] | None = None,
        item_uom_ids: Sequence[int] | None = None,
        barcode: str | None = None,
        active: bool | None = None,
        primary_only: bool = False,
    ) -> list[PmsExportBarcode]:
        ...

    async def list_barcodes_by_item_id(
        self,
        *,
        item_id: int,
        active: bool | None = True,
        primary_only: bool = False,
    ) -> list[PmsExportBarcode]:
        ...

    async def probe_barcode(self, *, barcode: str) -> BarcodeProbeOut:
        ...

    async def get_sku_code(self, *, sku_code_id: int) -> PmsExportSkuCode | None:
        ...

    async def list_sku_codes(
        self,
        *,
        item_ids: Sequence[int] | None = None,
        sku_code_ids: Sequence[int] | None = None,
        code: str | None = None,
        active: bool | None = None,
        primary_only: bool = False,
    ) -> list[PmsExportSkuCode]:
        ...

    async def list_sku_codes_by_item_id(
        self,
        *,
        item_id: int,
        active: bool | None = True,
        primary_only: bool = False,
    ) -> list[PmsExportSkuCode]:
        ...

    async def resolve_active_code_for_outbound_default(
        self,
        *,
        code: str,
        enabled_only: bool = True,
    ) -> PmsExportSkuCodeResolution | None:
        ...
