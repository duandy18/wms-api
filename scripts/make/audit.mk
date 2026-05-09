# =================================
# audit.mk - 审计 / 守门员规则
# =================================

.PHONY: audit-no-legacy-stock-sql
audit-no-legacy-stock-sql:
	@bash -c 'set -euo pipefail; \
	  echo "[audit-no-legacy-stock-sql] forbid SQL access to legacy stocks/batches in app/..."; \
	  hits="$$(rg -n --hidden \
	    --glob "!alembic/**" \
	    --glob "!tests/**" \
	    --glob "!**/*.md" \
	    --glob "!**/*.sql" \
	    "(?i)(FROM|JOIN|UPDATE|INTO)\\s+stocks\\b|(?i)(FROM|JOIN|UPDATE|INTO)\\s+batches\\b" app || true)"; \
	  if [ -z "$$hits" ]; then \
	    echo "[audit-no-legacy-stock-sql] OK (no legacy SQL access)"; \
	    exit 0; \
	  fi; \
	  echo ""; \
	  echo "$$hits"; \
	  echo ""; \
	  echo "[audit-no-legacy-stock-sql] FAIL: legacy SQL access detected in app/"; \
	  echo "  use stocks_lot + lots instead (lot-world is the only truth)."; \
	  exit 1;'

# =================================
# 运价模块守门员：禁止旧 surcharge / old table 词汇回流
# - 只扫 app/tests（不扫 alembic，迁移历史允许保留）
# - 防止 condition_json / amount_json / pricing_scheme_dest_adjustments /
#   dest_adjustments 这类退役口径重新混入运行/测试代码
# =================================
.PHONY: audit-no-legacy-pricing-terms
audit-no-legacy-pricing-terms:
	@bash -c 'set -euo pipefail; \
	  echo "[audit-no-legacy-pricing-terms] forbid retired pricing terms in app/tests ..."; \
	  hits="$$(rg -n --hidden \
	    --glob "!**/*.md" \
	    "(condition_json|amount_json|pricing_scheme_dest_adjustments|dest_adjustments)" \
	    app tests || true)"; \
	  if [ -z "$$hits" ]; then \
	    echo "[audit-no-legacy-pricing-terms] OK (no retired pricing terms)"; \
	    exit 0; \
	  fi; \
	  echo ""; \
	  echo "$$hits"; \
	  echo ""; \
	  echo "[audit-no-legacy-pricing-terms] FAIL: retired pricing terms detected in app/tests"; \
	  echo "  use structured surcharge fields + current pricing contracts only."; \
	  exit 1;'

# =================================
# Phase 5.1 封口：禁止任何隐性写 orders.warehouse_id
# - 白名单仅允许：manual-assign service（devconsole 写入已被禁止）
# =================================
.PHONY: audit-no-implicit-warehouse-id
audit-no-implicit-warehouse-id:
	@bash -c 'set -euo pipefail; \
	  echo "[audit-no-implicit-warehouse-id] forbid implicit writes to orders.warehouse_id ..."; \
	  hits="$$(rg -n "UPDATE orders\\s+SET\\s+warehouse_id|SET\\s+warehouse_id\\s*=" app -S || true)"; \
	  if [ -z "$$hits" ]; then \
	    echo "[audit-no-implicit-warehouse-id] OK (no hits)"; exit 0; \
	  fi; \
	  allow_re="app/wms/outbound/services/order_fulfillment_manual_assign\\.py"; \
	  bad="$$(printf "%s\n" "$$hits" | rg -v "$$allow_re" || true)"; \
	  if [ -n "$$bad" ]; then \
	    echo "$$bad"; \
	    echo "[audit-no-implicit-warehouse-id] FAIL: only manual-assign service may write orders.warehouse_id"; \
	    exit 1; \
	  fi; \
	  echo "[audit-no-implicit-warehouse-id] OK (hits only in whitelist)"; \
	'

# =================================
# PMS 独立化第一阶段收口守门员：
# WMS 执行业务侧禁止重新读取 PMS owner/export。
#
# 唯一允许：
#   app/wms/pms_projection/services/rebuild_service.py
#
# 说明：
# - rebuild_service 是 WMS-local PMS projection 的重建入口；
# - WMS 执行链必须只读 wms_pms_*_projection；
# - 禁止 fallback 回 app.pms / PMS owner items / item_uoms / item_barcodes / item_sku_codes。
# =================================
.PHONY: audit-no-wms-pms-owner-boundary
audit-no-wms-pms-owner-boundary:
	@bash -c 'set -euo pipefail; \
	  echo "[audit-no-wms-pms-owner-boundary] forbid WMS runtime coupling to PMS owner/export ..."; \
	  forbidden_re="from app\\.pms|app\\.pms|ItemReadService|BarcodeProbeService|PmsExport|(?i:\\b(FROM|JOIN|UPDATE|INTO)\\s+([a-z_][a-z0-9_]*\\.)?items\\b)|(?i:\\b(FROM|JOIN|UPDATE|INTO)\\s+([a-z_][a-z0-9_]*\\.)?item_uoms\\b)|(?i:\\b(FROM|JOIN|UPDATE|INTO)\\s+([a-z_][a-z0-9_]*\\.)?item_barcodes\\b)|(?i:\\b(FROM|JOIN|UPDATE|INTO)\\s+([a-z_][a-z0-9_]*\\.)?item_sku_codes\\b)|items\\.expiry_policy|items\\.lot_source_policy|item_uoms\\.ratio_to_base"; \
	  hits="$$(rg -n --hidden \
	    --glob "!**/__pycache__/**" \
	    --glob "!**/*.md" \
	    "$$forbidden_re" app/wms || true)"; \
	  if [ -z "$$hits" ]; then \
	    echo "[audit-no-wms-pms-owner-boundary] OK (no PMS owner/export boundary hits)"; \
	    exit 0; \
	  fi; \
	  allow_re="^app/wms/pms_projection/services/rebuild_service\\.py:"; \
	  bad="$$(printf "%s\n" "$$hits" | rg -v "$$allow_re" || true)"; \
	  if [ -n "$$bad" ]; then \
	    echo ""; \
	    echo "$$bad"; \
	    echo ""; \
	    echo "[audit-no-wms-pms-owner-boundary] FAIL: WMS business code must not read PMS owner/export"; \
	    echo "  allowed owner read location: app/wms/pms_projection/services/rebuild_service.py"; \
	    echo "  use WMS-local PMS projection read services instead."; \
	    exit 1; \
	  fi; \
	  echo "[audit-no-wms-pms-owner-boundary] OK (hits only in projection rebuild whitelist)"; \
	'

# =================================
# Phase 2 守门员：运价区间必须兜底覆盖（避免 no matching bracket 线上翻车）
# =================================
.PHONY: audit-pricing-brackets
audit-pricing-brackets: venv
	@bash -c 'set -euo pipefail; \
	  export PYTHONPATH=. ; \
	  export WMS_DATABASE_URL="$(DEV_TEST_DB_DSN)"; \
	  export WMS_TEST_DATABASE_URL="$(DEV_TEST_DB_DSN)"; \
	  echo "[audit-pricing-brackets] scanning pricing zones/brackets on TEST DB ($(DEV_TEST_DB_DSN)) ..."; \
	  "$(PY)" scripts/audit_pricing_brackets.py;'

# 统一 audit 入口
# =================================

.PHONY: audit-all
audit-all: audit-no-legacy-stock-sql audit-no-legacy-pricing-terms audit-no-wms-pms-owner-boundary
	@echo "[audit-all] OK"
