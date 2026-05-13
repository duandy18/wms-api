from __future__ import annotations

from pathlib import Path


def test_inbound_commit_service_does_not_import_local_procurement_completion_sync() -> None:
    text = Path("app/wms/inbound/services/inbound_commit_service.py").read_text(
        encoding="utf-8"
    )

    assert "purchase_order_completion_sync" not in text
    assert "sync_purchase_completion_for_inbound_event" not in text
