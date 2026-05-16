from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from app.integrations.procurement.contracts import (
    ProcurementPurchaseOrderOut,
    ProcurementPurchaseOrderSourceOptionsOut,
)
from app.integrations.procurement.wms_procurement_service_auth import (
    wms_to_procurement_service_auth_headers,
)


class ProcurementReadClientError(RuntimeError):
    pass


class HttpProcurementReadClient:
    """HTTP client for procurement-api read-v1 contracts.

    边界说明：
    - WMS 只读取 procurement-api read API。
    - 本 client 不写 procurement owner 数据。
    - 本 client 不创建 WMS 入库单。
    - 本 client 统一以 wms-service 身份调用 Procurement。
    - 采购入库来源必须使用 procurement-api 暴露给 WMS 的 receiving-sources 合同，
      不再绑定采购管理页面的 purchase-orders 读模型路径。
    """

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        normalized = (base_url or "").strip().rstrip("/")
        if not normalized:
            raise ValueError("procurement base_url is required")

        self._base_url = normalized
        self._timeout_seconds = float(timeout_seconds)
        self._transport = transport
        self._headers = wms_to_procurement_service_auth_headers(headers)

    async def list_purchase_order_source_options(
        self,
        *,
        target_warehouse_id: int | None = None,
        q: str | None = None,
        limit: int = 200,
    ) -> ProcurementPurchaseOrderSourceOptionsOut:
        params: dict[str, str] = {"limit": str(int(limit))}

        if target_warehouse_id is not None:
            params["target_warehouse_id"] = str(int(target_warehouse_id))

        if q is not None and q.strip():
            params["q"] = q.strip()

        payload = await self._get_json(
            "/procurement/read/v1/wms/receiving-sources",
            params=params,
        )

        return ProcurementPurchaseOrderSourceOptionsOut.model_validate(payload)

    async def get_purchase_order(self, po_id: int) -> ProcurementPurchaseOrderOut:
        payload = await self._get_json(
            f"/procurement/read/v1/wms/receiving-sources/{int(po_id)}",
            params=None,
        )

        return ProcurementPurchaseOrderOut.model_validate(payload)

    async def _get_json(
        self,
        path: str,
        *,
        params: dict[str, str] | None,
    ) -> Any:
        url = f"{self._base_url}{path}"

        async with httpx.AsyncClient(
            transport=self._transport,
            headers=self._headers,
            timeout=httpx.Timeout(self._timeout_seconds),
        ) as client:
            response = await client.get(url, params=params)

        if response.status_code >= 400:
            raise ProcurementReadClientError(
                f"procurement read request failed: status={response.status_code}, path={path}"
            )

        return response.json()
