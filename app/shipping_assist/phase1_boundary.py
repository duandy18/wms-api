# app/shipping_assist/phase1_boundary.py
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath


class DomainOwner(StrEnum):
    TMS = "TMS"
    WMS = "WMS"
    OMS = "OMS"


class TmsSubdomain(StrEnum):
    SHIPPING_ASSIST_CONFIG = "ShippingAssistConfig"
    SHIPPING_ASSIST_QUOTE = "ShippingAssistQuote"
    SHIPPING_ASSIST_RECORDS = "ShippingAssistRecords"
    SHIPPING_ASSIST_REPORTS = "ShippingAssistReports"


@dataclass(frozen=True, slots=True)
class FrozenOwnership:
    """
    第一阶段冻结后的对象所有权定义。

    当前 WMS 已退役 quote / shipment runtime 代码；仍保留 WMS 当前承载的
    providers / pricing / records / reports 相关边界定义。
    """

    code: str
    owner_domain: DomainOwner
    owner_subdomain: TmsSubdomain | None
    collaborators: tuple[DomainOwner, ...]
    description: str


@dataclass(frozen=True, slots=True)
class FileOwnershipRule:
    """
    当前仓库物理文件归属冻结规则。

    已迁移到 Logistics 的 quote / quote_snapshot / shipment runtime 文件不再
    出现在本规则中；这些路径若被查询应返回 None。
    """

    path_prefix: str
    owner_domain: DomainOwner
    owner_subdomain: TmsSubdomain | None
    note: str


FROZEN_OWNERSHIP: dict[str, FrozenOwnership] = {
    "shipping_provider": FrozenOwnership(
        code="shipping_provider",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_CONFIG,
        collaborators=(DomainOwner.WMS,),
        description="快递网点实体，由 TMS/ShippingAssistConfig 主拥有。",
    ),
    "warehouse_shipping_provider_binding": FrozenOwnership(
        code="warehouse_shipping_provider_binding",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_CONFIG,
        collaborators=(DomainOwner.WMS,),
        description="仓库与快递网点绑定属于发货辅助配置，不属于 WMS 私有配置。",
    ),
    "pricing_scheme": FrozenOwnership(
        code="pricing_scheme",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_CONFIG,
        collaborators=(DomainOwner.WMS,),
        description="运价方案由 TMS/ShippingAssistConfig 主拥有。",
    ),
    "destination_group": FrozenOwnership(
        code="destination_group",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_CONFIG,
        collaborators=(DomainOwner.TMS,),
        description="区域规则属于 TMS/ShippingAssistConfig。",
    ),
    "pricing_matrix": FrozenOwnership(
        code="pricing_matrix",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_CONFIG,
        collaborators=(DomainOwner.TMS,),
        description="价格矩阵属于 TMS/ShippingAssistConfig。",
    ),
    "surcharge_config": FrozenOwnership(
        code="surcharge_config",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_CONFIG,
        collaborators=(DomainOwner.TMS,),
        description="附加费配置属于 TMS/ShippingAssistConfig。",
    ),
    "shipping_record": FrozenOwnership(
        code="shipping_record",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_RECORDS,
        collaborators=(DomainOwner.WMS, DomainOwner.OMS),
        description="shipping_record 是发货记录，由发货辅助/ShippingAssistRecords 主拥有。",
    ),
    "shipping_report": FrozenOwnership(
        code="shipping_report",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_REPORTS,
        collaborators=(DomainOwner.WMS,),
        description="发货辅助统计统一属于 TMS/ShippingAssistReports。",
    ),
    "order": FrozenOwnership(
        code="order",
        owner_domain=DomainOwner.OMS,
        owner_subdomain=None,
        collaborators=(DomainOwner.TMS, DomainOwner.WMS),
        description="Order 是业务来源对象，不是发货辅助核心对象。",
    ),
    "warehouse_outbound": FrozenOwnership(
        code="warehouse_outbound",
        owner_domain=DomainOwner.WMS,
        owner_subdomain=None,
        collaborators=(DomainOwner.TMS,),
        description="仓内出库属于 WMS；可触发外部 Logistics 执行，但不拥有发货执行主线。",
    ),
}


