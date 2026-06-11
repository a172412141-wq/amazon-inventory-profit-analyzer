from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


SUM_FIELDS = [
    "sales_7d_units",
    "sales_14d_units",
    "sales_7d_amount",
    "sales_14d_amount",
    "total_supply_qty",
    "available_qty",
    "available_stock_qty",
    "inbound_qty",
    "recommended_replenishment_qty",
    "ad_spend",
    "ad_sales",
    "order_gross_profit",
    "aged_inventory_90_plus",
    "aged_inventory_181_plus",
    "aged_inventory_91_180",
    "aged_inventory_181_270",
    "aged_inventory_271_330",
    "aged_inventory_331_365",
    "aged_inventory_365_plus",
    "main_daily_sales",
]


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _sum(group: pd.DataFrame, column: str) -> float:
    if column not in group.columns:
        return 0.0
    value = _num(group[column]).sum(min_count=1)
    if pd.isna(value):
        return 0.0
    return float(value)


def _unique_join(group: pd.DataFrame, column: str) -> str:
    if column not in group.columns:
        return ""
    values = (
        group[column]
        .dropna()
        .astype(str)
        .map(str.strip)
    )
    values = [value for value in values.unique().tolist() if value and value.lower() not in {"nan", "none"}]
    return "、".join(values[:8])


def _gross_margin_from_sales_amount(row: dict[str, Any]) -> float:
    gross_profit = row.get("order_gross_profit", 0.0)
    sales_amount = row.get("sales_7d_amount", 0.0)
    if sales_amount <= 0:
        sales_amount = row.get("sales_14d_amount", 0.0)
    return float(gross_profit / sales_amount) if sales_amount > 0 else np.nan


def aggregate_dimension(df: pd.DataFrame, group_col: str, dimension_type: str | None = None) -> pd.DataFrame:
    if group_col not in df.columns:
        return pd.DataFrame()

    source = df.copy()
    source[group_col] = source[group_col].astype("string").fillna("").str.strip()
    source = source[source[group_col] != ""]
    if source.empty:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for group_value, group in source.groupby(group_col, dropna=False):
        row: dict[str, Any] = {group_col: group_value}
        if dimension_type:
            row["dimension_type"] = dimension_type
            row["dimension_value"] = group_value

        row["sku_count"] = int(group["sku"].nunique()) if "sku" in group.columns else int(len(group))
        row["parent_count"] = int(group["parent_asin"].nunique()) if "parent_asin" in group.columns else 0
        row["spu"] = _unique_join(group, "spu")
        row["product_line"] = _unique_join(group, "product_line")

        for field in SUM_FIELDS:
            if field == "main_daily_sales":
                continue
            row[field] = _sum(group, field)

        avg_sales_7d_sum = row.get("sales_7d_units", 0.0) / 7
        available_stock = row.get("available_stock_qty", row.get("available_qty", 0.0))
        row["weighted_stock_days"] = (
            available_stock / avg_sales_7d_sum
            if avg_sales_7d_sum > 0
            else (np.inf if available_stock > 0 else np.nan)
        )

        ad_sales = row.get("ad_sales", 0.0)
        ad_spend = row.get("ad_spend", 0.0)
        row["acos"] = ad_spend / ad_sales if ad_sales > 0 else (np.inf if ad_spend > 0 else np.nan)

        row["order_gross_margin"] = _gross_margin_from_sales_amount(row)

        avg_7d = row.get("sales_7d_units", 0.0) / 7
        avg_14d = row.get("sales_14d_units", 0.0) / 14
        if row.get("sales_7d_units", 0.0) == 0 and row.get("sales_14d_units", 0.0) == 0:
            row["recent_sales_trend"] = "无销量"
        elif avg_7d > avg_14d * 1.3:
            row["recent_sales_trend"] = "近期起量"
        elif avg_7d < avg_14d * 0.7:
            row["recent_sales_trend"] = "近期下滑"
        else:
            row["recent_sales_trend"] = "销量稳定"
        rows.append(row)

    return pd.DataFrame(rows)
