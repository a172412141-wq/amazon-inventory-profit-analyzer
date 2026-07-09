from __future__ import annotations

from typing import Any

from .config import threshold
from .evidence_builder import build_evidence
from .metric_normalizer import safe_number
from .types import DiagnosisInput, ValidationResult


ROLE_MAP = {"引流 SKU": "traffic", "主力 SKU": "core", "利润 SKU": "profit", "低效异常 SKU": "inefficient"}


def analyze_sku_roles(data: DiagnosisInput, config: dict[str, Any], validation: ValidationResult) -> dict[str, Any]:
    counts = dict(data.get("skuRoles", {}))
    sku_count = int(safe_number(data.get("scope", {}).get("skuCount")) or len(data.get("skuDetails", [])))
    traffic = int(safe_number(counts.get("trafficSkuCount")) or 0)
    core = int(safe_number(counts.get("coreSkuCount")) or 0)
    profit = int(safe_number(counts.get("profitSkuCount")) or 0)
    inefficient = int(safe_number(counts.get("inefficientSkuCount")) or 0)
    inefficient_share = inefficient / sku_count if sku_count else 0
    inefficient_warning = threshold(config, ("sku_roles", "inefficient_share_warning")) or 0
    critical_days = threshold(config, ("inventory", "critical_days")) or 0
    stockout_days = threshold(config, ("inventory", "stockout_days")) or 0
    status_details: list[dict[str, Any]] = []
    for item in data.get("skuDetails", []):
        tags: list[str] = []
        available_days = safe_number(item.get("availableDays"))
        gross_profit = safe_number(item.get("grossProfit"))
        if available_days is not None and available_days > critical_days:
            tags.extend(["inventory_risk", "clearance_candidate", "stop_replenishment"])
        if available_days is not None and available_days < stockout_days:
            tags.append("stockout_risk")
        if item.get("finalAction") in {"清货处理", "禁止补货", "高毛利停补"}:
            tags.append("stop_replenishment")
        if gross_profit is not None and gross_profit < 0 and "clearance_candidate" in tags:
            tags.append("exit_candidate")
        if any(issue.severity == "error" for issue in validation.issues):
            tags.append("data_anomaly")
        status_details.append({"sku": item.get("sku"), "role": ROLE_MAP.get(str(item.get("role")), "inefficient"), "statusTags": sorted(set(tags))})

    findings: list[str] = []
    if traffic > 0 and core == 0 and profit == 0:
        findings.append("存在引流SKU，但没有主力SKU和利润SKU，父体尚未形成有效流量承接与利润沉淀。")
        findings.append("引流SKU不等于优秀SKU；若没有父体带动和正向利润贡献，它当前只承担流量消耗。")
    if inefficient_share >= inefficient_warning:
        findings.append(f"低效异常SKU占比为{inefficient_share:.0%}，需要限制新增广告和库存资源。")
    if not findings:
        findings.append("SKU角色结构未出现明显断层，仍需结合父体和品线比较验证资源配置。")

    evidence = [
        build_evidence(
            "FANG_ROLE_001",
            "confirmed",
            ["skuRoles", "skuDetails.role", "skuDetails.finalAction"],
            "角色沿用现有互斥分类；状态标签由风险条件叠加",
            f"roleOrder=traffic>core>profit>inefficient; inefficientWarning={inefficient_warning:.0%}",
            "角色数量、角色断层与资源状态比较",
            {"traffic": traffic, "core": core, "profit": profit, "inefficient": inefficient, "skuCount": sku_count},
            findings[0],
        )
    ]
    return {"summary": findings[0], "roleCounts": {"traffic": traffic, "core": core, "profit": profit, "inefficient": inefficient}, "findings": findings, "skuStatuses": status_details, "evidence": evidence}

