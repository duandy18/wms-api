# scripts/print_pms_api_routes.py
from __future__ import annotations

from app.pms_api.main import app


def main() -> None:
    rows: list[tuple[str, str]] = []

    for route in app.routes:
        path = getattr(route, "path", "")
        methods = sorted(getattr(route, "methods", []) or [])
        if isinstance(path, str):
            rows.append((path, ",".join(methods)))

    for path, methods in sorted(rows):
        print(f"{methods:20s} {path}")


if __name__ == "__main__":
    main()
