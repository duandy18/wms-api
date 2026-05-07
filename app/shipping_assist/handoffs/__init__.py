# app/shipping_assist/handoffs/__init__.py
"""
Shipping Assist / Handoffs module.

语义定位：
- 发货交接页读取 wms_logistics_export_records；
- 该表记录 WMS 出库事实交接给独立 Logistics 系统的状态；
- 本模块只提供只读列表，不提供导入结果/物流结果回写。
"""
