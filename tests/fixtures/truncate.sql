-- tests/fixtures/truncate.sql
-- 说明：
-- - 每个 test function 开始前清库
-- - 目标：可重复、无脏数据累积
-- - 注意：这里会清掉主数据（items/warehouses）与运费域（shipping_*）以及库存/台账事实
--
-- Phase 4E：
-- - stocks / batches 已退场并在预演中 rename 为 *_legacy；
-- - tests 清库不再触碰 legacy 表，避免 drop 后脚本再次炸裂。
--
-- Pricing Phase-3：
-- - shipping_provider_pricing_scheme_modules 已退场；
-- - 新主线改为 ranges + pricing_matrix(cellized)。
--
-- Pricing Phase-surcharge-config：
-- - surcharge 主线已切到 surcharge_configs + surcharge_config_cities；
-- - tests 清库不再触碰 shipping_provider_surcharges 旧表。
--
-- PMS Split Stabilization：
-- - PMS owner 真相已拆到 pms-api / pms DB；
-- - WMS 测试里 wms_pms_*_projection 是 PMS current-state 测试投影；
-- - projection 表必须每个 test function 清空，禁止跨用例残留。

TRUNCATE TABLE
  -- PMS read projections
  wms_pms_barcode_projection,
  wms_pms_sku_code_projection,
  wms_pms_uom_projection,
  wms_pms_item_projection,

  -- platform order ingestion jobs
  -- finance facts
  finance_order_sales_lines,
  finance_shipping_cost_lines,
  finance_purchase_price_ledger_lines,

  -- orders / order_items
  order_items,
  orders,

  -- stock / ledger / snapshots
  stock_ledger,
  stock_snapshots,

  -- outbound commits
  outbound_commits,

  -- store_items
  store_items,

  -- errors
  event_error_log,

  -- ===== shipping domain（避免每用例累积脏数据）=====
  wms_logistics_handoff_payloads,
  wms_logistics_export_records,
  shipping_records,
  shipping_providers,

  -- master data
  warehouses,
  items
RESTART IDENTITY CASCADE;
