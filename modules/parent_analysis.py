from __future__ import annotations

import numpy as np
import pandas as pd

from .aggregation import aggregate_dimension


def _safe_share(value: float, total: float) -> float:
    if total == 0 or pd.isna(total):
        return np.nan
    return float(value / total)


def parent_structure_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    if "parent_asin" not in df.columns:
        return pd.DataFrame()

    source = df.copy()
    source["parent_asin"] = source["parent_asin"].astype("string").fillna("").str.strip()
    source = source[source["parent_asin"] != ""]
    if source.empty:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    for parent_asin, group in source.groupby("parent_asin"):
        total_sales = pd.to_numeric(group.get("sales_14d_units"), errors="coerce").fillna(0).sum()
        total_stock = pd.to_numeric(group.get("total_supply_qty"), errors="coerce").fillna(0).sum()
        total_ad_spend = pd.to_numeric(group.get("ad_spend"), errors="coerce").fillna(0).sum()
        total_profit = pd.to_numeric(group.get("order_gross_profit"), errors="coerce").fillna(0).sum()

        for _, sku in group.iterrows():
            sales_share = _safe_share(float(sku.get("sales_14d_units", 0) or 0), float(total_sales))
            stock_share = _safe_share(float(sku.get("total_supply_qty", 0) or 0), float(total_stock))
            ad_share = _safe_share(float(sku.get("ad_spend", 0) or 0), float(total_ad_spend))
            profit_share = _safe_share(float(sku.get("order_gross_profit", 0) or 0), float(total_profit))
            gross_profit = pd.to_numeric(pd.Series([sku.get("order_gross_profit")]), errors="coerce").iloc[0]

            problems: list[str] = []
            if not pd.isna(sales_share) and not pd.isna(stock_share) and sales_share >= 0.4 and stock_share <= 0.2:
                problems.append("热卖变体缺货风险")
            if not pd.isna(sales_share) and not pd.isna(stock_share) and sales_share <= 0.1 and stock_share >= 0.3:
                problems.append("滞销变体压货")
            if not pd.isna(ad_share) and ad_share >= 0.4 and not pd.isna(gross_profit) and gross_profit <= 0:
                problems.append("广告错配")
            if not pd.isna(gross_profit) and gross_profit <= 0 and not pd.isna(sales_share) and sales_share >= 0.2:
                problems.append("高销量亏损变体")

            if problems:
                rows.append(
                    {
                        "parent_asin": parent_asin,
                        "sku": sku.get("sku", ""),
                        "spu": sku.get("spu", ""),
                        "product_line": sku.get("product_line", ""),
                        "sales_14d_units": sku.get("sales_14d_units", np.nan),
                        "total_supply_qty": sku.get("total_supply_qty", np.nan),
                        "ad_spend": sku.get("ad_spend", np.nan),
                        "order_gross_profit": gross_profit,
                        "order_gross_margin": sku.get("order_gross_margin", np.nan),
                        "sku_sales_share_in_parent": sales_share,
                        "sku_stock_share_in_parent": stock_share,
                        "sku_ad_spend_share_in_parent": ad_share,
                        "sku_profit_share_in_parent": profit_share,
                        "structure_problem": "；".join(problems),
                        "final_action": sku.get("final_action", ""),
                        "reason": sku.get("reason", ""),
                    }
                )

    return pd.DataFrame(rows)


def _parent_status(row: pd.Series, imbalanced_parents: set[str]) -> str:
    gross_profit = row.get("order_gross_profit")
    margin = row.get("order_gross_margin")
    ad_spend = row.get("ad_spend")
    acos = row.get("acos")
    stock_days = row.get("weighted_stock_days")
    parent_asin = str(row.get("parent_asin", ""))

    if not pd.isna(gross_profit) and gross_profit <= 0:
        return "父体亏损"
    if not pd.isna(ad_spend) and ad_spend > 0 and not pd.isna(acos) and not pd.isna(margin) and acos >= margin:
        return "父体广告亏损"
    if not pd.isna(stock_days) and stock_days < 30:
        return "父体缺货风险"
    if not pd.isna(stock_days) and stock_days > 180:
        return "父体高库存风险"
    if parent_asin in imbalanced_parents:
        return "父体结构失衡"
    if not pd.isna(stock_days) and 30 <= stock_days <= 120 and not pd.isna(margin) and margin > 0:
        return "父体健康"
    return "父体需复核"


def analyze_parent(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    anomalies = parent_structure_anomalies(df)
    summary = aggregate_dimension(df, "parent_asin")
    if summary.empty:
        return summary, anomalies

    imbalanced = set(anomalies["parent_asin"].astype(str)) if not anomalies.empty else set()
    summary["parent_status"] = summary.apply(lambda row: _parent_status(row, imbalanced), axis=1)
    ordered = [
        "parent_asin",
        "parent_status",
        "sku_count",
        "spu",
        "product_line",
        "sales_7d_units",
        "sales_14d_units",
        "sales_7d_amount",
        "sales_14d_amount",
        "total_supply_qty",
        "available_qty",
        "inbound_qty",
        "recommended_replenishment_qty",
        "ad_spend",
        "ad_sales",
        "order_gross_profit",
        "weighted_stock_days",
        "acos",
        "order_gross_margin",
        "aged_inventory_181_plus",
        "recent_sales_trend",
    ]
    for column in ordered:
        if column not in summary.columns:
            summary[column] = pd.NA
    return summary[ordered], anomalies
