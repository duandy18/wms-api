# app/integrations/oms/__init__.py
"""
WMS-owned OMS read projections.

Boundary:
- OMS owner runtime remains in oms-api.
- WMS consumes OMS read-v1 HTTP output.
- These tables are WMS local read indexes, not OMS owner tables.
- Business writes must not write these projection tables directly.
"""
