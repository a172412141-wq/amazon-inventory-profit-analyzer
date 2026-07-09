from __future__ import annotations

from typing import Any

from .config import threshold
from .evidence_builder import build_evidence
from .metric_normalizer import safe_divide, safe_number
from .types import DiagnosisInput, ValidationResult


STAGE_LABELS = {
    "growth": "增长阶段",
    "stable": "稳定经营阶段",
    "efficiency_optimization": "效率优化阶段",
    "inventory_reduction": "去库存阶段",
    "loss_control": "库存退出 / 经营止损阶段",
    "exit": "退出阶段",
    "insufficient_data": "数据不足",
}


def classify_lifecycle(
    data: DiagnosisInput,
    config: dict[str, Any],
    validation: ValidationResult,
    inventory_diagnosis: dict[str, Any],
    advertising_diagnosis: dict[str, Any],
    profitability_diagnosis: dict[str, Any],
    sales_diagnosis: dict[str, Any],
) -> dict[str, Any]:
    inventory = data.get("inventory", {})
    roles = data.get("skuRoles", {})
    scope = data.get("scope", {})
    critical_days = threshold(config, ("inventory", "critical_days")) or 0
    severe_days = threshold(config, ("inventory", "severe_days")) or 0
    high_180_share = threshold(config, ("inventory", "high_180_plus_share")) or 0
    current_days = safe_number(inventory_diagnosis.get("currentDays"))
    inventory_180 = safe_number(inventory.get("inventory180Plus"))
    total = safe_number(inventory.get("totalInventory"))
    inventory_180_share = safe_divide(inventory_180, total)
    core_count = int(safe_number(roles.get("coreSkuCount")) or 0)
    clearance_count = int(safe_number(roles.get("clearanceRiskSkuCount")) or 0)
    sku_count = int(safe_number(scope.get("skuCount")) or 0)

    required_present = [
        safe_number(data.get("sales", {}).get("currentDailyUnits")),
        safe_number(data.get("profitability", {}).get("grossProfit")),
        safe_number(inventory.get("availableDays")),
    ]
    if sum(value is not None for value in required_present) < 2:
        stage = "insufficient_data"
    elif profitability_diagnosis.get("isNegative") and (
        (current_days or 0) > critical_days
        or (inventory_180 or 0) > 0
        or (clearance_count > 0 and core_count == 0)
    ):
        stage = "loss_control"
    elif (current_days or 0) > critical_days or (inventory_180_share or 0) >= high_180_share:
        stage = "inventory_reduction"
    elif advertising_diagnosis.get("isCoreProblem") or sales_diagnosis.get("belowTarget"):
        stage = "efficiency_optimization"
    elif (
        profitability_diagnosis.get("isNegative") is False
        and sales_diagnosis.get("belowTarget") is False
        and (current_days or 0) <= threshold(config, ("inventory", "healthy_days_max"))
        and core_count > 0
    ):
        stage = "growth"
    else:
        stage = "stable"

    exit_candidate = bool(
        stage == "loss_control"
        and (current_days or 0) > severe_days
        and (inventory_180_share or 0) >= high_180_share
        and core_count == 0
        and sku_count > 0
        and clearance_count >= sku_count
    )
    status = "confirmed" if stage != "insufficient_data" and validation.confidence != "low" else ("probable" if stage != "insufficient_data" else "unknown")
    summary = STAGE_LABELS[stage]
    if exit_candidate:
        summary += "（退出候选，需用历史持续性数据复核）"
    evidence = [
        build_evidence(
            "FANG_STAGE_001",
            status,
            ["inventory.availableDays", "inventory.inventory180Plus", "profitability.grossProfit", "sales.currentDailyUnits", "sales.targetDailyUnits", "skuRoles.coreSkuCount", "skuRoles.clearanceRiskSkuCount"],
            "多信号规则：库存风险 + 利润结果 + 销售目标差距 + SKU结构",
            f"criticalDays={critical_days:g}; severeDays={severe_days:g}; high180Share={high_180_share:.0%}",
            "周转优先于规模、毛利润和毛利率",
            {"currentDays": current_days, "inventory180Plus": inventory_180, "inventory180Share": inventory_180_share, "coreSkuCount": core_count, "clearanceRiskSkuCount": clearance_count, "salesBelowTarget": sales_diagnosis.get("belowTarget"), "negativeProfit": profitability_diagnosis.get("isNegative")},
            f"当前识别为{summary}。",
        )
    ]
    return {"stage": stage, "confidence": validation.confidence, "summary": summary, "exitCandidate": exit_candidate, "reasons": evidence}

