# app/partners/suppliers/models/__init__.py
from app.partners.suppliers.models.supplier import Supplier
from app.partners.suppliers.models.supplier_contact import SupplierContact

__all__ = [
    "Supplier",
    "SupplierContact",
]
