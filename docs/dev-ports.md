# WMS local development ports

## Port contract

| Component | Port | Purpose |
| --- | ---: | --- |
| wms-api | 8000 | FastAPI / Uvicorn HTTP service |
| wms-web | 5173 | Vite dev server |
| wms-db | 5433 | Shared local PostgreSQL host port |
| pms-api upstream | 8005 | PMS HTTP API consumed by WMS |
| oms-api upstream | 8010 | OMS HTTP API consumed by WMS |
| procurement-api upstream | 8015 | Procurement HTTP API consumed by WMS |
| logistics-api upstream | 8020 | Logistics HTTP API consumed by WMS |

## Environment variables

| Variable | Example | Meaning |
| --- | --- | --- |
| `WMS_DATABASE_URL` | `postgresql+psycopg://wms:wms@127.0.0.1:5433/wms` | WMS development database |
| `WMS_TEST_DATABASE_URL` | `postgresql+psycopg://wms:wms@127.0.0.1:5433/wms_test` | WMS test database |
| `PMS_API_BASE_URL` | `http://127.0.0.1:8005` | PMS API upstream |
| `OMS_API_BASE_URL` | `http://127.0.0.1:8010` | OMS API upstream |
| `PROCUREMENT_API_BASE_URL` | `http://127.0.0.1:8015` | Procurement API upstream |
| `LOGISTICS_API_BASE_URL` | `http://127.0.0.1:8020` | Logistics API upstream |
| `OMS_API_TOKEN` | empty by default | Bearer token with `oms.fulfillment.read` scope when syncing OMS fulfillment projection |

## Rules

- Local development PostgreSQL uses the shared host port `5433`.
- Do not use `5433` for FastAPI. It is reserved for PostgreSQL.
- Do not use `8000` for PostgreSQL. It is reserved for wms-api HTTP.
- wms-web should call wms-api through `VITE_API_BASE_URL=http://127.0.0.1:8000`.
- WMS must read Procurement purchase order sources through wms-api → procurement-api; wms-web must not call procurement-api directly.
- If another local PostgreSQL container already owns `5433`, do not start another DB container from this repo.
