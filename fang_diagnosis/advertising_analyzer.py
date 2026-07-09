from __future__ import annotations

from typing import Any

from .config import threshold
from .evidence_builder import build_evidence
from .metric_normalizer import normalize_percentage, safe_number
from .types import DiagnosisInput, ValidationResult


def analyze_advertising(data: DiagnosisInput, config: dict[str, Any], validation: ValidationResult) -> dict[str, Any]:
    advertising = data.get("advertising", {})
    spend = safe_number(advertising.get("spend"))
    attributed_sales = safe_number(advertising.get("attributedSales"))
    acos = normalize_percentage(advertising.get("acos"))
    tacoas = normalize_percentage(advertising.get("tacoas"))
    clicks = safe_number(advertising.get("clicks"))
    min_spend = threshold(config, ("advertising", "minimum_spend_for_reliable_acos")) or 0
    min_clicks = threshold(config, ("advertising", "minimum_clicks_for_reliable_cvr")) or 0
    data_conflict = "advertising" in validation.blocked_fields or any(
        issue.code.startswith(("AD_", "ACOS", "TACOAS")) and issue.severity == "error"
        for issue in validation.issues
    )
    reliable_sample = bool((spend or 0) >= min_spend and (clicks or 0) >= min_clicks and not data_conflict)
    is_core_problem = bool(reliable_sample and (acos or 0) > 0)

    if data_conflict:
        summary = "广告字段存在口径冲突，当前只能确认花费与销售额事实，不能把广告归因为核心经营问题。"
        status = "unknown"
    elif not reliable_sample:
        summary = f"ACoS为{acos:.2%}；但广告绝对花费仅{spend or 0:,.2f}，低于可靠样本阈值{min_spend:,.0f}，广告不是当前核心矛盾。" if acos is not None else f"广告花费{spend or 0:,.2f}低于可靠样本阈值{min_spend:,.0f}，样本不足。"
        status = "confirmed"
    else:
        summary = f"广告花费{spend:,.2f}、广告销售额{attributed_sales or 0:,.2f}、ACoS {acos:.2%}，样本达到诊断阈值。"
        status = "probable"

    evidence = [
        build_evidence(
            "FANG_AD_001",
            status,
            ["advertising.spend", "advertising.attributedSales", "advertising.acos", "advertising.clicks"],
            "acos = spend / attributedSales",
            f"minimumSpend={min_spend:g}; minimumClicks={min_clicks:g}",
            "先判断数据可信度与绝对样本，再判断效率",
            {"spend": spend, "attributedSales": attributed_sales, "acos": acos, "tacoas": tacoas, "clicks": clicks},
            summary,
        )
    ]
    findings = [summary]
    if data_conflict:
        findings.append("先核对广告订单、点击、CTR、CPC、广告CVR和归因窗口，再讨论投放调整。")
    elif not reliable_sample:
        findings.append("不得仅因ACoS偏高就提升广告问题优先级。")
    return {
        "summary": summary,
        "isCoreProblem": is_core_problem,
        "sampleReliable": reliable_sample,
        "dataConflict": data_conflict,
        "findings": findings,
        "evidence": evidence,
    }

