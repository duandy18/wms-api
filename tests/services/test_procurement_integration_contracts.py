from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.integrations.procurement.contracts import ProcurementPurchaseOrderOut


def _purchase_order_payload() -> dict[str, object]:
    now = datetime(2026, 5, 15, tzinfo=UTC)

    return {
        "id": 4,
        "po_no": "PO-20260515045356-70E169",
        "supplier_id": 3,
        "supplier_code_snapshot": "SU-001",
        "supplier_name_snapshot": "北京清淼源工程咨询有限公司",
        "target_warehouse_id": 1,
        "target_warehouse_code_snapshot": "WH-1",
        "target_warehouse_name_snapshot": "河北省固安第一仓库",
        "purchaser": "Andy",
        "purchase_time": now,
        "status": "CREATED",
        "total_amount": "1980.00",
        "remark": None,
        "created_at": now,
        "updated_at": now,
        "closed_at": None,
        "canceled_at": None,
        "editable": False,
        "edit_block_reason": None,
        "total_ordered_base": 165,
        "total_received_base": 0,
        "total_remaining_base": 165,
        "completion_status": "NOT_RECEIVED",
        "last_received_at": None,
        "lines": [],
    }


def test_procurement_purchase_order_out_accepts_completion_summary_fields() -> None:
    out = ProcurementPurchaseOrderOut.model_validate(_purchase_order_payload())

    assert out.id == 4
    assert out.total_ordered_base == 165
    assert out.total_received_base == 0
    assert out.total_remaining_base == 165
    assert out.completion_status == "NOT_RECEIVED"
    assert out.last_received_at is None


def test_procurement_purchase_order_out_still_forbids_unknown_fields() -> None:
    payload = _purchase_order_payload()
    payload["unknown_field"] = "must fail"

    with pytest.raises(ValidationError):
        ProcurementPurchaseOrderOut.model_validate(payload)
