from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .recommendations import sort_by_priority_action


ROLE_ORDER = ["引流 SKU", "主力 SKU", "利润 SKU", "低效异常 SKU"]
ROLE_REPORT_KEYS = {
    "traffic_skus": "引流 SKU",
    "main_skus": "主力 SKU",
    "profit_skus": "利润 SKU",
    "low_efficiency_skus": "低效异常 SKU",
}

ROLE_REPORT_COLUMNS = [
    "sku",
    "parent_asin",
    "role_parent_key",
    "spu",
    "product_line",
    "sku_role",
    "sku_role_candidates",
    "sku_role_reason",
    "sku_sales_share_in_parent",
    "sku_revenue_share_in_parent",
    "sku_ad_spend_share_in_parent",
    "sku_profit_share_in_parent",
    "sku_stock_share_in_parent",
    "role_daily_sales",
    "parent_avg_role_daily_sales",
    "parent_order_gross_margin",
    "parent_avg_sales_14d_units",
    "parent_avg_order_gross_margin",
    "sales_14d_units",
    "sales_14d_amount",
    "ad_spend",
    "ad_sales",
    "ad_order_share",
    "order_gross_profit",
    "order_gross_margin",
    "acos",
    "available_stock_qty",
    "aged_inventory_90_plus",
    "aged_inventory_181_plus",
    "available_stock_days",
    "stock_days",
    "recommended_replenishment_qty",
    "final_action",
    "priority",
    "reason",
]

def _threshold(thresholds: dict[str, Any] | None, path: tuple[str, ...], default: float) -> float:
    current: Any = thresholds or {}
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return float(current)


