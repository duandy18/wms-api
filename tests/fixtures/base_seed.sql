-- tests/fixtures/base_seed.sql
-- Lot-World baseline (v2)
-- - supplier lots keyed by lot_code_key
-- - internal lots are singleton per (warehouse_id,item_id)
--
-- Phase M-5 收口约定（工程级）：
-- ✅ base_seed.sql 只负责非 PMS owner 测试基线：
--    - warehouses
--    - stores / platform_test_stores
--    - suppliers
--    - shipping_providers
--    - inbound_receipts placeholder
-- ❌ 禁止在 baseline 中写入任何库存事实：
--    - lots
--    - stocks_lot
--    - stock_ledger
--    - stock_snapshots
--
-- PMS legacy baseline 去 owner 化第四刀说明：
-- - PMS owner 真相已拆到 pms-api / PMS DB。
-- - WMS 测试 baseline 不再写旧 PMS owner seed。
-- - WMS 测试需要 PMS current-state 时，只能使用 tests/fixtures/pms_projection_seed.sql
--   构造 wms_pms_*_projection。
--
-- 库存/lot 事实必须在 tests 中显式通过统一入口构造：
--   - ensure_lot_full / ensure_internal_lot_singleton
--   - adjust_lot_impl / lot-only stock write primitives
--   - tests/helpers/inventory.py: seed_supplier_lot_slot 等

-- ===== warehouses =====
INSERT INTO warehouses (id, name, code)
VALUES (1, 'WH-1', 'WH-1')
ON CONFLICT (id) DO NOTHING;

-- ===== stores (TEST gate baseline) =====
INSERT INTO stores (
  id,
  platform,
  store_code,
  store_name,
  active,
  route_mode
)
VALUES (
  9001,
  'PDD',
  'UT-TEST-STORE-1',
  'UT-TEST-STORE-1',
  true,
  'FALLBACK'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO platform_test_stores (platform, store_code, store_id, code)
VALUES ('PDD', 'UT-TEST-STORE-1', 9001, 'DEFAULT')
ON CONFLICT (platform, code)
DO UPDATE SET store_code = EXCLUDED.store_code, store_id = EXCLUDED.store_id;

-- ===== suppliers (WMS / procurement side baseline) =====
INSERT INTO suppliers (id, name, code, active)
VALUES
  (1, 'UT-SUP-1', 'UT-SUP-1', true),
  (3, 'UT-SUP-3', 'UT-SUP-3', true)
ON CONFLICT (id) DO NOTHING;

-- ===== shipping_providers (minimal) =====
INSERT INTO shipping_providers (id, name, shipping_provider_code, active, priority, address)
VALUES
  (1, 'UT-CARRIER-1', 'UT-CAR-1', true, 100, 'UT-ADDR-1'),
  (2, 'Fake Express', 'FAKE', true, 100, 'UT-ADDR-FAKE')
ON CONFLICT (id) DO NOTHING;

-- ===== inbound_receipts (compat placeholder) =====
-- 注意：当前 INTERNAL lot 的终态 identity 不应依赖 inbound_receipts。
-- 但某些历史路径/测试可能仍假设有一条 receipt seed，因此保留这条 placeholder。
-- 新任务模型下，这条 seed 只作为“手工来源的已发布任务单占位”，不再使用旧事实层列。
INSERT INTO inbound_receipts (
  id,
  warehouse_id,
  supplier_id,
  counterparty_name_snapshot,
  source_type,
  source_doc_id,
  source_doc_no_snapshot,
  receipt_no,
  status,
  remark,
  created_at,
  updated_at,
  warehouse_name_snapshot,
  created_by,
  released_at
)
VALUES
  (
    9000001,
    1,
    NULL,
    NULL,
    'MANUAL',
    NULL,
    NULL,
    'UT-INTERNAL-LOT-SEED-9000001',
    'RELEASED',
    'seed placeholder',
    now(),
    now(),
    'WH-1',
    NULL,
    now()
  )
ON CONFLICT (id) DO NOTHING;

-- ===== sequences =====
SELECT setval(
  pg_get_serial_sequence('warehouses','id'),
  COALESCE((SELECT MAX(id) FROM warehouses), 0),
  true
);

SELECT setval(
  pg_get_serial_sequence('stores','id'),
  COALESCE((SELECT MAX(id) FROM stores), 0),
  true
);

SELECT setval(
  pg_get_serial_sequence('shipping_providers','id'),
  COALESCE((SELECT MAX(id) FROM shipping_providers), 0),
  true
);
