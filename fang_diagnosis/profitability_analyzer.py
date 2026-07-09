from __future__ import annotations

from typing import Any

from .config import threshold
from .evidence_builder import build_evidence
from .metric_normalizer import normalize_percentage, safe_number
from .types import DiagnosisInput, ValidationResult


def analyze_profitability(data: DiagnosisInput, config: dict[str, Any], validation: ValidationResult) -> dict[str, Any]:
    profitability = data.get("profitability", {})
    inventory = data.get("inventory", {})
    advertising = data.get("advertising", {})
    gross_profit = safe_number(profitability.get("grossProfit"))
    gross_margin = normalize_percentage(profitability.get("grossMargin"))
    contribution = safe_number(profitability.get("contributionProfit"))
    negative_threshold = threshold(config, ("profitability", "negative_profit")) or 0
    margin_conflict = "profitability.grossMargin" in validation.blocked_fields
    old_inventory = safe_number(inventory.get("inventory180Plus")) or 0
    ad_spend = safe_number(advertising.get("spend")) or 0

    findings: list[str] = []
    if gross_profit is None:
        summary = "毛利润缺失，无法判断经营实际贡献。"
        status = "unknown"
    elif gross_profit < negative_threshold:
        summary = f"订单毛利润为{gross_profit:,.2f}，经营结果为负。"
        status = "confirmed"
        findings.append("毛利润为负，规模扩张会放大亏损。")
        if old_inventory > 0:
            findings.append("负毛利润与180天以上库存同时存在，应先止损并释放库存。")
    else:
        summary = f"订单毛利润为{gross_profit:,.2f}，当前形成正向绝对贡献。"
        status = "confirmed"
    if margin_conflict:
        findings.append("毛利润与毛利率口径冲突，毛利率只能作为待核对字段，不能用于确定性归因。")
    elif gross_margin is not None:
        findings.append(f"平均毛利率为{gross_margin:.2%}，仅代表利润空间，不替代毛利润与周转判断。")
    if contribution is None:
        findings.append("贡献利润未提供，无法确认广告、仓储、促销和退款后的真实贡献。")

    evidence = [
        build_evidence(
            "FANG_PROFIT_001",
            status,
            ["profitability.grossProfit", "profitability.grossMargin", "profitability.contributionProfit", "inventory.inventory180Plus", "advertising.spend"],
            "grossMargin reference = grossProfit / salesAmount",
            f"negativeProfit<{negative_threshold:g}",
            "同时比较绝对利润、利润率、广告和库存老化",
            {"grossProfit": gross_profit, "grossMargin": gross_margin, "contributionProfit": contribution, "inventory180Plus": old_inventory, "adSpend": ad_spend},
            summary,
        )
    ]
    return {"summary": summary, "findings": findings, "evidence": evidence, "isNegative": bool(gross_profit is not None and gross_profit < negative_threshold), "marginConflict": margin_conflict}