def _numeric(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce")


def _text(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series("", index=df.index, dtype="string")
    return df[column].astype("string").fillna("").str.strip()


def _safe_share(values: pd.Series, totals: pd.Series) -> pd.Series:
    values = pd.to_numeric(values, errors="coerce").fillna(0.0)
    totals = pd.to_numeric(totals, errors="coerce").fillna(0.0)
    return values.div(totals.where(totals > 0)).fillna(0.0)


def _role_daily_sales(df: pd.DataFrame, sales_14d_units: pd.Series) -> pd.Series:
    daily_sales = _numeric(df, "current_daily_sales_units", np.nan)
    if "current_daily_sales_units" not in df.columns:
        daily_sales = pd.Series(np.nan, index=df.index, dtype="float64")
    daily_sales = daily_sales.where(daily_sales.notna(), sales_14d_units / 14)
    return daily_sales.fillna(0.0)


def _parent_margin(
    gross_profit: pd.Series,
    sales_7d_amount: pd.Series,
    sales_14d_amount: pd.Series,
    group: pd.Series,
) -> pd.Series:
    parent_profit = gross_profit.fillna(0.0).groupby(group).transform("sum")
    parent_sales = sales_7d_amount.fillna(0.0).groupby(group).transform("sum")
    fallback_sales = sales_14d_amount.fillna(0.0).groupby(group).transform("sum")
    parent_sales = parent_sales.where(parent_sales > 0, fallback_sales)
    return parent_profit.div(parent_sales.where(parent_sales > 0))


def _role_parent_key(df: pd.DataFrame) -> pd.Series:
    parent = _text(df, "parent_asin")
    sku = _text(df, "sku")
    fallback = "未分组-" + sku.where(sku != "", pd.Series(df.index.astype(str), index=df.index))
    return parent.where(parent != "", fallback)


def _candidate_labels(row: pd.Series) -> str:
    labels: list[str] = []
    if bool(row.get("_traffic_candidate", False)):
        labels.append("引流候选")
    if bool(row.get("_main_candidate", False)):
        labels.append("主力候选")
    if bool(row.get("_profit_candidate", False)):
        labels.append("利润候选")
    if bool(row.get("_low_efficiency_candidate", False)):
        labels.append("低效异常候选")
    if not labels:
        labels.append("兜底归类")
    return "；".join(labels)


def _role_reason(row: pd.Series) -> str:
    sales_share = row.get("sku_sales_share_in_parent", 0.0)
    ad_share = row.get("sku_ad_spend_share_in_parent", 0.0)
    daily_sales = row.get("role_daily_sales", np.nan)
    margin = row.get("order_gross_margin", np.nan)
    parent_avg_daily_sales = row.get("parent_avg_role_daily_sales", np.nan)
    parent_margin = row.get("parent_order_gross_margin", np.nan)
    role = row.get("sku_role", "")
    candidates = row.get("sku_role_candidates", "")
    base = f"父体内广告花费占比 {ad_share:.2%}，销量占比 {sales_share:.2%}"
    if not pd.isna(daily_sales) and not pd.isna(parent_avg_daily_sales):
        base += f"，日均销量 {float(daily_sales):.2f} / 父体日均销量平均值 {float(parent_avg_daily_sales):.2f}"
    if not pd.isna(margin) and not pd.isna(parent_margin):
        base += f"，毛利率 {float(margin):.2%} / 父体毛利率 {float(parent_margin):.2%}"

    if role == "低效异常 SKU":
        return base + f"；命中 {candidates}，不满足引流、主力或利润 SKU 条件。"
    if role == "主力 SKU":
        return base + f"；命中 {candidates}，销量和毛利率均高于父体平均值。"
    if role == "利润 SKU":
        return base + f"；命中 {candidates}，毛利率高于父体平均值 50% 以上。"
    return base + f"；命中 {candidates}，广告花费占父体总花费超过 35%。"


def _final_role(row: pd.Series) -> str:
    if bool(row.get("_traffic_candidate", False)):
        return "引流 SKU"
    if bool(row.get("_main_candidate", False)):
        return "主力 SKU"
    if bool(row.get("_profit_candidate", False)):
        return "利润 SKU"
    return "低效异常 SKU"


def classify_sku_roles(df: pd.DataFrame, thresholds: dict[str, Any] | None = None) -> pd.DataFrame:
    result = df.copy()
    if result.empty:
        result["sku_role"] = pd.Series(dtype="string")
        result["sku_role_candidates"] = pd.Series(dtype="string")
        result["sku_role_reason"] = pd.Series(dtype="string")
        return result

    role_parent_key = _role_parent_key(result)
    result["role_parent_key"] = role_parent_key
    result["parent_sku_count"] = _text(result, "sku").groupby(role_parent_key).transform("nunique")

    sales_units = _numeric(result, "sales_14d_units")
    daily_sales = _role_daily_sales(result, sales_units)
    sales_amount = _numeric(result, "sales_14d_amount")
    sales_7d_amount = _numeric(result, "sales_7d_amount", np.nan)
    ad_spend = _numeric(result, "ad_spend")
    ad_impressions = _numeric(result, "ad_impressions")
    ad_clicks = _numeric(result, "ad_clicks")
    gross_profit = _numeric(result, "order_gross_profit", np.nan)
    margin = _numeric(result, "order_gross_margin", np.nan)
    stock_qty = _numeric(result, "available_stock_qty")

    group = role_parent_key
    result["sku_sales_share_in_parent"] = _safe_share(sales_units, sales_units.groupby(group).transform("sum"))
    result["sku_revenue_share_in_parent"] = _safe_share(sales_amount, sales_amount.groupby(group).transform("sum"))
    result["sku_ad_spend_share_in_parent"] = _safe_share(ad_spend, ad_spend.groupby(group).transform("sum"))
    result["sku_impression_share_in_parent"] = _safe_share(ad_impressions, ad_impressions.groupby(group).transform("sum"))
    result["sku_click_share_in_parent"] = _safe_share(ad_clicks, ad_clicks.groupby(group).transform("sum"))
    result["sku_profit_share_in_parent"] = _safe_share(gross_profit.clip(lower=0), gross_profit.clip(lower=0).groupby(group).transform("sum"))
    result["sku_stock_share_in_parent"] = _safe_share(stock_qty, stock_qty.groupby(group).transform("sum"))
    result["role_daily_sales"] = daily_sales
    result["parent_avg_role_daily_sales"] = daily_sales.groupby(group).transform("mean")
    result["parent_order_gross_margin"] = _parent_margin(gross_profit, sales_7d_amount, sales_amount, group)
    result["parent_avg_sales_14d_units"] = sales_units.groupby(group).transform("mean")
    result["parent_avg_order_gross_margin"] = margin.groupby(group).transform("mean")

    traffic_ad_share = _threshold(thresholds, ("sku_roles", "traffic_ad_spend_share"), 0.35)
    profit_margin_multiplier = _threshold(thresholds, ("sku_roles", "profit_margin_multiplier"), 1.50)

    ad_share = result["sku_ad_spend_share_in_parent"]
    parent_avg_daily_sales = result["parent_avg_role_daily_sales"]
    parent_margin = result["parent_order_gross_margin"]

    result["_traffic_candidate"] = ad_share > traffic_ad_share
    result["_main_candidate"] = (daily_sales > parent_avg_daily_sales) & (margin > parent_margin)
    result["_profit_candidate"] = (
        parent_margin.gt(0)
        & margin.ge(parent_margin * profit_margin_multiplier)
    )
    result["_low_efficiency_candidate"] = ~(
        result["_traffic_candidate"]
        | result["_main_candidate"]
        | result["_profit_candidate"]
    )

    result["sku_role_candidates"] = result.apply(_candidate_labels, axis=1)
    result["sku_role"] = result.apply(_final_role, axis=1)
    result["sku_role_reason"] = result.apply(_role_reason, axis=1)
    return result.drop(
        columns=[
            "_low_efficiency_candidate",
            "_main_candidate",
            "_profit_candidate",
            "_traffic_candidate",
        ],
        errors="ignore",
    )


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = df.copy()
    for column in columns:
        if column not in result.columns:
            result[column] = pd.NA
    return result[columns]


def _sort_role_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return _ensure_columns(df, ROLE_REPORT_COLUMNS)
    result = sort_by_priority_action(df)
    result["_role_sort"] = pd.Categorical(result["sku_role"], categories=ROLE_ORDER, ordered=True)
    result["_sales_share_sort"] = pd.to_numeric(result.get("sku_sales_share_in_parent"), errors="coerce").fillna(0.0)
    result["_profit_share_sort"] = pd.to_numeric(result.get("sku_profit_share_in_parent"), errors="coerce").fillna(0.0)
    result = result.sort_values(["_role_sort", "_sales_share_sort", "_profit_share_sort"], ascending=[True, False, False])
    return result.drop(columns=["_role_sort", "_sales_share_sort", "_profit_share_sort"], errors="ignore")


def build_sku_role_reports(df: pd.DataFrame, thresholds: dict[str, Any] | None = None) -> dict[str, pd.DataFrame]:
    source = df.copy()
    required_columns = {
        "sku_role",
        "sku_role_candidates",
        "sku_role_reason",
        "sku_sales_share_in_parent",
        "sku_profit_share_in_parent",
        "sku_stock_share_in_parent",
    }
    if not required_columns.issubset(source.columns):
        source = classify_sku_roles(source, thresholds)

    reports: dict[str, pd.DataFrame] = {}
    for key, role in ROLE_REPORT_KEYS.items():
        role_mask = source["sku_role"].astype("string").fillna("").eq(role)
        role_mask = role_mask.reindex(source.index, fill_value=False)
        selected = source.loc[role_mask].copy()
        reports[key] = _ensure_columns(_sort_role_table(selected), ROLE_REPORT_COLUMNS)
    return reports
