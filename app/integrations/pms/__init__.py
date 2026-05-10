# app/integrations/pms/__init__.py
"""
PMS integration boundary.

Consumers outside PMS should depend on this package instead of importing
PMS export services directly.
"""

from app.integrations.pms.inprocess_client import InProcessPmsReadClient

__all__ = ["InProcessPmsReadClient"]
