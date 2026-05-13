# tests/ci/test_wms_oms_legacy_source_retired.py
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


RETIRED_PATHS = (
    "app/oms/contracts/platform_orders_confirm_create.py",
    "app/oms/contracts/platform_orders_ingest.py",
    "app/oms/contracts/platform_orders_manual_decisions.py",
    "app/oms/contracts/platform_orders_replay.py",
    "app/oms/contracts/platform_orders_resolve_preview.py",
    "app/oms/contracts/stores_order_sim.py",
    "app/oms/contracts/stores.py",
    "app/oms/deps/stores_order_sim_gate.py",
    "app/oms/deps/stores_order_sim_testset_guard.py",
    "app/oms/fsku/contracts",
    "app/oms/fsku/router.py",
    "app/oms/fsku/router_platform_code_mappings.py",
    "app/oms/fsku/routers",
    "app/oms/fsku/services",
    "app/oms/order_facts/contracts",
    "app/oms/order_facts/router.py",
    "app/oms/order_facts/router_code_mapping.py",
    "app/oms/order_facts/router_order_sku_resolution.py",
    "app/oms/order_facts/router_platform_order_mirrors.py",
    "app/oms/order_facts/services",
    "app/oms/repos/platform_order_fact_service.py",
    "app/oms/repos/platform_orders_fact.py",
    "app/oms/repos/stores_order_sim.py",
    "app/oms/repos/stores_order_sim_bindings.py",
    "app/oms/routers/platform_orders_confirm_create.py",
    "app/oms/routers/platform_orders_ingest_routes.py",
    "app/oms/routers/platform_orders_manual_decisions.py",
    "app/oms/routers/platform_orders_replay.py",
    "app/oms/routers/platform_orders_resolve_preview.py",
    "app/oms/routers/stores.py",
    "app/oms/routers/stores_bindings_read.py",
    "app/oms/routers/stores_bindings_write.py",
    "app/oms/routers/stores_crud.py",
    "app/oms/routers/stores_order_sim.py",
    "app/oms/routers/stores_order_sim_cart.py",
    "app/oms/routers/stores_order_sim_generate.py",
    "app/oms/routers/stores_order_sim_merchant_lines.py",
    "app/oms/routers/stores_routing.py",
)


def test_wms_legacy_oms_runtime_source_files_are_removed() -> None:
    existing = [path for path in RETIRED_PATHS if (ROOT / path).exists()]
    assert existing == []


def test_wms_oms_keeps_projection_and_known_model_boundaries() -> None:
    assert (ROOT / "app/oms/router.py").is_file()
    assert (ROOT / "app/oms/fulfillment_projection").is_dir()
    assert (ROOT / "app/integrations/oms").is_dir()

    # Kept intentionally until the schema-drop/cross-module cleanup phase.
    assert (ROOT / "app/oms/orders").is_dir()
    assert (ROOT / "app/oms/stores/models").is_dir()
