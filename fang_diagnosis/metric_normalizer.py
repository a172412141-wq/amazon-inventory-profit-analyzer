from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from .types import DiagnosisInput


def safe_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def normalize_percentage(value: Any) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    text = str(value).strip()
    has_percent = text.endswith("%")
    if has_percent:
        text = text[:-1]
    number = safe_number(text)
    if number is None:
        return None
    if has_percent or abs(number) > 2:
        return number / 100
    return number


def safe_divide(numerator: Any, denominator: Any) -> float | None:
    left = safe_number(numerator)
    right = safe_number(denominator)
    if left is None or right is None or right == 0:
        return None
    return left / right


def _sum(df: pd.DataFrame, column: str) -> float | None:
    if column not in df.columns:
        return None
    value = pd.to_numeric(df[column], errors="coerce").sum(min_count=1)
    return safe_number(value)


def _metric(metrics: dict[str, Any], name: str) -> float | None:
    return safe_number(metrics.get(name))


def _text(row: pd.Series, field: str) -> str | None:
    value = row.get(field)
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def build_diagnosis_input(
    full_df: pd.DataFrame,
    overview_metrics: dict[str, Any],
    mapping_report: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> DiagnosisInput:
    source = full_df.copy()
    report = mapping_report or {}
    meta = dict(metadata or {})
    meta.setdefault("analysisPeriodDays", 14)
    meta.setdefault("generatedAt", datetime.now(timezone.utc).isoformat())

    missing_fields = set(report.get("missing_fields", []))
    source_presence: dict[str, bool] = {}
    for column in source.columns:
        if column.startswith("_missing_"):
            continue
        missing_flag = f"_missing_{column}"
        has_row_value = True
        if missing_flag in source.columns:
            has_row_value = bool((~source[missing_flag].fillna(True).astype(bool)).any())
        source_presence[column] = column not in missing_fields and has_row_value

    sku_details: list[dict[str, Any]] = []
    for _, row in source.iterrows():
        sku_details.append(
            {
                "sku": _text(row, "sku") or "",
                "asin": _text(row, "asin"),
                "parentAsin": _text(row, "parent_asin"),
                "spu": _text(row, "spu"),
                "productLine": _text(row, "product_line"),
                "size": _text(row, "size") or _text(row, "category_level_3"),
                "color": _text(row, "color"),
                "price": safe_number(row.get("price")),
                "units14d": safe_number(row.get("sales_14d_units")),
                "dailyUnits": safe_number(row.get("current_daily_sales_units")),
                "salesAmount": safe_number(row.get("sales_14d_amount")),
                "grossProfit": safe_number(row.get("order_gross_profit")),
                "grossMargin": normalize_percentage(row.get("order_gross_margin")),
                "adSpend": safe_number(row.get("ad_spend")),
                "adSales": safe_number(row.get("ad_sales")),
                "acos": normalize_percentage(row.get("acos")),
                "inventory": safe_number(row.get("available_stock_qty")),
                "availableDays": safe_number(row.get("available_stock_days")),
                "inventoryAge": safe_number(row.get("aged_inventory_90_plus")),
                "role": _text(row, "sku_role"),
                "finalAction": _text(row, "final_action"),
                "systemPriority": _text(row, "priority"),
            }
        )

    return DiagnosisInput(
        metadata=meta,
        scope={
            "skuCount": int(_metric(overview_metrics, "SKU 总数") or len(source)),
            "parentCount": int(_metric(overview_metrics, "父体数") or 0),
            "spuCount": int(_metric(overview_metrics, "SPU 数") or 0),
            "productLineCount": int(_metric(overview_metrics, "品线数") or 0),
        },
        sales={
            "salesAmount14d": _metric(overview_metrics, "14天销售额"),
            "units14d": _metric(overview_metrics, "14天销量"),
            "currentDailyUnits": _metric(overview_metrics, "目前日均销量"),
            "currentDailyRevenue": _metric(overview_metrics, "目前日均销售额"),
            "targetDailyUnits": _metric(overview_metrics, "理想周转情况下日销量"),
        },
        advertising={
            "spend": _metric(overview_metrics, "总广告花费"),
            "attributedSales": _metric(overview_metrics, "广告销售额"),
            "acos": normalize_percentage(overview_metrics.get("整体 ACOS")),
            "tacoas": normalize_percentage(overview_metrics.get("整体 ACOAS")),
            "adOrderShare": normalize_percentage(overview_metrics.get("广告订单占比")),
            "cpc": _metric(overview_metrics, "CPC"),
            "ctr": normalize_percentage(overview_metrics.get("CTR")),
            "cvr": normalize_percentage(overview_metrics.get("CVR")),
            "adCvr": normalize_percentage(overview_metrics.get("广告CVR")),
            "clicks": _sum(source, "ad_clicks"),
            "impressions": _sum(source, "ad_impressions"),
            "adOrders": _sum(source, "ad_orders"),
        },
        profitability={
            "grossProfit": _metric(overview_metrics, "订单毛利润"),
            "grossMargin": normalize_percentage(overview_metrics.get("平均毛利率")),
            "contributionProfit": _metric(overview_metrics, "贡献利润"),
            "profitIncludesAdvertising": meta.get("profitIncludesAdvertising"),
            "profitIncludesStorage": meta.get("profitIncludesStorage"),
            "profitIncludesRefunds": meta.get("profitIncludesRefunds"),
        },
        inventory={
            "totalInventory": _metric(overview_metrics, "总库存/总供给"),
            "availableInventory": _sum(source, "available_stock_qty"),
            "inboundInventory": _sum(source, "inbound_qty"),
            "availableDays": _metric(overview_metrics, "可售库存天数"),
            "inventory61to90": _metric(overview_metrics, "61-90天可售库存量"),
            "inventory91to180": _metric(overview_metrics, "91-180天可售库存量"),
            "inventory180Plus": _metric(overview_metrics, "180天+可售库存量"),
            "inventory90PlusCount": _metric(overview_metrics, "库龄超过90天合计数量"),
            "inventory90PlusShare": normalize_percentage(overview_metrics.get("90天+库存占比")),
            "recommendedReplenishment": _metric(overview_metrics, "建议补货总量"),
        },
        skuRoles={
            "trafficSkuCount": int(_metric(overview_metrics, "引流 SKU 数") or 0),
            "coreSkuCount": int(_metric(overview_metrics, "主力 SKU 数") or 0),
            "profitSkuCount": int(_metric(overview_metrics, "利润 SKU 数") or 0),
            "inefficientSkuCount": int(_metric(overview_metrics, "低效异常 SKU 数") or 0),
            "clearanceRiskSkuCount": int(_metric(overview_metrics, "清货风险 SKU 数") or 0),
            "stopReplenishmentSkuCount": int(_metric(overview_metrics, "禁止补货 SKU 数") or 0),
            "urgentReplenishmentSkuCount": int(_metric(overview_metrics, "立即补货 SKU 数") or 0),
        },
        skuDetails=sku_details,
        sourcePresence=source_presence,
    )