FILE_OWNERSHIP_RULES: tuple[FileOwnershipRule, ...] = (
    FileOwnershipRule(
        path_prefix="app/models/shipping_provider.py",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_CONFIG,
        note="快递网点实体。",
    ),
    FileOwnershipRule(
        path_prefix="app/models/warehouse_shipping_provider.py",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_CONFIG,
        note="仓库-快递网点绑定。",
    ),
    FileOwnershipRule(
        path_prefix="app/models/shipping_provider_contact.py",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_CONFIG,
        note="快递网点联系人配置。",
    ),
    FileOwnershipRule(
        path_prefix="app/shipping_assist/providers/",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_CONFIG,
        note="发货辅助 providers 子域。",
    ),
    FileOwnershipRule(
        path_prefix="app/shipping_assist/pricing/",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_CONFIG,
        note="发货辅助 pricing 子域。",
    ),
    FileOwnershipRule(
        path_prefix="app/shipping_assist/alerts/",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_QUOTE,
        note="告警聚合服务；当前保留历史运输异常观测。",
    ),
    FileOwnershipRule(
        path_prefix="app/models/shipping_record.py",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_RECORDS,
        note="发货记录事实模型。",
    ),
    FileOwnershipRule(
        path_prefix="app/shipping_assist/records/router.py",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_RECORDS,
        note="发货记录新主路由装配入口。",
    ),
    FileOwnershipRule(
        path_prefix="app/shipping_assist/records/contracts.py",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_RECORDS,
        note="发货记录只读合同。",
    ),
    FileOwnershipRule(
        path_prefix="app/shipping_assist/records/repository.py",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_RECORDS,
        note="发货记录只读查询实现。",
    ),
    FileOwnershipRule(
        path_prefix="app/shipping_assist/records/routes_read.py",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_RECORDS,
        note="发货记录读取路由。",
    ),
    FileOwnershipRule(
        path_prefix="app/api/routers/shipping_reports_routes_",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_REPORTS,
        note="历史发货辅助报表叶子路由；冻结归属仍属于 ShippingAssistReports。",
    ),
    FileOwnershipRule(
        path_prefix="app/shipping_assist/reports/router.py",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_REPORTS,
        note="发货辅助报表新主路由壳。",
    ),
    FileOwnershipRule(
        path_prefix="app/shipping_assist/reports/routes_",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_REPORTS,
        note="发货辅助报表子路由实现。",
    ),
    FileOwnershipRule(
        path_prefix="app/shipping_assist/reports/helpers.py",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_REPORTS,
        note="发货辅助报表 helper。",
    ),
    FileOwnershipRule(
        path_prefix="app/shipping_assist/reports/contracts.py",
        owner_domain=DomainOwner.TMS,
        owner_subdomain=TmsSubdomain.SHIPPING_ASSIST_REPORTS,
        note="发货辅助报表合同定义。",
    ),
)


def get_frozen_ownership(code: str) -> FrozenOwnership:
    """
    返回第一阶段冻结对象的所有权定义。

    Raises:
        KeyError: 当 code 不存在时抛出。
    """

    return FROZEN_OWNERSHIP[code]


def find_file_ownership(path: str) -> FileOwnershipRule | None:
    """
    根据文件路径返回冻结后的领域归属。

    规则：
    - 采用前缀匹配
    - 更长的 path_prefix 优先，避免上层前缀吞掉更具体规则
    """

    normalized = PurePosixPath(path).as_posix()
    matched: FileOwnershipRule | None = None

    for rule in sorted(FILE_OWNERSHIP_RULES, key=lambda item: len(item.path_prefix), reverse=True):
        if normalized.startswith(rule.path_prefix):
            matched = rule
            break

    return matched
