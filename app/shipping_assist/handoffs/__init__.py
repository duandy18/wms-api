
# app/shipping_assist/handoffs/__init__.py
"""
Shipping Assist / Handoffs module.

语义定位：
- 发货交接读取 wms_logistics_export_records；
- 交接数据读取 wms_logistics_handoff_payloads；
- ready / import-results / shipping-results 是 WMS 与独立 Logistics 的跨系统交接资源接口；
- 旧 /wms/outbound/logistics-* 已退役，不保留 alias。
"""
