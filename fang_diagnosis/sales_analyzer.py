from __future__ import annotations

from typing import Any

from .config import threshold
from .evidence_builder import build_evidence
from .metric_normalizer import safe_number
from .types import DiagnosisInput


def analyze_sales(data: DiagnosisInput, config: dict[str, Any]) -> dict[str, Any]:
    sales = data.get("sales", {})
    current = safe_number(sales.get("currentDailyUnits"))
    target = safe_number(sales.get("targetDailyUnits"))
    amount = safe_number(sales.get("salesAmount14d"))
    units = safe_number(sales.get("units14d"))
    gap_ratio = threshold(config, ("sales", "target_gap_ratio")) or 0
    achievement = current / target if current is not None and target not in {None, 0} else None
    below_target = bool(achievement is not None and achievement < gap_ratio)
    if achievement is None:
        summary = "当前日销量或目标日销量缺失，无法判断销售动能与周转目标差距。"
        status = "unknown"
    else:
        summary = f"当前日销量{current:.2f}件，目标日销量{target:.2f}件，达成率{achievement:.1%}。"
        status = "confirmed"
    evidence = [
        build_evidence(
            "FANG_SALES_001",
            status,
            ["sales.currentDailyUnits", "sales.targetDailyUnits", "sales.salesAmount14d", "sales.units14d"],
            "achievement = currentDailyUnits / targetDailyUnits",
            f"targetGapRatio={gap_ratio:.2f}",
            "当前销量速度与目标速度比较",
            {"currentDailyUnits": current, "targetDailyUnits": target, "achievement": achievement, "salesAmount14d": amount, "units14d": units},
            summary,
        )
    ]
    return {"summary": summary, "achievement": achievement, "belowTarget": below_target, "findings": [summary], "evidence": evidence}

