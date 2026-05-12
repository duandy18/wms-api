# ========================
# Local runtime commands
# ========================

HOST ?= 0.0.0.0
PORT ?= 8000

.PHONY: uvicorn
uvicorn: venv
	@WMS_ENV=dev WMS_TEST_DATABASE_URL= WMS_DATABASE_URL="$(DEV_DB_DSN)" PYTHONPATH=. $(PY) -m uvicorn app.main:app --host "$(HOST)" --port "$(PORT)" --reload
