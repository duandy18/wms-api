-- tests/fixtures/base_seed.sql
-- Lot-World baseline (v2)
-- - supplier lots keyed by lot_code_key
-- - internal lots are singleton per (warehouse_id,item_id)
--
-- Phase M-5 收口约定（工程级）：
-- ✅ base_seed.sql 只负责“主数据种子”（master data）
-- ❌ 禁止在 baseline 中写入任何库存事实：
--    - lots
--    - stocks_lot
--    - stock_ledger
--    - stock_snapshots
--
-- 库存/lot 事实必须在 tests 中显式通过统一入口构造：
--   - ensure_lot_full / ensure_internal_lot_singleton
--   - adjust_lot_impl / lot-only stock write primitives
--   - tests/helpers/inventory.py: seed_supplier_lot_slot 等
--
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

-- ===== suppliers (minimal) =====

-- ===== pms master data brands / categories =====
INSERT INTO pms_brands (
  id,
  name_cn,
  code,
  is_active,
  is_locked,
  sort_order,
  remark,
  created_at,
  updated_at
)
VALUES
  (1, 'BRAND-A', 'BRANDA', TRUE, FALSE, 10, 'base seed brand A', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  (2, 'BRAND-B', 'BRANDB', TRUE, FALSE, 20, 'base seed brand B', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (id) DO UPDATE SET
  name_cn = EXCLUDED.name_cn,
  code = EXCLUDED.code,
  is_active = EXCLUDED.is_active,
  updated_at = CURRENT_TIMESTAMP;

SELECT setval(
  pg_get_serial_sequence('pms_brands', 'id'),
  GREATEST((SELECT COALESCE(MAX(id), 1) FROM pms_brands), 1),
  TRUE
);

INSERT INTO pms_business_categories (
  id,
  parent_id,
  level,
  product_kind,
  category_name,
  category_code,
  path_code,
  is_leaf,
  is_active,
  is_locked,
  sort_order,
  remark,
  created_at,
  updated_at
)
VALUES
  (1, NULL, 1, 'OTHER', 'CATEGORY-A', 'CATA', 'CATA', TRUE, TRUE, FALSE, 10, 'base seed category A', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  (2, NULL, 1, 'OTHER', 'CATEGORY-B', 'CATB', 'CATB', TRUE, TRUE, FALSE, 20, 'base seed category B', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (id) DO UPDATE SET
  category_name = EXCLUDED.category_name,
  category_code = EXCLUDED.category_code,
  path_code = EXCLUDED.path_code,
  product_kind = EXCLUDED.product_kind,
  is_leaf = EXCLUDED.is_leaf,
  is_active = EXCLUDED.is_active,
  updated_at = CURRENT_TIMESTAMP;

SELECT setval(
  pg_get_serial_sequence('pms_business_categories', 'id'),
  GREATEST((SELECT COALESCE(MAX(id), 1) FROM pms_business_categories), 1),
  TRUE
);

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


-- ===== items =====
INSERT INTO items (
  id, sku, name,
  brand_id, category_id,
  lot_source_policy, expiry_policy, derivation_allowed, uom_governance_enabled
)
VALUES
  (1,    'SKU-0001', 'UT-ITEM-1',
   1, 1,
   'SUPPLIER_ONLY'::lot_source_policy, 'NONE'::expiry_policy, true, true),
  (3001, 'SKU-3001', 'SOFT-PICK-1',
   1, 1,
   'SUPPLIER_ONLY'::lot_source_policy, 'NONE'::expiry_policy, true, true),
  (3002, 'SKU-3002', 'SOFT-PICK-2',
   1, 1,
   'SUPPLIER_ONLY'::lot_source_policy, 'NONE'::expiry_policy, true, true),
  (3003, 'SKU-3003', 'SOFT-PICK-BASE',
   1, 1,
   'SUPPLIER_ONLY'::lot_source_policy, 'NONE'::expiry_policy, true, true),
  (4001, 'SKU-4001', 'OUTBOUND-MERGE',
   1, 1,
   'SUPPLIER_ONLY'::lot_source_policy, 'NONE'::expiry_policy, true, true),
  (4002, 'SKU-4002', 'PURCHASE-BASE-1',
   1, 1,
   'SUPPLIER_ONLY'::lot_source_policy, 'NONE'::expiry_policy, true, true)
ON CONFLICT (id) DO UPDATE SET
  sku = EXCLUDED.sku,
  name = EXCLUDED.name,
  brand_id = EXCLUDED.brand_id,
  category_id = EXCLUDED.category_id,
  lot_source_policy = EXCLUDED.lot_source_policy,
  expiry_policy = EXCLUDED.expiry_policy,
  derivation_allowed = EXCLUDED.derivation_allowed,
  uom_governance_enabled = EXCLUDED.uom_governance_enabled;


-- ===== item_sku_codes (SKU governance truth) =====
UPDATE item_sku_codes c
   SET code_type = 'ALIAS',
       is_primary = false,
       is_active = true,
       effective_to = COALESCE(c.effective_to, CURRENT_TIMESTAMP),
       updated_at = CURRENT_TIMESTAMP
  FROM items i
 WHERE c.item_id = i.id
   AND c.is_primary = true
   AND c.code <> upper(trim(i.sku));

INSERT INTO item_sku_codes (
  item_id,
  code,
  code_type,
  is_primary,
  is_active,
  effective_from,
  effective_to,
  remark,
  created_at,
  updated_at
)
SELECT
  i.id,
  upper(trim(i.sku)),
  'PRIMARY',
  true,
  true,
  COALESCE(i.created_at, CURRENT_TIMESTAMP),
  NULL,
  'base seed primary sku',
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM items i
WHERE trim(i.sku) <> ''
ON CONFLICT (code) DO UPDATE SET
  code_type = 'PRIMARY',
  is_primary = true,
  is_active = true,
  effective_to = NULL,
  updated_at = CURRENT_TIMESTAMP
WHERE item_sku_codes.item_id = EXCLUDED.item_id;

-- ===== item_uoms (unit truth source) =====
INSERT INTO item_uoms (
  item_id, uom, ratio_to_base, display_name,
  is_base, is_purchase_default, is_inbound_default, is_outbound_default
)
SELECT
  i.id,
  'PCS',
  1,
  'PCS',
  true,
  true,
  true,
  true
FROM items i
WHERE i.id IN (1, 3001, 3002, 3003, 4001, 4002)
ON CONFLICT ON CONSTRAINT uq_item_uoms_item_uom
DO UPDATE SET
  ratio_to_base = EXCLUDED.ratio_to_base,
  display_name = EXCLUDED.display_name,
  is_base = EXCLUDED.is_base,
  is_purchase_default = EXCLUDED.is_purchase_default,
  is_inbound_default = EXCLUDED.is_inbound_default,
  is_outbound_default = EXCLUDED.is_outbound_default;

-- ===== item_barcodes (primary; bind to base item_uom) =====
INSERT INTO item_barcodes (
  item_id,
  item_uom_id,
  barcode,
  symbology,
  active,
  is_primary,
  created_at,
  updated_at
)
SELECT
  i.id,
  u.id,
  'AUTO-BC-' || i.id::text,
  'CUSTOM',
  true,
  true,
  NOW(),
  NOW()
FROM items i
JOIN item_uoms u
  ON u.item_id = i.id
 AND u.is_base = true
WHERE NOT EXISTS (
  SELECT 1
  FROM item_barcodes b
  WHERE b.item_id = i.id
);

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






SELECT setval(
  pg_get_serial_sequence('items','id'),
  COALESCE((SELECT MAX(id) FROM items), 0),
  true
);

-- ===== supplier bindings / policies =====
UPDATE items
SET supplier_id = 1,
    enabled = true
WHERE id IN (3001, 3002, 4002);

UPDATE items
SET expiry_policy = 'REQUIRED'::expiry_policy,
    shelf_life_value = 30,
    shelf_life_unit = 'DAY',
    enabled = true,
    supplier_id = 1
WHERE id = 3001;

UPDATE items
SET supplier_id = 3,
    enabled = true
WHERE id = 1;


-- ===== WMS PMS read projections (PMS split test baseline) =====
-- PMS owner 真相已拆到 pms-api / pms DB。
-- WMS 测试仍暂时保留旧 PMS owner seed 以支撑尚未迁移的历史测试；
-- 同时必须把相同 PMS current-state 复制到 wms_pms_*_projection，
-- 供新测试路径通过 projection-backed fake PMS read client 读取。
INSERT INTO wms_pms_item_projection (
  item_id,
  sku,
  name,
  spec,
  enabled,
  supplier_id,
  brand,
  category,
  expiry_policy,
  shelf_life_value,
  shelf_life_unit,
  lot_source_policy,
  derivation_allowed,
  uom_governance_enabled,
  pms_updated_at,
  source_hash,
  sync_version,
  synced_at
)
SELECT
  i.id,
  i.sku,
  i.name,
  i.spec,
  COALESCE(i.enabled, TRUE),
  i.supplier_id,
  b.name_cn,
  c.category_name,
  i.expiry_policy::text,
  i.shelf_life_value,
  i.shelf_life_unit::text,
  i.lot_source_policy::text,
  COALESCE(i.derivation_allowed, TRUE),
  COALESCE(i.uom_governance_enabled, TRUE),
  COALESCE(i.updated_at, CURRENT_TIMESTAMP),
  'test-baseline:item:' || i.id::text || ':' || COALESCE(i.sku, ''),
  'test-baseline',
  CURRENT_TIMESTAMP
FROM items i
LEFT JOIN pms_brands b
  ON b.id = i.brand_id
LEFT JOIN pms_business_categories c
  ON c.id = i.category_id
WHERE i.id IN (1, 3001, 3002, 3003, 4001, 4002)
ON CONFLICT (item_id) DO UPDATE SET
  sku = EXCLUDED.sku,
  name = EXCLUDED.name,
  spec = EXCLUDED.spec,
  enabled = EXCLUDED.enabled,
  supplier_id = EXCLUDED.supplier_id,
  brand = EXCLUDED.brand,
  category = EXCLUDED.category,
  expiry_policy = EXCLUDED.expiry_policy,
  shelf_life_value = EXCLUDED.shelf_life_value,
  shelf_life_unit = EXCLUDED.shelf_life_unit,
  lot_source_policy = EXCLUDED.lot_source_policy,
  derivation_allowed = EXCLUDED.derivation_allowed,
  uom_governance_enabled = EXCLUDED.uom_governance_enabled,
  pms_updated_at = EXCLUDED.pms_updated_at,
  source_hash = EXCLUDED.source_hash,
  sync_version = EXCLUDED.sync_version,
  synced_at = CURRENT_TIMESTAMP;

INSERT INTO wms_pms_uom_projection (
  item_uom_id,
  item_id,
  uom,
  display_name,
  uom_name,
  ratio_to_base,
  net_weight_kg,
  is_base,
  is_purchase_default,
  is_inbound_default,
  is_outbound_default,
  pms_updated_at,
  source_hash,
  sync_version,
  synced_at
)
SELECT
  u.id,
  u.item_id,
  u.uom,
  u.display_name,
  COALESCE(NULLIF(u.display_name, ''), NULLIF(u.uom, ''), u.uom),
  u.ratio_to_base,
  u.net_weight_kg,
  u.is_base,
  u.is_purchase_default,
  u.is_inbound_default,
  u.is_outbound_default,
  COALESCE(u.updated_at, CURRENT_TIMESTAMP),
  'test-baseline:uom:' || u.id::text || ':' || u.item_id::text || ':' || COALESCE(u.uom, ''),
  'test-baseline',
  CURRENT_TIMESTAMP
FROM item_uoms u
WHERE u.item_id IN (1, 3001, 3002, 3003, 4001, 4002)
ON CONFLICT (item_uom_id) DO UPDATE SET
  item_id = EXCLUDED.item_id,
  uom = EXCLUDED.uom,
  display_name = EXCLUDED.display_name,
  uom_name = EXCLUDED.uom_name,
  ratio_to_base = EXCLUDED.ratio_to_base,
  net_weight_kg = EXCLUDED.net_weight_kg,
  is_base = EXCLUDED.is_base,
  is_purchase_default = EXCLUDED.is_purchase_default,
  is_inbound_default = EXCLUDED.is_inbound_default,
  is_outbound_default = EXCLUDED.is_outbound_default,
  pms_updated_at = EXCLUDED.pms_updated_at,
  source_hash = EXCLUDED.source_hash,
  sync_version = EXCLUDED.sync_version,
  synced_at = CURRENT_TIMESTAMP;

INSERT INTO wms_pms_sku_code_projection (
  sku_code_id,
  item_id,
  sku_code,
  code_type,
  is_primary,
  is_active,
  effective_from,
  effective_to,
  pms_updated_at,
  source_hash,
  sync_version,
  synced_at
)
SELECT
  sc.id,
  sc.item_id,
  sc.code,
  sc.code_type,
  sc.is_primary,
  sc.is_active,
  sc.effective_from,
  sc.effective_to,
  COALESCE(sc.updated_at, CURRENT_TIMESTAMP),
  'test-baseline:sku-code:' || sc.id::text || ':' || COALESCE(sc.code, ''),
  'test-baseline',
  CURRENT_TIMESTAMP
FROM item_sku_codes sc
WHERE sc.item_id IN (1, 3001, 3002, 3003, 4001, 4002)
ON CONFLICT (sku_code_id) DO UPDATE SET
  item_id = EXCLUDED.item_id,
  sku_code = EXCLUDED.sku_code,
  code_type = EXCLUDED.code_type,
  is_primary = EXCLUDED.is_primary,
  is_active = EXCLUDED.is_active,
  effective_from = EXCLUDED.effective_from,
  effective_to = EXCLUDED.effective_to,
  pms_updated_at = EXCLUDED.pms_updated_at,
  source_hash = EXCLUDED.source_hash,
  sync_version = EXCLUDED.sync_version,
  synced_at = CURRENT_TIMESTAMP;

INSERT INTO wms_pms_barcode_projection (
  barcode_id,
  item_id,
  item_uom_id,
  barcode,
  symbology,
  active,
  is_primary,
  pms_updated_at,
  source_hash,
  sync_version,
  synced_at
)
SELECT
  b.id,
  b.item_id,
  b.item_uom_id,
  b.barcode,
  b.symbology,
  b.active,
  b.is_primary,
  COALESCE(b.updated_at, CURRENT_TIMESTAMP),
  'test-baseline:barcode:' || b.id::text || ':' || COALESCE(b.barcode, ''),
  'test-baseline',
  CURRENT_TIMESTAMP
FROM item_barcodes b
WHERE b.item_id IN (1, 3001, 3002, 3003, 4001, 4002)
ON CONFLICT (barcode_id) DO UPDATE SET
  item_id = EXCLUDED.item_id,
  item_uom_id = EXCLUDED.item_uom_id,
  barcode = EXCLUDED.barcode,
  symbology = EXCLUDED.symbology,
  active = EXCLUDED.active,
  is_primary = EXCLUDED.is_primary,
  pms_updated_at = EXCLUDED.pms_updated_at,
  source_hash = EXCLUDED.source_hash,
  sync_version = EXCLUDED.sync_version,
  synced_at = CURRENT_TIMESTAMP;
