from __future__ import annotations

from typing import Any

from .config import threshold
from .evidence_builder import build_evidence
from .metric_normalizer import normalize_percentage, safe_divide, safe_number
from .types import DiagnosisInput, RelationshipFinding, ValidationResult


def detect_contradictions(
    data: DiagnosisInput,
    config: dict[str, Any],
    validation: ValidationResult,
    inventory_diagnosis: dict[str, Any],
    advertising_diagnosis: dict[str, Any],
    profitability_diagnosis: dict[str, Any],
    sales_diagnosis: dict[str, Any],
    sku_structure: dict[str, Any],
) -> tuple[list[RelationshipFinding], list[str]]:
    findings: list[RelationshipFinding] = []
    skipped: list[str] = []
    inventory = data.get("inventory", {})
    advertising = data.get("advertising", {})
    profitability = data.get("profitability", {})
    sales = data.get("sales", {})
    roles = data.get("skuRoles", {})
    sku_details = data.get("skuDetails", [])
    high_margin = threshold(config, ("profitability", "high_margin")) or 0
    critical_days = threshold(config, ("inventory", "critical_days")) or 0
    min_spend = threshold(config, ("advertising", "minimum_spend_for_reliable_acos")) or 0
    high_acos = threshold(config, ("advertising", "high_acos")) or 0
    inefficient_warning = threshold(config, ("sku_roles", "inefficient_share_warning")) or 0

    slow_high_margin = [
        item for item in sku_details
        if (normalize_percentage(item.get("grossMargin")) or -999) >= high_margin
        and (safe_number(item.get("dailyUnits")) or 0) <= 0
        and (safe_number(item.get("availableDays")) or 0) > critical_days
    ]
    if slow_high_margin:
        findings.append(_finding("FANG_REL_001", "高毛利未转化为现金贡献", "P1", "confirmed", "高毛利率SKU同时低销量且库存天数过高，账面利润空间未转化为现金贡献。", [build_evidence("FANG_REL_001", "confirmed", ["skuDetails.grossMargin", "skuDetails.dailyUnits", "skuDetails.availableDays"], "逐SKU关系比较", f"grossMargin>={high_margin:.0%}; availableDays>{critical_days:g}", "同一SKU的毛利、销量和库存关系", {"skus": [item.get("sku") for item in slow_high_margin]}, "高毛利、低动销与高库存同时发生。")], {"turnover": "库存资金回收慢", "cashFlow": "账面利润未形成现金回报"}))
    else:
        skipped.append("FANG_REL_001")

    if (safe_number(advertising.get("spend")) or 0) >= min_spend:
        if data.get("metadata", {}).get("naturalSalesGrowth") is False:
            findings.append(_finding("FANG_REL_002", "广告未形成自然增量", "P1", "probable", "广告花费达到可靠样本，但自然销量未增长，广告可能只在购买订单。", [advertising_diagnosis["evidence"][0]], {"scale": "自然增长未被验证", "grossProfit": "付费订单可能挤压利润"}))
        else:
            skipped.append("FANG_REL_002")
    else:
        skipped.append("FANG_REL_002")

    if inventory_diagnosis.get("clearanceCandidate") and safe_number(sales.get("targetDailyUnits")) is None:
        findings.append(_finding("FANG_REL_003", "高库存缺乏消化依据", "P0", "probable", "库存风险已发生，但缺少目标日销量、流量、价格或活动计划，库存投入缺乏可验证的消化依据。", inventory_diagnosis.get("evidence", []), {"turnover": "无法证明库存可在目标周期内释放", "cashFlow": "新增投入可能扩大占资"}))
    else:
        skipped.append("FANG_REL_003")

    if profitability_diagnosis.get("isNegative") and (safe_number(sales.get("units14d")) or 0) > 0:
        findings.append(_finding("FANG_REL_004", "规模正在放大亏损", "P0", "confirmed", "存在实际销量但毛利润为负，继续扩大销量会放大经营亏损。", profitability_diagnosis.get("evidence", []) + sales_diagnosis.get("evidence", []), {"scale": "销量增长不等于有效规模", "grossProfit": "每个经营周期继续产生负贡献"}))
    else:
        skipped.append("FANG_REL_004")

    traffic = int(safe_number(roles.get("trafficSkuCount")) or 0)
    core = int(safe_number(roles.get("coreSkuCount")) or 0)
    profit = int(safe_number(roles.get("profitSkuCount")) or 0)
    if traffic > 0 and core == 0 and profit == 0:
        findings.append(_finding("FANG_REL_005", "父体流量没有形成承接与利润沉淀", "P1", "confirmed", "存在引流SKU，但主力SKU和利润SKU均为0；流量尚未证明能够转化为父体规模与利润。", sku_structure.get("evidence", []), {"scale": "缺少稳定承接SKU", "grossProfit": "没有利润SKU沉淀资源回报"}))
    else:
        skipped.append("FANG_REL_005")

    sku_count = int(safe_number(data.get("scope", {}).get("skuCount")) or 0)
    inefficient = int(safe_number(roles.get("inefficientSkuCount")) or 0)
    inefficient_share = inefficient / sku_count if sku_count else 0
    if inefficient_share >= inefficient_warning and ((safe_number(advertising.get("spend")) or 0) > 0 or (safe_number(inventory.get("totalInventory")) or 0) > 0):
        findings.append(_finding("FANG_REL_006", "低效SKU仍在占用经营资源", "P1", "confirmed", "低效SKU占比较高，但库存或广告资源仍在投入，形成资源错配。", sku_structure.get("evidence", []), {"turnover": "低效库存占资", "grossProfit": "资源回报被稀释"}))
    else:
        skipped.append("FANG_REL_006")

    if sales_diagnosis.get("belowTarget") and (safe_number(inventory.get("availableDays")) or 0) > critical_days:
        findings.append(_finding("FANG_REL_007", "当前经营方式无法实现周转目标", "P0", "confirmed", "当前日销量显著低于目标日销量，同时库存天数超过严重阈值，按当前方式无法在目标周期内完成周转。", sales_diagnosis.get("evidence", []) + inventory_diagnosis.get("evidence", []), {"turnover": "库存消化周期显著超标", "cashFlow": "资金回收速度低于目标"}))
    else:
        skipped.append("FANG_REL_007")

    acos = normalize_percentage(advertising.get("acos"))
    spend = safe_number(advertising.get("spend")) or 0
    if acos is not None and acos >= high_acos and spend < min_spend:
        findings.append(_finding("FANG_REL_008", "广告效率样本不足", "P3", "confirmed", "ACoS数值偏高，但广告绝对花费低于可靠阈值，广告不能被定义为当前主要矛盾。", advertising_diagnosis.get("evidence", []), {"grossProfit": "绝对影响有限", "scale": "样本不足以判断扩量能力"}))
    else:
        skipped.append("FANG_REL_008")

    ad_errors = [issue for issue in validation.issues if issue.severity == "error" and issue.code.startswith(("AD_", "ACOS", "TACOAS"))]
    if ad_errors:
        evidence = [build_evidence("FANG_REL_009", "confirmed", [issue.field for issue in ad_errors], "字段交叉校验", "任一关键广告字段冲突", "广告字段之间的数学与业务一致性", {"issueCodes": [issue.code for issue in ad_errors]}, "广告数据不可直接用于确定性决策。")]
        findings.append(_finding("FANG_REL_009", "广告数据口径冲突", "P0", "confirmed", "广告字段互相冲突，错误口径可能导致错误停投或扩量决策。", evidence, {"grossProfit": "无法可靠判断广告利润影响", "scale": "无法可靠判断广告增量"}))
    else:
        skipped.append("FANG_REL_009")

    inventory_91 = safe_number(inventory.get("inventory91to180")) or 0
    inventory_180 = safe_number(inventory.get("inventory180Plus")) or 0
    if inventory_91 == 0 and inventory_180 > 0:
        evidence = [build_evidence("FANG_REL_010", "confirmed", ["inventory.inventory91to180", "inventory.inventory180Plus"], "分库龄段直接比较", "inventory180Plus>0", "更严重库龄优先于较轻区间", {"inventory91to180": inventory_91, "inventory180Plus": inventory_180}, "91-180天库存为0不能解释为库存安全。")]
        findings.append(_finding("FANG_REL_010", "180天以上库存不能被较轻区间掩盖", "P0", "confirmed", "91-180天库存为0，但180天以上库存仍然很高；必须优先处理更严重的老化库存。", evidence, {"turnover": "库存已跨过更严重老化区间", "cashFlow": "不可逆仓储和清理成本继续增加"}))
    else:
        skipped.append("FANG_REL_010")
    return findings, skipped


def _finding(code: str, title: str, severity: str, status: str, description: str, evidence: list[Any], impact: dict[str, str]) -> RelationshipFinding:
    return RelationshipFinding(code=code, title=title, severity=severity, status=status, description=description, evidence=evidence, business_impact=impact)

