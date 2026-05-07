# =================================
# lint.mk - backend lint
# =================================

.PHONY: lint lint-backend

lint: lint-backend

lint-backend: venv
	@echo "[lint] Running pre-commit hooks ..."
	pre-commit run --all-files
