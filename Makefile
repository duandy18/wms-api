# ==============================
#   WMS-DU Makefile (Thin Root)
# ==============================

SHELL := /bin/bash
VENV  := .venv
PY    := $(shell if [ -x "$(VENV)/bin/python3" ]; then echo "$(VENV)/bin/python3"; elif [ -x "$(VENV)/bin/python" ]; then echo "$(VENV)/bin/python"; else echo "python3"; fi)
PIP   := $(VENV)/bin/pip
ALEMB := $(PY) -m alembic
PYTEST:= $(VENV)/bin/pytest

# ========================
# Database DSN
# ========================
TEST_DB_DSN ?= postgresql+psycopg://postgres:wms@127.0.0.1:55432/postgres
DEV_DB_DSN  ?= postgresql+psycopg://wms:wms@127.0.0.1:5433/wms
DEV_TEST_DB_DSN ?= postgresql+psycopg://wms:wms@127.0.0.1:5433/wms_test

# ========================
# Local runtime env defaults
# ========================
WMS_ENV ?= dev
WMS_TEST_DATABASE_URL ?=
WMS_DATABASE_URL ?= $(DEV_DB_DSN)
PMS_API_BASE_URL ?= http://127.0.0.1:8005
OMS_API_BASE_URL ?= http://127.0.0.1:8010
OMS_API_TOKEN ?=

# ---- 自动加载 .env.local ----
ifneq (,$(wildcard .env.local))
include .env.local
endif

DEV_ENV := WMS_ENV="$(WMS_ENV)" WMS_TEST_DATABASE_URL="$(WMS_TEST_DATABASE_URL)" WMS_DATABASE_URL="$(WMS_DATABASE_URL)" PMS_API_BASE_URL="$(PMS_API_BASE_URL)" OMS_API_BASE_URL="$(OMS_API_BASE_URL)" OMS_API_TOKEN="$(OMS_API_TOKEN)" PYTHONPATH=.
TEST_ENV := WMS_ENV=test WMS_TEST_DATABASE_URL="$(DEV_TEST_DB_DSN)" WMS_DATABASE_URL="$(DEV_TEST_DB_DSN)" PMS_API_BASE_URL="$(PMS_API_BASE_URL)" OMS_API_BASE_URL="$(OMS_API_BASE_URL)" OMS_API_TOKEN="$(OMS_API_TOKEN)" PYTHONPATH=.

# ---- 分模块拆分 ----
include scripts/make/env.mk
include scripts/make/db.mk
include scripts/make/run.mk
include scripts/make/audit.mk
include scripts/make/test.mk
include scripts/make/lint.mk
include scripts/make/openapi.mk
