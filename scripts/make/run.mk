# ========================
# Local runtime commands
# ========================

HOST ?= 0.0.0.0
PORT ?= 8000

.PHONY: uvicorn
uvicorn: venv
	@$(DEV_ENV) $(PY) -m uvicorn app.main:app --host "$(HOST)" --port "$(PORT)" --reload
