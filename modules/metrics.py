from __future__ import annotations

import numpy as np
import pandas as pd


def _series(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column in df.columns:
        return pd.to_numeric(df[column], errors="coerce")
    return pd.Series(default, index=df.index, dtype="float64")


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    numerator = pd.to_numeric(numerator, errors="coerce")
    denominator = pd.to_numeric(denominator, errors="coerce")
    result = numerator / denominator.replace(0, np.nan)
    return result


def calculate_metrics(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    sales_7d_units = _series(result, "sales_7d_units")
    sales_14d_units = _series(result, "sales_14d_units")
    predicted_daily_sales = _series(result, "predicted_daily_sales", np.nan)
    total_supply_qty = _series(result, "total_supply_qty")
    available_qty = _series(result, "available_qty", np.nan)
    stock_days = _series(result, "stock_days", np.nan)
    ad_spend = _series(result, "ad_spend")
    ad_sales = _series(result, "ad_sales")
    order_gross_margin = _series(result, "order_gross_margin", np.nan)
    acos = _series(result, "acos", np.nan)

    result["avg_sales_7d"] = sales_7d_units / 7
    result["avg_sales_14d"] = sales_14d_units / 14

    sales_candidates = pd.concat(
        [
            result["avg_sales_7d"],
            result["avg_sales_14d"] * 0.8,
            predicted_daily_sales,
        ],
        axis=1,
    )
    result["main_daily_sales"] = sales_candidates.max(axis=1, skipna=True).fillna(0.0)

    result["calculated_stock_days"] = np.where(
        result["main_daily_sales"] <= 0,
        np.inf,
        total_supply_qty / result["main_daily_sales"],
    )

    has_available_qty = "available_qty" in result.columns and not available_qty.isna().all()
    if has_available_qty:
        result["available_stock_days"] = np.where(
            result["main_daily_sales"] <= 0,
            np.inf,
            available_qty.fillna(0.0) / result["main_daily_sales"],
        )
    else:
        result["available_stock_days"] = stock_days

    result["break_even_acos"] = order_gross_margin
    result["ad_no_conversion_flag"] = (ad_spend > 0) & (ad_sales <= 0)
    result["acos_over_margin_flag"] = (acos >= order_gross_margin) & order_gross_margin.notna()

    result["recent_sales_trend"] = np.select(
        [
            (sales_7d_units == 0) & (sales_14d_units == 0),
            result["avg_sales_7d"] > result["avg_sales_14d"] * 1.3,
            result["avg_sales_7d"] < result["avg_sales_14d"] * 0.7,
        ],
        ["无销量", "近期起量", "近期下滑"],
        default="销量稳定",
    )

    result["division_by_zero_flag"] = result["main_daily_sales"] <= 0
    return result
