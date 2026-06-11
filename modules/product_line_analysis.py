from __future__ import annotations

import pandas as pd

from .aggregation import aggregate_dimension
from .spu_analysis import _status_and_recommendation


def _prepare_dimension(df: pd.DataFrame, column: str, label: str, thresholds: dict | None = None) -> pd.DataFrame:
    summary = aggregate_dimension(df, column, label)
    if summary.empty:
        return summary
    high_sales_threshold = summary["sales_14d_amount"].quantile(0.8) if "sales_14d_amount" in summary.columns else 0
    pairs = summary.apply(lambda row: _status_and_recommendation(row, high_sales_threshold, thresholds), axis=1)
    summary["line_status"] = [pair[0] for pair in pairs]
    summary["operation_recommendation"] = [pair[1] for pair in pairs]
    return summary


def analyze_product_lines(df: pd.DataFrame, thresholds: dict | None = None) -> pd.DataFrame:
    parts = [
        _prepare_dimension(df, "product_line", "product_line", thresholds),
        _prepare_dimension(df, "category_level_1", "category_level_1", thresholds),
    ]
    parts = [part for part in parts if not part.empty]
    if not parts:
        return pd.DataFrame()
    summary = pd.concat(parts, ignore_index=True)
    ordered = [
        "dimension_type",
        "dimension_value",
        "line_status",
        "operation_recommendation",
        "sku_count",
        "parent_count",
        "spu",
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
        "acoas",
        "order_gross_margin",
        "aged_inventory_90_plus",
        "aged_inventory_181_plus",
        "recent_sales_trend",
    ]
    for column in ordered:
        if column not in summary.columns:
            summary[column] = pd.NA
    return summary[ordered]
