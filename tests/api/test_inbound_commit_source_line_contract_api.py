from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.wms.inbound.contracts.inbound_commit import InboundCommitIn, InboundCommitLineIn


def test_purchase_inbound_commit_line_uses_source_line_id() -> None:
    line = InboundCommitLineIn.model_validate(
        {
            "item_id": 3001,
            "uom_id": 11,
            "qty_input": 2,
            "source_line_id": 7001,
        }
    )

    assert line.source_line_id == 7001


def test_purchase_inbound_commit_line_rejects_po_line_id_alias() -> None:
    with pytest.raises(ValidationError):
        InboundCommitLineIn.model_validate(
            {
                "item_id": 3001,
                "uom_id": 11,
                "qty_input": 2,
                "po_line_id": 7001,
            }
        )


def test_purchase_inbound_commit_requires_source_line_id_for_purchase_source() -> None:
    with pytest.raises(ValidationError):
        InboundCommitIn.model_validate(
            {
                "warehouse_id": 1,
                "source_type": "PURCHASE_ORDER",
                "source_ref": "PO-1",
                "occurred_at": datetime.now(UTC).isoformat(),
                "lines": [
                    {
                        "item_id": 3001,
                        "uom_id": 11,
                        "qty_input": 2,
                    }
                ],
            }
        )


def test_manual_inbound_commit_does_not_require_source_line_id() -> None:
    payload = InboundCommitIn.model_validate(
        {
            "warehouse_id": 1,
            "source_type": "MANUAL",
            "source_ref": None,
            "occurred_at": datetime.now(UTC).isoformat(),
            "lines": [
                {
                    "item_id": 3001,
                    "uom_id": 11,
                    "qty_input": 2,
                }
            ],
        }
    )

    assert payload.lines[0].source_line_id is None
