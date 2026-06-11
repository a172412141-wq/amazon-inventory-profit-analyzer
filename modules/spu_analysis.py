from __future__ import annotations

import pandas as pd

from .aggregation import aggregate_dimension


def _threshold(thresholds: dict | None, path: tuple[str, ...], default: float) -> float:
    current = thresholds or {}
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return float(current)


def _status_and_recommendation(row: pd.Series, high_sales_threshold: float, thresholds: dict | None = None) -> tuple[str, str]:
    sales = row.get("sales_14d_amount", 0)
    stock_days = row.get("weighted_stock_days")
    margin = row.get("order_gross_margin")
    gross_profit = row.get("order_gross_profit")
    acos = row.get("acos")
    ad_spend = row.get("ad_spend", 0)
    ad_ratio = ad_spend / sales if sales and sales > 0 else 0
    trend = row.get("recent_sales_trend", "")
    high_margin = _threshold(thresholds, ("margin", "high_margin"), 0.15)
    medium_margin = _threshold(thresholds, ("margin", "medium_margin"), 0.08)
    healthy_max_days = _threshold(thresholds, ("inventory", "healthy_max_days"), 60)
    acceleration_days = _threshold(thresholds, ("inventory", "acceleration_days"), 60)
    urgent_redline_days = _threshold(thresholds, ("inventory", "urgent_redline_days"), 180)

    healthy_stock = not pd.isna(stock_days) and 30 <= stock_days <= healthy_max_days
    high_margin_slow = not pd.isna(margin) and margin >= high_margin and not pd.isna(stock_days) and stock_days >= acceleration_days
    ad_bad = not pd.isna(acos) and not pd.isna(margin) and acos >= margin

    if not pd.isna(stock_days) and stock_days > urgent_redline_days and ((not pd.isna(gross_profit) and gross_profit <= 0) or ad_bad):
        return "清退品线", "停补清货"
    if high_margin_slow:
        recommendation = "加大投入促周转" if stock_days <= 90 else "控补货防现金流恶化"
        return "高毛利低周转品线", recommendation
    if sales >= high_sales_threshold and healthy_stock and not pd.isna(margin) and margin >= high_margin and not pd.isna(gross_profit) and gross_profit > 0:
        return "明星品线", "加资源"
    if healthy_stock and not pd.isna(margin) and margin >= medium_margin and not pd.isna(gross_profit) and gross_profit > 0 and ad_ratio < 0.10:
        return "现金牛品线", "稳定运营"
    if trend == "近期起量" and not pd.isna(stock_days) and stock_days <= 90 and not pd.isna(margin) and margin > 0:
        return "增长品线", "控风险测试"
    if sales > 0 and ((not pd.isna(gross_profit) and gross_profit <= 0) or ad_bad):
        return "问题品线", "优化广告/成本"
    return "观察品线", "稳定运营"


def analyze_spu(df: pd.DataFrame, thresholds: dict | None = None) -> pd.DataFrame:
    summary = aggregate_dimension(df, "spu")
    if summary.empty:
        return summary
    high_sales_threshold = summary["sales_14d_amount"].quantile(0.8) if "sales_14d_amount" in summary.columns else 0
    pairs = summary.apply(lambda row: _status_and_recommendation(row, high_sales_threshold, thresholds), axis=1)
    summary["spu_status"] = [pair[0] for pair in pairs]
    summary["operation_recommendation"] = [pair[1] for pair in pairs]
    ordered = [
        "spu",
        "spu_status",
        "operation_recommendation",
        "sku_count",
        "parent_count",
        "product_line",
        "sales_7d_units",
        "sales_14d_units",
        "sales_7d_amount",
        "sales_14d_amount",
        "total_supply_qty",
        "available_stock_qty",
        "available_qty",
        "inbound_qty",
        "recommended_replenishment_qty",
        "ad_spend",
        "ad_sales",
        "order_gross_profit",
        "weighted_stock_days",
        "acos",
        "order_gross_margin",
        "aged_inventory_90_plus",
        "aged_inventory_181_plus",
        "recent_sales_trend",
    ]
    for column in ordered:
        if column not in summary.columns:
            summary[column] = pd.NA
    return summary[ordered]
