from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .recommendations import sort_by_priority_action


ROLE_ORDER = ["主力 SKU", "利润 SKU", "引流 SKU", "低效异常 SKU"]
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
    "sales_14d_units",
    "sales_14d_amount",
    "ad_spend",
    "ad_sales",
    "ad_order_share",
    "order_gross_profit",
    "order_gross_margin",
    "acos",
    "available_stock_qty",
    "available_stock_days",
    "stock_days",
    "recommended_replenishment_qty",
    "final_action",
    "priority",
    "reason",
]

LOW_EFFICIENCY_ACTIONS = {"清货处理", "禁止补货", "高毛利停补", "暂缓补货"}


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


def _share_of_group_positive(values: pd.Series, group_key: pd.Series) -> pd.Series:
    positive_values = values.clip(lower=0).fillna(0.0)
    totals = positive_values.groupby(group_key).transform("sum")
    return _safe_share(positive_values, totals)


def _rank_top(values: pd.Series, group_key: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce").fillna(0.0)
    ranks = numeric.groupby(group_key).rank(method="first", ascending=False)
    return (ranks == 1) & (numeric > 0)


def _inventory_days(df: pd.DataFrame) -> pd.Series:
    available_days = _numeric(df, "available_stock_days", np.nan)
    stock_days = _numeric(df, "stock_days", np.nan)
    return available_days.where(available_days.notna(), stock_days)


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
    profit_share = row.get("sku_profit_share_in_parent", 0.0)
    ad_share = row.get("sku_ad_spend_share_in_parent", 0.0)
    stock_share = row.get("sku_stock_share_in_parent", 0.0)
    stock_days = row.get("available_stock_days", np.nan)
    role = row.get("sku_role", "")
    candidates = row.get("sku_role_candidates", "")
    base = (
        f"父体内销量占比 {sales_share:.2%}，毛利润占比 {profit_share:.2%}，"
        f"广告花费占比 {ad_share:.2%}，可售库存占比 {stock_share:.2%}"
    )
    if not pd.isna(stock_days):
        base += f"，可售库存天数 {float(stock_days):.1f}"

    if role == "低效异常 SKU":
        return base + f"；命中 {candidates}，优先按低效异常处理，需复核库存、利润或广告效率。"
    if role == "主力 SKU":
        return base + f"；命中 {candidates}，父体内销量/销售贡献靠前且利润为正，作为主力款管理。"
    if role == "利润 SKU":
        return base + f"；命中 {candidates}，利润贡献或毛利率较好，作为利润款管理。"
    return base + f"；命中 {candidates}，承担流量或订单承接作用，但利润效率需持续观察。"


def _final_role(row: pd.Series) -> str:
    if bool(row.get("_severe_low_efficiency_candidate", False)):
        return "低效异常 SKU"
    if bool(row.get("_main_candidate", False)):
        return "主力 SKU"
    if bool(row.get("_profit_candidate", False)):
        return "利润 SKU"
    if bool(row.get("_traffic_candidate", False)):
        return "引流 SKU"

    gross_profit = row.get("order_gross_profit", np.nan)
    sales_units = row.get("sales_14d_units", 0.0)
    ad_spend = row.get("ad_spend", 0.0)
    if not pd.isna(gross_profit) and gross_profit > 0 and sales_units > 0:
        return "利润 SKU"
    if sales_units > 0 or ad_spend > 0:
        return "引流 SKU"
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
    sales_amount = _numeric(result, "sales_14d_amount")
    ad_spend = _numeric(result, "ad_spend")
    ad_sales = _numeric(result, "ad_sales")
    ad_impressions = _numeric(result, "ad_impressions")
    ad_clicks = _numeric(result, "ad_clicks")
    gross_profit = _numeric(result, "order_gross_profit", np.nan)
    margin = _numeric(result, "order_gross_margin", np.nan)
    acos = _numeric(result, "acos", np.nan)
    stock_qty = _numeric(result, "available_stock_qty")
    total_supply = _numeric(result, "total_supply_qty")
    main_daily_sales = _numeric(result, "main_daily_sales")
    inventory_days = _inventory_days(result)

    group = role_parent_key
    result["sku_sales_share_in_parent"] = _safe_share(sales_units, sales_units.groupby(group).transform("sum"))
    result["sku_revenue_share_in_parent"] = _safe_share(sales_amount, sales_amount.groupby(group).transform("sum"))
    result["sku_ad_spend_share_in_parent"] = _safe_share(ad_spend, ad_spend.groupby(group).transform("sum"))
    result["sku_impression_share_in_parent"] = _safe_share(ad_impressions, ad_impressions.groupby(group).transform("sum"))
    result["sku_click_share_in_parent"] = _safe_share(ad_clicks, ad_clicks.groupby(group).transform("sum"))
    result["sku_profit_share_in_parent"] = _share_of_group_positive(gross_profit, group)
    result["sku_stock_share_in_parent"] = _safe_share(stock_qty, stock_qty.groupby(group).transform("sum"))

    high_share = _threshold(thresholds, ("sku_roles", "high_parent_share"), 0.30)
    medium_share = _threshold(thresholds, ("sku_roles", "medium_parent_share"), 0.20)
    low_share = _threshold(thresholds, ("sku_roles", "low_parent_share"), 0.10)
    high_stock_share = _threshold(thresholds, ("sku_roles", "high_stock_share"), 0.30)
    traffic_profit_discount = _threshold(thresholds, ("sku_roles", "traffic_profit_share_discount"), 0.70)
    high_margin = _threshold(thresholds, ("margin", "high_margin"), 0.15)
    redline_days = _threshold(thresholds, ("inventory", "redline_days"), 90)

    sales_share = result["sku_sales_share_in_parent"]
    revenue_share = result["sku_revenue_share_in_parent"]
    ad_share = result["sku_ad_spend_share_in_parent"]
    impression_share = result["sku_impression_share_in_parent"]
    click_share = result["sku_click_share_in_parent"]
    profit_share = result["sku_profit_share_in_parent"]
    stock_share = result["sku_stock_share_in_parent"]

    positive_profit = gross_profit > 0
    has_sales = sales_units > 0
    has_ads = ad_spend > 0
    ad_no_conversion = has_ads & (ad_sales <= 0)
    ad_loss = has_ads & margin.notna() & acos.notna() & (acos >= margin)
    stock_abnormal = (inventory_days > redline_days) | (inventory_days.map(np.isposinf) & (stock_qty > 0))
    no_sales_stock = (main_daily_sales <= 0) & (total_supply > 0)
    low_sales_high_stock = (sales_share <= low_share) & (stock_share >= high_stock_share) & (stock_qty > 0)
    final_action = _text(result, "final_action")
    severe_action = final_action.isin(LOW_EFFICIENCY_ACTIONS)
    top_sales = _rank_top(sales_units, group) | _rank_top(sales_amount, group)
    top_profit = _rank_top(gross_profit, group)

    result["_low_efficiency_candidate"] = (
        severe_action
        | ad_no_conversion
        | ad_loss
        | stock_abnormal
        | no_sales_stock
        | low_sales_high_stock
        | (gross_profit <= 0)
    )
    result["_severe_low_efficiency_candidate"] = (
        severe_action
        | ad_no_conversion
        | stock_abnormal
        | no_sales_stock
        | low_sales_high_stock
        | (gross_profit <= 0)
    )
    result["_main_candidate"] = (
        ((sales_share >= high_share) | (revenue_share >= high_share) | top_sales)
        & positive_profit
        & has_sales
        & ~stock_abnormal
        & ~ad_no_conversion
    )
    result["_profit_candidate"] = (
        positive_profit
        & ((margin >= high_margin) | (profit_share >= high_share) | top_profit)
        & ~stock_abnormal
        & ~ad_no_conversion
    )
    result["_traffic_candidate"] = (
        ((ad_share >= high_share) | (impression_share >= high_share) | (click_share >= high_share) | (sales_share >= medium_share))
        & (has_sales | has_ads)
        & (
            (margin < high_margin)
            | (profit_share < sales_share * traffic_profit_discount)
            | ad_loss
            | (ad_share > sales_share * 1.3)
        )
        & ~ad_no_conversion
    )

    result["sku_role_candidates"] = result.apply(_candidate_labels, axis=1)
    result["sku_role"] = result.apply(_final_role, axis=1)
    result["sku_role_reason"] = result.apply(_role_reason, axis=1)
    return result.drop(
        columns=[
            "_low_efficiency_candidate",
            "_severe_low_efficiency_candidate",
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
