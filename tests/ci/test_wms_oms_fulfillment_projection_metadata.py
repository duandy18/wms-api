from __future__ import annotations

from pathlib import Path

from app.db.base import Base, init_models

ROOT = Path(__file__).resolve().parents[2]


def test_wms_oms_fulfillment_projection_models_are_registered() -> None:
    init_models(force=True)

    expected = {
        "wms_oms_fulfillment_order_projection",
        "wms_oms_fulfillment_line_projection",
        "wms_oms_fulfillment_component_projection",
        "wms_oms_fulfillment_projection_sync_runs",
    }

    assert expected <= set(Base.metadata.tables)


def test_wms_oms_fulfillment_projection_uses_wms_owned_table_names() -> None:
    text = (ROOT / "app/integrations/oms/projection_models.py").read_text(encoding="utf-8")

    assert "wms_oms_fulfillment_order_projection" in text
    assert "wms_oms_fulfillment_line_projection" in text
    assert "wms_oms_fulfillment_component_projection" in text
    assert "wms_oms_fulfillment_projection_sync_runs" in text

    assert '__tablename__ = "oms_' not in text
    assert "from app.oms" not in text


def test_wms_local_env_contract_includes_oms_api_base_url() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    env_mk = (ROOT / "scripts/make/env.mk").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "OMS_API_BASE_URL ?= http://127.0.0.1:8010" in makefile
    assert 'OMS_API_BASE_URL="$(OMS_API_BASE_URL)"' in makefile
    assert 'export OMS_API_BASE_URL="$(OMS_API_BASE_URL)"' in env_mk
    assert "$(OMS_API_BASE_URL)/openapi.json" in env_mk
    assert "OMS_API_BASE_URL=http://127.0.0.1:8010" in env_example


def test_wms_oms_projection_has_no_cross_system_foreign_keys() -> None:
    text = (ROOT / "app/integrations/oms/projection_models.py").read_text(encoding="utf-8")

    assert "oms_fskus" not in text
    assert "oms_orders" not in text
    assert "orders.id" not in text
    assert "order_lines.id" not in text
    assert "wms_pms_" not in text
