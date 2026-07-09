from __future__ import annotations

from typing import Any

from .config import threshold
from .evidence_builder import build_evidence
from .metric_normalizer import safe_divide, safe_number
from .types import DiagnosisInput, Evidence, ValidationResult


def analyze_inventory(data: DiagnosisInput, config: dict[str, Any], validation: ValidationResult) -> dict[str, Any]:
    inventory = data.get("inventory", {})
    sales = data.get("sales", {})
    total = safe_number(inventory.get("totalInventory"))
    available = safe_number(inventory.get("availableInventory"))
    current_daily = safe_number(sales.get("currentDailyUnits"))
    target_daily = safe_number(sales.get("targetDailyUnits"))
    current_days = safe_number(inventory.get("availableDays"))
    calculated_current_days = safe_divide(available, current_daily)
    target_days = safe_divide(available, target_daily)
    inventory_90 = safe_number(inventory.get("inventory90PlusCount"))
    inventory_180 = safe_number(inventory.get("inventory180Plus"))
    share_90 = safe_number(inventory.get("inventory90PlusShare"))
    replenishment = safe_number(inventory.get("recommendedReplenishment"))

    critical_days = threshold(config, ("inventory", "critical_days")) or 0
    target_share = threshold(config, ("inventory", "target_90_plus_share")) or 0
    release_qty = None
    if inventory_90 is not None and total is not None:
        release_qty = max(inventory_90 - total * target_share, 0)

    evidence: list[Evidence] = []
    if current_days is not None:
        evidence.append(
            build_evidence(
                "FANG_INV_001",
                "confirmed" if "inventory.availableDays" not in validation.blocked_fields else "unknown",
                ["inventory.availableDays", "inventory.availableInventory", "sales.currentDailyUnits"],
                "availableInventory / currentDailyUnits",
                f"criticalDays={critical_days:g}",
                "当前可售库存天数与严重库存阈值比较",
                {"reportedDays": current_days, "calculatedDays": calculated_current_days, "availableInventory": available, "currentDailyUnits": current_daily},
                f"当前报告口径可售库存天数为{current_days:.0f}天。",
            )
        )
    if target_days is not None:
        evidence.append(
            build_evidence(
                "FANG_INV_002",
                "confirmed",
                ["inventory.availableInventory", "sales.targetDailyUnits"],
                "availableInventory / targetDailyUnits",
                "使用输入目标日销量",
                "按目标速度测算库存消化周期",
                {"availableInventory": available, "targetDailyUnits": target_daily, "targetDays": target_days},
                f"即使达到目标日销量{target_daily:.2f}件，现有库存仍需约{round(target_days):.0f}天消化。",
            )
        )

    findings: list[str] = []
    if current_days is not None:
        findings.append(f"当前口径可售库存可支撑约{current_days:.0f}天。")
    if target_days is not None:
        findings.append(f"即使达到目标日销量{target_daily:.2f}件，现有库存仍需约{round(target_days):.0f}天消化。")
    if inventory_180 is not None and inventory_180 > 0:
        findings.append(f"180天以上库存为{inventory_180:,.0f}件，优先级高于91-180天库存是否为0。")
    if release_qty is not None and release_qty > 0:
        findings.append(f"若要把90天以上库存占比压至{target_share:.0%}，按当前口径至少需释放约{release_qty:,.0f}件库存。")
    if replenishment == 0:
        findings.append("系统建议补货量为0，不应新增库存投入。")

    stop_replenishment = bool((current_days or 0) > critical_days or (inventory_180 or 0) > 0)
    summary = "；".join(findings[:3]) if findings else "库存数据不足，无法形成确定性周转结论。"
    return {
        "summary": summary,
        "currentDays": current_days,
        "calculatedCurrentDays": calculated_current_days,
        "targetDays": target_days,
        "targetDailyUnits": target_daily,
        "releaseQuantityToTarget": release_qty,
        "shouldReplenish": bool((replenishment or 0) > 0 and not stop_replenishment),
        "shouldStopReplenishment": stop_replenishment,
        "clearanceCandidate": bool((inventory_180 or 0) > 0 or (current_days or 0) > critical_days),
        "findings": findings,
        "evidence": evidence,
    }

