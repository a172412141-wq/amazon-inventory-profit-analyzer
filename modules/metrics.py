from __future__ import annotations

import numpy as np
import pandas as pd


def _threshold(thresholds: dict | None, path: tuple[str, ...], default: float) -> float:
    current = thresholds or {}
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return float(current)


def _series(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column in df.columns:
        return pd.to_numeric(df[column], errors="coerce")
    return pd.Series(default, index=df.index, dtype="float64")


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    numerator = pd.to_numeric(numerator, errors="coerce")
    denominator = pd.to_numeric(denominator, errors="coerce")
    result = numerator / denominator.replace(0, np.nan)
    return result


def calculate_metrics(df: pd.DataFrame, thresholds: dict | None = None) -> pd.DataFrame:
    result = df.copy()

    sales_7d_units = _series(result, "sales_7d_units")
    sales_14d_units = _series(result, "sales_14d_units")
    sales_7d_amount = _series(result, "sales_7d_amount", np.nan)
    sales_14d_amount = _series(result, "sales_14d_amount", np.nan)
    predicted_daily_sales = _series(result, "predicted_daily_sales", np.nan)
    total_supply_qty = _series(result, "total_supply_qty")
    available_qty = _series(result, "available_qty", np.nan)
    inbound_qty = _series(result, "inbound_qty")
    ad_spend = _series(result, "ad_spend")
    ad_sales = _series(result, "ad_sales")
    ad_impressions = _series(result, "ad_impressions")
    ad_clicks = _series(result, "ad_clicks")
    ad_orders = _series(result, "ad_orders")
    cpc_input = _series(result, "cpc", np.nan)
    ctr_input = _series(result, "ctr", np.nan)
    ad_cvr_input = _series(result, "ad_cvr", np.nan)
    cvr_input = _series(result, "cvr", np.nan)
    sessions_7d = _series(result, "sessions_7d", np.nan)
    sessions_14d = _series(result, "sessions_14d", np.nan)
    order_gross_margin = _series(result, "order_gross_margin", np.nan)
    acos = _series(result, "acos", np.nan)
    ideal_turnover_days = _threshold(thresholds, ("inventory", "ideal_turnover_days"), 90)

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
    result["current_daily_sales_units"] = np.where(
        sales_7d_units > 0,
        sales_7d_units / 7,
        sales_14d_units / 14,
    )
    result["current_daily_sales_amount"] = np.where(
        sales_7d_amount > 0,
        sales_7d_amount / 7,
        sales_14d_amount / 14,
    )

    result["calculated_stock_days"] = np.where(
        result["main_daily_sales"] <= 0,
        np.inf,
        total_supply_qty / result["main_daily_sales"],
    )

    available_missing = result.get(
        "_missing_available_qty",
        pd.Series(False, index=result.index),
    ).fillna(False).astype(bool)
    available_fallback = (total_supply_qty.fillna(0.0) - inbound_qty.fillna(0.0)).clip(lower=0)
    available_stock_qty = available_qty.where(~available_missing, available_fallback)
    available_stock_qty = available_stock_qty.where(available_stock_qty.notna(), available_fallback).clip(lower=0)
    result["available_stock_qty"] = available_stock_qty

    avg_sales_7d = result["avg_sales_7d"]
    result["available_stock_days"] = np.where(
        avg_sales_7d > 0,
        available_stock_qty / avg_sales_7d,
        np.where(available_stock_qty > 0, np.inf, 0.0),
    )
    result["inbound_stock_days"] = np.where(
        avg_sales_7d > 0,
        inbound_qty.fillna(0.0) / avg_sales_7d,
        np.where(inbound_qty.fillna(0.0) > 0, np.inf, 0.0),
    )
    result["ideal_turnover_daily_units"] = np.where(
        ideal_turnover_days > 0,
        available_stock_qty / ideal_turnover_days,
        np.nan,
    )
    result["over_90_stock_qty"] = (available_stock_qty - avg_sales_7d * ideal_turnover_days).clip(lower=0)
    result["over_90_inventory_ratio"] = _safe_divide(result["over_90_stock_qty"], available_stock_qty)
    calculated_cpc = _safe_divide(ad_spend, ad_clicks)
    result["cpc"] = cpc_input.where(cpc_input.notna(), calculated_cpc)
    result["ctr"] = ctr_input.where(ctr_input.notna(), _safe_divide(ad_clicks, ad_impressions))
    result["ad_cvr"] = ad_cvr_input.where(ad_cvr_input.notna(), _safe_divide(ad_orders, ad_clicks))
    calculated_cvr = _safe_divide(sales_14d_units, sessions_14d)
    calculated_cvr = calculated_cvr.where(calculated_cvr.notna(), _safe_divide(sales_7d_units, sessions_7d))
    result["cvr"] = cvr_input.where(cvr_input.notna(), calculated_cvr)
    result["ad_order_share"] = _safe_divide(ad_orders, sales_14d_units)
    amount_share = _safe_divide(ad_sales, sales_14d_amount)
    result["ad_order_share"] = result["ad_order_share"].where(result["ad_order_share"].notna(), amount_share)

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
