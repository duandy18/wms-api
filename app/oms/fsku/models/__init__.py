# app/oms/fsku/models/__init__.py
# OMS only owns platform merchant-code bindings.
# PMS owns FSKU master data and FSKU components.

from app.oms.fsku.models.merchant_code_fsku_binding import MerchantCodeFskuBinding

__all__ = [
    "MerchantCodeFskuBinding",
]
