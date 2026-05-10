# app/pms_api/__init__.py
"""
Standalone PMS API application package.

This package is the process boundary for the future PMS service.
It must mount PMS-owned routes only and must not mount WMS / OMS /
Procurement / Finance / Shipping Assist runtime routes.
"""
