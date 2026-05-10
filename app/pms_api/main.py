# app/pms_api/main.py
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.http_problem_handlers import register_exception_handlers
from app.pms_api.router_mount import mount_pms_routers

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("pms-api")

PMS_API_VERSION = "0.1.0"
PMS_ENV = os.getenv("PMS_ENV", os.getenv("WMS_ENV", "dev")).lower()

app = FastAPI(
    title="PMS API",
    version=PMS_API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "http://127.0.0.1:8002",
        "http://localhost:8002",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
mount_pms_routers(app)


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "name": "PMS API",
        "version": PMS_API_VERSION,
        "env": PMS_ENV,
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "pms-api",
        "version": PMS_API_VERSION,
    }


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/pms/read/v1/health")
async def read_v1_health() -> dict[str, str]:
    return {
        "status": "ok",
        "surface": "pms-read-v1",
    }
