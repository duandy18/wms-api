# scripts/make/pms_api.mk
#
# Standalone PMS API process commands.
#
# 说明：
# - 使用 .RECIPEPREFIX 避免 Makefile tab / heredoc 缩进问题。
# - pms-api 当前是独立进程、暂时同库。
# - 不挂 WMS / OMS / Procurement / Finance / Shipping Assist runtime routes。

.RECIPEPREFIX := >

.PHONY: pms-api-dev pms-api-routes pms-api-smoke

pms-api-dev:
>PYTHONPATH=. \
>PMS_ENV=dev \
>WMS_ENV=dev \
>WMS_DATABASE_URL="$(DEV_DB_DSN)" \
>WMS_TEST_DATABASE_URL="$(DEV_DB_DSN)" \
>$(PY) -m uvicorn app.pms_api.main:app --host 127.0.0.1 --port 8002 --reload

pms-api-routes:
>PYTHONPATH=. $(PY) scripts/print_pms_api_routes.py

pms-api-smoke:
>set -euo pipefail; \
>PYTHONPATH=. \
>PMS_ENV=dev \
>WMS_ENV=dev \
>WMS_DATABASE_URL="$(DEV_DB_DSN)" \
>WMS_TEST_DATABASE_URL="$(DEV_DB_DSN)" \
>$(PY) -m uvicorn app.pms_api.main:app --host 127.0.0.1 --port 8002 >/tmp/pms-api-smoke.log 2>&1 & \
>pid=$$!; \
>trap 'kill $$pid >/dev/null 2>&1 || true' EXIT; \
>for i in $$(seq 1 30); do \
>  if curl -fsS http://127.0.0.1:8002/health >/tmp/pms-api-health.json; then \
>    cat /tmp/pms-api-health.json; \
>    echo; \
>    exit 0; \
>  fi; \
>  sleep 1; \
>done; \
>echo "pms-api smoke failed"; \
>cat /tmp/pms-api-smoke.log; \
>exit 1
