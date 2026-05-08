
from __future__ import annotations

from pathlib import Path


def test_shipping_assist_handoffs_ready_requires_complete_outbound_fact() -> None:
    source = Path("app/shipping_assist/handoffs/repository_ready.py").read_text()

    assert '"p.outbound_event_id IS NOT NULL"' in source
    assert (
        '"NULLIF(BTRIM(COALESCE(p.outbound_source_ref, \'\')), \'\') IS NOT NULL"'
        in source
    )
    assert '"p.outbound_completed_at IS NOT NULL"' in source
    assert '"jsonb_array_length(p.shipment_items) > 0"' in source

    assert '"NULLIF(BTRIM(COALESCE(p.receiver_name, \'\')), \'\') IS NOT NULL"' in source
    assert '"NULLIF(BTRIM(COALESCE(p.receiver_phone, \'\')), \'\') IS NOT NULL"' in source
    assert '"NULLIF(BTRIM(COALESCE(p.receiver_province, \'\')), \'\') IS NOT NULL"' in source
    assert '"NULLIF(BTRIM(COALESCE(p.receiver_city, \'\')), \'\') IS NOT NULL"' in source
    assert '"NULLIF(BTRIM(COALESCE(p.receiver_address, \'\')), \'\') IS NOT NULL"' in source
