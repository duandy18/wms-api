# WMS-DU

WMS-DU backend service for WMS execution, inventory, inbound, outbound, finance, and cross-system integration.

当前后端目录清理原则：

- ORM 模型归属业务模块目录，app/models 全局模型目录已退役。
- 运行代码按业务域收敛，避免全局 services / repos / contracts / helpers / utils 残留。
- 无真实引用的旧脚本、旧 datafix、旧 backfill、旧 demo、旧 smoke 优先删除。
- 删不掉但有真实业务归属的文件，应迁入对应业务模块。
- 不保留 alias / 双轨 / 兼容壳。
- 前后端继续坚持刚性契约。

## Local dev ports

| Component | Port | Purpose |
| --- | ---: | --- |
| wms-api | 8000 | FastAPI / Uvicorn HTTP service |
| wms-web | 5173 | Vite dev server |
| wms-db | 5433 | Shared local PostgreSQL host port |
| pms-api upstream | 8005 | PMS HTTP API consumed by WMS |
| oms-api upstream | 8010 | OMS HTTP API consumed by WMS |
| procurement-api upstream | 8015 | Procurement HTTP API consumed by WMS |
| logistics-api upstream | 8020 | Logistics HTTP API consumed by WMS |

See `docs/dev-ports.md` for the full local port contract.

## 后端常用入口

- make alembic-check
- make test TESTS="tests/api/test_no_duplicate_routes.py tests/api/test_user_api.py"
- make lint-backend
- make openapi-export

当前保留的 scripts/ 主要是 Makefile / CI / 测试 / 审计真实入口，不再维护历史一次性修补脚本。

---

## Frontend

WMS frontend is maintained in the independent `wms-web` repository:

- local Vite port: `5173`
- API base URL: `http://127.0.0.1:8000`
