# tests/ci/test_wms_oms_fulfillment_projection_sync_boundary.py
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


FORBIDDEN_OWNER_SQL_RE = re.compile(
    r"\bFROM\s+(orders|order_lines|oms_fskus|oms_fsku_components|platform_code_fsku_mappings)\b"
    r"|\bJOIN\s+(orders|order_lines|oms_fskus|oms_fsku_components|platform_code_fsku_mappings)\b",
    re.IGNORECASE,
)


def test_oms_fulfillment_projection_sync_uses_read_v1_endpoint_only() -> None:
    text = (ROOT / "app/integrations/oms/projection_sync.py").read_text(encoding="utf-8")

    assert "/oms/read/v1/fulfillment-ready-orders" in text
    assert "/oms/fskus" not in text
    assert "/oms/platform-code-mappings" not in text
    assert "/collector" not in text


def test_oms_fulfillment_projection_sync_does_not_read_owner_tables_directly() -> None:
    text = (ROOT / "app/integrations/oms/projection_sync.py").read_text(encoding="utf-8")

    assert FORBIDDEN_OWNER_SQL_RE.search(text) is None
    assert "from app.oms" not in text


def test_oms_fulfillment_projection_sync_writes_projection_tables_only() -> None:
    text = (ROOT / "app/integrations/oms/projection_sync.py").read_text(encoding="utf-8")

    assert "INSERT INTO wms_oms_fulfillment_order_projection" in text
    assert "INSERT INTO wms_oms_fulfillment_line_projection" in text
    assert "INSERT INTO wms_oms_fulfillment_component_projection" in text

    assert "INSERT INTO orders" not in text
    assert "INSERT INTO order_lines" not in text
    assert "wms_logistics_" not in text
    assert "outbound_event" not in text
    assert "wms_pms_" not in text


def test_oms_fulfillment_projection_sync_has_local_make_target_and_token_contract() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    test_mk = (ROOT / "scripts/make/test.mk").read_text(encoding="utf-8")

    assert "OMS_API_TOKEN ?=" in makefile
    assert 'OMS_API_TOKEN="$(OMS_API_TOKEN)"' in makefile
    assert "OMS_API_TOKEN=" in env_example
    assert "oms-fulfillment-projection-sync" in test_mk
    assert "scripts/oms/sync_fulfillment_projection.py" in test_mk
