# =================================
# env.mk - 基础与帮助/环境/清理
# =================================

.PHONY: help
help:
	@echo ""
	@echo "WMS-DU Makefile 帮助："
	@echo "  make env                     - 打印当前本地开发环境变量"
	@echo "  make env-check               - 检查 WMS 本地环境、PMS projection feed 与 OMS OpenAPI"
	@echo "  make venv                    - 创建虚拟环境"
	@echo "  make deps                    - 安装依赖"
	@echo "  make clean-pyc               - 清缓存"
	@echo "  make uvicorn                 - 启动本地后端，默认端口 8000"
	@echo "  make alembic-check           - alembic check (默认 DEV 5433)"
	@echo "  make upgrade-head            - alembic 升级到 HEAD (默认 DEV 5433)"
	@echo "  make alembic-current-dev     - 查看当前 DEV 库 revision（5433）"
	@echo "  make alembic-history-dev     - 查看 DEV 库最近迁移历史（tail 30）"
	@echo ""
	@echo "  make dev-reset-db            - 重置 5433 开发库（慎用，核爆）"
	@echo "  make dev-reset-test-db       - 重置 5433 测试库 wms_test（推荐，pytest 使用）"
	@echo "  make dev-ensure-admin        - 在 5433 开发库添加 admin/admin123"
	@echo "  make pilot-ensure-admin      - 在 55432 中试库添加 admin（自定义密码）"
	@echo ""
	@echo "  make audit-uom               - 审计：services 层禁止散落 qty_ordered * units_per_case（仅允许 qty_base.py）"
	@echo "  make audit-consistency       - 审计：禁止绕过库存底座（禁止在非底座模块直接 await write_ledger()）"
	@echo "  make audit-all               - 口径 + 一致性双审计"
	@echo "  make seed-opening-ledger-test - 制度化：按 stocks 补齐 opening ledger（用于三账一致性）"
	@echo "  make audit-three-books       - 三账一致性自检（TEST DB 上运行 snapshot + compare）"
	@echo ""
	@echo "  make pms-projection-sync     - 从 PMS 同步 WMS 本地 projection"
	@echo "  make oms-fulfillment-projection-sync - 从 OMS 同步 WMS 履约 projection"
	@echo "  make test                    - pytest（默认跑 wms_test；pytest 后自动补账 + 三账体检）"
	@echo "  make test-core               - 只跑 grp_core"
	@echo "  make test-flow               - 只跑 grp_flow"
	@echo "  make test-snapshot           - 只跑 grp_snapshot"
	@echo "  make test-rbac               - RBAC 测试"
	@echo "  make test-internal-outbound  - 内部出库 Golden Flow E2E"
	@echo "  make test-phase5-service-assignment - Phase5: service assignment tests (CI gate)"

	@echo "  make test-all                - 全量回归（不含三账体检后置步骤）"
	@echo ""
	@echo "  make lint-backend            - pre-commit/ruff"
	@echo ""

.PHONY: env env-dev env-test env-check
env: env-dev

env-dev:
	@printf '%s\n' 'export WMS_ENV="$(WMS_ENV)"'
	@printf '%s\n' 'export WMS_TEST_DATABASE_URL="$(WMS_TEST_DATABASE_URL)"'
	@printf '%s\n' 'export WMS_DATABASE_URL="$(WMS_DATABASE_URL)"'
	@printf '%s\n' 'export PMS_API_BASE_URL="$(PMS_API_BASE_URL)"'
	@printf '%s\n' 'export OMS_API_BASE_URL="$(OMS_API_BASE_URL)"'
	@printf '%s\n' '# OMS_API_TOKEN is loaded from .env.local for make targets and is intentionally not printed by make env'
	@printf '%s\n' 'export PYTHONPATH=.'

env-test:
	@printf '%s\n' 'export WMS_ENV=test'
	@printf '%s\n' 'export WMS_TEST_DATABASE_URL="$(DEV_TEST_DB_DSN)"'
	@printf '%s\n' 'export WMS_DATABASE_URL="$(DEV_TEST_DB_DSN)"'
	@printf '%s\n' 'export PMS_API_BASE_URL="$(PMS_API_BASE_URL)"'
	@printf '%s\n' 'export OMS_API_BASE_URL="$(OMS_API_BASE_URL)"'
	@printf '%s\n' 'export PYTHONPATH=.'

env-check:
	@echo "===== WMS API env ====="
	@echo "PY=$(PY)"
	@echo "HOST=$(HOST)"
	@echo "PORT=$(PORT)"
	@echo "WMS_ENV=$(WMS_ENV)"
	@echo "WMS_TEST_DATABASE_URL=$(WMS_TEST_DATABASE_URL)"
	@echo "WMS_DATABASE_URL=$(WMS_DATABASE_URL)"
	@echo "PMS_API_BASE_URL=$(PMS_API_BASE_URL)"
	@echo "OMS_API_BASE_URL=$(OMS_API_BASE_URL)"
	@if [ -n "$(OMS_API_TOKEN)" ]; then echo "OMS_API_TOKEN_CONFIGURED=true"; else echo "OMS_API_TOKEN_CONFIGURED=false"; fi
	@echo
	@echo "===== WMS app import check ====="
	@$(DEV_ENV) $(PY) -c "from app.main import app; print('WMS app import OK:', len(app.routes), 'routes')"
	@echo
	@echo "===== PMS projection feed check ====="
	@curl --max-time 3 -fsS -H "X-Service-Client: wms-service" "$(PMS_API_BASE_URL)/pms/read/v1/projection-feed/suppliers?limit=1&offset=0" >/dev/null && echo "PMS projection feed OK: $(PMS_API_BASE_URL)" || (echo "PMS projection feed FAILED: $(PMS_API_BASE_URL)" >&2; exit 2)
	@echo
	@echo "===== OMS OpenAPI check ====="
	@curl --max-time 3 -fsS "$(OMS_API_BASE_URL)/openapi.json" >/dev/null && echo "OMS API OK: $(OMS_API_BASE_URL)" || (echo "OMS API FAILED: $(OMS_API_BASE_URL)" >&2; exit 2)

.PHONY: venv
venv:
	@test -d $(VENV) || python3 -m venv $(VENV)
	@$(PY) -m pip install -U pip

.PHONY: deps
deps: venv
	@test -f requirements.txt && $(PIP) install -r requirements.txt || echo "[deps] skip"

.PHONY: clean-pyc
clean-pyc:
	@find app -name '__pycache__' -type d -prune -exec rm -rf {} + || true
	@find app -name '*.py[co]' -delete || true

.PHONY: day0
day0: clean-pyc alembic-check
	@echo 'Day-0 done.'

# =================================
# 分组标记注入（A + C）
# =================================
.PHONY: mark-ac
mark-ac:
	@bash -c 'set -euo pipefail; \
	  apply_mark() { \
	    local mark="$$1"; shift; \
	    for f in "$$@"; do \
	      if [ -f "$$f" ] && ! rg -q "pytestmark" "$$f"; then \
	        sed -i "1i import pytest\npytestmark = pytest.mark.$$mark\n" "$$f"; \
	        echo "[mark] added $$mark -> $$f"; \
	      fi; \
	    done; \
	  }; \
	  apply_mark grp_core \
	    tests/services/test_inbound_service.py \
	    tests/services/test_putaway_service.py \
	    tests/services/test_outbound_service.py \
	    tests/services/test_inventory_ops.py; \
	  apply_mark grp_flow \
	    tests/services/test_outbound_fefo_basic.py \
	    tests/services/test_outbound_ledger_consistency.py \
	    tests/services/test_stock_service_fefo.py;'
