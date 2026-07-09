from __future__ import annotations

from typing import Any

from .contradiction_detector import detect_contradictions
from .types import DiagnosisInput, RelationshipFinding, ValidationResult


def analyze_relationships(
    data: DiagnosisInput,
    config: dict[str, Any],
    validation: ValidationResult,
    inventory_diagnosis: dict[str, Any],
    advertising_diagnosis: dict[str, Any],
    profitability_diagnosis: dict[str, Any],
    sales_diagnosis: dict[str, Any],
    sku_structure: dict[str, Any],
) -> tuple[list[RelationshipFinding], list[str]]:
    findings, skipped = detect_contradictions(data, config, validation, inventory_diagnosis, advertising_diagnosis, profitability_diagnosis, sales_diagnosis, sku_structure)
    roles = sku_structure.get("roleCounts", {})
    if (
        inventory_diagnosis.get("clearanceCandidate")
        and sales_diagnosis.get("belowTarget")
        and profitability_diagnosis.get("isNegative")
        and int(roles.get("core", 0)) == 0
    ):
        composite_evidence = (
            inventory_diagnosis.get("evidence", [])
            + sales_diagnosis.get("evidence", [])
            + profitability_diagnosis.get("evidence", [])
            + sku_structure.get("evidence", [])
        )
        findings.append(
            RelationshipFinding(
                code="FANG_CORE_001",
                title="高库龄、低动销、负毛利且无主力SKU",
                severity="P0",
                status="confirmed" if validation.confidence != "low" else "probable",
                description="库存老化、销售动能不足、经营结果为负和角色断层同时发生，当前核心任务是库存退出与经营止损，而不是补货或扩大规模。",
                evidence=composite_evidence,
                business_impact={"turnover": "库存无法按当前速度释放", "scale": "缺少主力SKU承接规模", "grossProfit": "当前经营结果为负", "cashFlow": "库存持续占用现金"},
            )
        )
    return findings, skipped

